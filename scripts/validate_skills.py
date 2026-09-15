#!/usr/bin/env python3
"""Validate the portable RPA Core Agent Skills repository."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import hashlib
import json
import re
import subprocess
import sys
import tempfile
import tomllib
from pathlib import Path, PurePosixPath
from typing import Any, Sequence

from file_transaction import replace_files
from repository_paths import canonical_repository_path

NAME_PATTERN = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
VERSION_PATTERN = re.compile(r"^\d+\.\d+\.\d+(?:-[0-9A-Za-z.-]+)?$")
RELEASE_STATUS = "stable"
DEVELOPMENT_STATUS = "development-only"
COMMIT_PATTERN = re.compile(r"^[0-9a-f]{40}$")
FRONTMATTER_FIELD_PATTERN = re.compile(r"^([a-z][a-z0-9-]*): (.+)$")
MARKDOWN_LINK_PATTERN = re.compile(r"\]\((https://[^)]+)\)")
EXPECTED_FRONTMATTER_FIELDS = {"name", "description"}
FORBIDDEN_SKILL_TEXT = (
    ".internal",
    ".rpiv",
    "P9-",
    "D:\\repos",
    "from rpacore.",
    "import rpacore.",
    "rpacore agent-skills",
    "http://",
    "/blob/main/",
    "/tree/main/",
)
MAX_SKILL_BYTES = 12_000
MAX_SKILL_LINES = 120
EXPECTED_MANIFEST_FIELDS = {
    "schema_version",
    "companion_version",
    "status",
    "license",
    "validation_python",
    "core",
    "skills",
}
EXPECTED_CORE_FIELDS = {
    "version_spec",
    "repository",
    "commit",
    "docs_base",
    "published_release",
}
EXPECTED_SKILL_FIELDS = {"name", "path", "sha256", "resources"}
EXPECTED_RESOURCE_FIELDS = {"path", "sha256"}
PACKAGING_INPUTS = (
    "manifest.toml",
    "LICENSE",
    "NOTICE",
    "docs/distribution.md",
    "scripts/file_transaction.py",
    "scripts/package_skills.py",
    "scripts/repository_paths.py",
    "scripts/validate_skills.py",
)


class ValidationError(ValueError):
    """A bounded repository contract violation."""


@dataclass(frozen=True)
class SkillSource:
    """Validated canonical paths and documentation links for one skill."""

    name: str
    path: Path
    expected_hash: str
    resource: dict[str, Any]
    resource_path: Path
    doc_links: frozenset[str]


def _read_utf8_lf(path: Path) -> str:
    try:
        payload = path.read_bytes()
    except OSError as exc:
        raise ValidationError(f"could not read {path}: {exc}") from exc
    if payload.startswith(b"\xef\xbb\xbf"):
        raise ValidationError(f"{path}: UTF-8 BOM is not allowed")
    if b"\r" in payload:
        raise ValidationError(f"{path}: CR/CRLF line endings are not allowed")
    try:
        text = payload.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ValidationError(f"{path}: expected UTF-8 text") from exc
    if not text.endswith("\n"):
        raise ValidationError(f"{path}: final newline is required")
    return text


def _load_manifest(path: Path) -> dict[str, Any]:
    text = _read_utf8_lf(path)
    try:
        manifest = tomllib.loads(text)
    except tomllib.TOMLDecodeError as exc:
        raise ValidationError(f"{path}: invalid TOML: {exc}") from exc
    if not isinstance(manifest, dict):
        raise ValidationError(f"{path}: expected a TOML table")
    return manifest


def _parse_frontmatter(path: Path, text: str) -> tuple[dict[str, str], str]:
    lines = text.splitlines()
    if not lines or lines[0] != "---":
        raise ValidationError(f"{path}: YAML frontmatter must be first")
    try:
        closing = lines.index("---", 1)
    except ValueError as exc:
        raise ValidationError(f"{path}: frontmatter closing delimiter is missing") from exc
    fields: dict[str, str] = {}
    for line in lines[1:closing]:
        match = FRONTMATTER_FIELD_PATTERN.fullmatch(line)
        if match is None:
            raise ValidationError(f"{path}: unsupported frontmatter line: {line!r}")
        key, value = match.groups()
        if key in fields:
            raise ValidationError(f"{path}: duplicate frontmatter field: {key}")
        fields[key] = value.strip()
    if set(fields) != EXPECTED_FRONTMATTER_FIELDS:
        raise ValidationError(
            f"{path}: frontmatter fields must be exactly "
            f"{sorted(EXPECTED_FRONTMATTER_FIELDS)}"
        )
    body = "\n".join(lines[closing + 1 :]).strip()
    if not body:
        raise ValidationError(f"{path}: skill body is empty")
    return fields, body


def _manifest_string(table: dict[str, Any], key: str, *, context: str) -> str:
    value = table.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ValidationError(f"{context}: {key} must be a non-empty string")
    return value


def _require_exact_fields(table: dict[str, Any], expected: set[str], *, context: str) -> None:
    actual = set(table)
    if actual != expected:
        raise ValidationError(
            f"{context}: fields must be exactly {sorted(expected)}, got {sorted(actual)}"
        )


def repository_path(
    repo_root: Path, value: str, *, context: str, require_file: bool = False
) -> Path:
    """Resolve one POSIX repository-relative path under a shared safety policy."""
    relative = PurePosixPath(value)
    if relative.is_absolute() or not relative.parts or ".." in relative.parts:
        raise ValidationError(f"{context}: unsafe repository path: {value}")
    candidate = canonical_repository_path(
        repo_root,
        Path(*relative.parts),
        error_factory=lambda message: ValidationError(f"{context}: {message}"),
    )
    if require_file and not candidate.is_file():
        raise ValidationError(f"{context}: path must be a regular file: {value}")
    return candidate


def compatibility_document(manifest: dict[str, Any]) -> dict[str, Any]:
    """Return the generated, skill-local compatibility contract."""
    core = manifest["core"]
    return {
        "schema_version": 1,
        "companion": {
            "version": manifest["companion_version"],
            "status": manifest["status"],
            "license": manifest["license"],
        },
        "core": {
            "version_spec": core["version_spec"],
            "commit": core["commit"],
            "docs_base": core["docs_base"],
            "published_release": core["published_release"],
        },
    }


def compatibility_bytes(manifest: dict[str, Any]) -> bytes:
    return (json.dumps(compatibility_document(manifest), indent=2) + "\n").encode("utf-8")


def distributed_files(manifest: dict[str, Any]) -> dict[str, str]:
    """Return every manifest-owned distributed path and digest."""
    files: dict[str, str] = {}
    for entry in manifest["skills"]:
        files[entry["path"]] = entry["sha256"]
        for resource in entry["resources"]:
            files[resource["path"]] = resource["sha256"]
    return dict(sorted(files.items()))


def _expected_companion_status(version: str) -> str:
    """Map a SemVer prerelease suffix to the development support tier."""
    return DEVELOPMENT_STATUS if "-" in version else RELEASE_STATUS


def _validate_manifest_header(manifest: dict[str, Any]) -> dict[str, Any]:
    _require_exact_fields(manifest, EXPECTED_MANIFEST_FIELDS, context="manifest")
    if manifest.get("schema_version") != 2:
        raise ValidationError("manifest: schema_version must be 2")
    version = _manifest_string(manifest, "companion_version", context="manifest")
    if VERSION_PATTERN.fullmatch(version) is None:
        raise ValidationError(f"manifest: invalid companion_version: {version}")
    status = _manifest_string(manifest, "status", context="manifest")
    allowed_statuses = {DEVELOPMENT_STATUS, RELEASE_STATUS}
    if status not in allowed_statuses:
        raise ValidationError(
            f"manifest: status must be one of {sorted(allowed_statuses)}"
        )
    expected_status = _expected_companion_status(version)
    if status != expected_status:
        raise ValidationError(
            f"manifest: companion_version {version} requires status {expected_status!r}"
        )
    if manifest.get("license") != "Apache-2.0":
        raise ValidationError("manifest: license must be Apache-2.0")
    if manifest.get("validation_python") != ">=3.11":
        raise ValidationError("manifest: validation_python must be >=3.11")

    core = manifest.get("core")
    if not isinstance(core, dict):
        raise ValidationError("manifest: [core] table is required")
    _require_exact_fields(core, EXPECTED_CORE_FIELDS, context="manifest.core")
    version_spec = _manifest_string(core, "version_spec", context="manifest.core")
    if re.fullmatch(r"==\d+\.\d+\.\d+", version_spec) is None:
        raise ValidationError("manifest.core: version_spec must select one exact tested release (==x.y.z)")
    repository = _manifest_string(core, "repository", context="manifest.core").rstrip("/")
    commit = _manifest_string(core, "commit", context="manifest.core")
    if COMMIT_PATTERN.fullmatch(commit) is None:
        raise ValidationError("manifest.core: commit must be 40 lowercase hexadecimal characters")
    docs_base = _manifest_string(core, "docs_base", context="manifest.core").rstrip("/")
    expected_docs_base = f"{repository}/blob/{commit}/docs"
    if docs_base != expected_docs_base:
        raise ValidationError(
            f"manifest.core: docs_base must equal immutable baseline {expected_docs_base}"
        )
    if not isinstance(core.get("published_release"), bool):
        raise ValidationError("manifest.core: published_release must be a boolean about Core")
    return core


def _validate_skill_source(
    *,
    repo_root: Path,
    entry: dict[str, Any],
    docs_base: str,
) -> SkillSource:
    _require_exact_fields(entry, EXPECTED_SKILL_FIELDS, context="manifest.skills")
    name = _manifest_string(entry, "name", context="manifest.skills")
    if len(name) > 64 or NAME_PATTERN.fullmatch(name) is None:
        raise ValidationError(f"manifest.skills: invalid skill name: {name}")
    path_value = _manifest_string(entry, "path", context=f"manifest.skills.{name}")
    expected_path = f"skills/{name}/SKILL.md"
    if path_value != expected_path:
        raise ValidationError(
            f"manifest.skills.{name}: path must be {expected_path}, got {path_value}"
        )
    expected_hash = _manifest_string(entry, "sha256", context=f"manifest.skills.{name}")
    if re.fullmatch(r"[0-9a-f]{64}", expected_hash) is None:
        raise ValidationError(f"manifest.skills.{name}: sha256 must be 64 lowercase hex characters")

    resources = entry.get("resources")
    if not isinstance(resources, list) or len(resources) != 1 or not isinstance(resources[0], dict):
        raise ValidationError(f"manifest.skills.{name}: exactly one compatibility resource is required")
    resource = resources[0]
    _require_exact_fields(
        resource, EXPECTED_RESOURCE_FIELDS, context=f"manifest.skills.{name}.resources"
    )
    resource_path_value = _manifest_string(
        resource, "path", context=f"manifest.skills.{name}.resources"
    )
    expected_resource_path = f"skills/{name}/references/compatibility.json"
    if resource_path_value != expected_resource_path:
        raise ValidationError(
            f"manifest.skills.{name}: resource path must be {expected_resource_path}, "
            f"got {resource_path_value}"
        )
    expected_resource_hash = _manifest_string(
        resource, "sha256", context=f"manifest.skills.{name}.resources"
    )
    if re.fullmatch(r"[0-9a-f]{64}", expected_resource_hash) is None:
        raise ValidationError(
            f"manifest.skills.{name}.resources: sha256 must be 64 lowercase hex characters"
        )

    path = repository_path(repo_root, path_value, context=f"manifest.skills.{name}")
    if not path.is_file():
        raise ValidationError(f"{path}: skill file is missing")
    resource_path = repository_path(
        repo_root, resource_path_value, context=f"manifest.skills.{name}.resources"
    )
    references = resource_path.parent
    directory_entries = sorted(path.parent.iterdir(), key=lambda candidate: candidate.name)
    allowed_entries = {path, references}
    extra_entries = [
        candidate for candidate in directory_entries if candidate not in allowed_entries
    ]
    if extra_entries:
        extra = ", ".join(str(candidate.relative_to(repo_root)) for candidate in extra_entries)
        raise ValidationError(f"{path.parent}: portable skill contains extra entries: {extra}")
    if references.exists() and not references.is_dir():
        raise ValidationError(f"{references}: references must be a real directory")
    if references.exists():
        reference_entries = sorted(references.iterdir(), key=lambda candidate: candidate.name)
        extra_references = [candidate for candidate in reference_entries if candidate != resource_path]
        if extra_references:
            extra = ", ".join(
                str(candidate.relative_to(repo_root)) for candidate in extra_references
            )
            raise ValidationError(f"{references}: contains extra entries: {extra}")
        if resource_path.exists() and not resource_path.is_file():
            raise ValidationError(f"{resource_path}: compatibility resource must be a regular file")

    payload = path.read_bytes()
    if len(payload) > MAX_SKILL_BYTES:
        raise ValidationError(f"{path}: exceeds {MAX_SKILL_BYTES} bytes")
    text = _read_utf8_lf(path)
    if len(text.splitlines()) > MAX_SKILL_LINES:
        raise ValidationError(f"{path}: exceeds {MAX_SKILL_LINES} lines")
    fields, body = _parse_frontmatter(path, text)
    if fields["name"] != name:
        raise ValidationError(f"{path}: frontmatter name does not match directory/manifest")
    description = fields["description"]
    if len(description) > 1024:
        raise ValidationError(f"{path}: description exceeds 1024 characters")
    if "rpacore version" not in body or "references/compatibility.json" not in body:
        raise ValidationError(
            f"{path}: body must route compatibility through rpacore version and its local resource"
        )
    folded_text = text.casefold()
    for forbidden in FORBIDDEN_SKILL_TEXT:
        if forbidden.casefold() in folded_text:
            raise ValidationError(f"{path}: forbidden content: {forbidden}")

    links = MARKDOWN_LINK_PATTERN.findall(text)
    doc_links = [link for link in links if "/docs/" in link]
    if not doc_links:
        raise ValidationError(f"{path}: at least one immutable Core documentation link is required")
    expected_prefix = f"{docs_base}/"
    for link in links:
        if not link.startswith(expected_prefix):
            raise ValidationError(f"{path}: absolute link is outside manifest baseline: {link}")
    for link in doc_links:
        relative_doc = PurePosixPath(link.removeprefix(expected_prefix))
        if relative_doc.is_absolute() or ".." in relative_doc.parts or not relative_doc.parts:
            raise ValidationError(f"{path}: unsafe documentation path: {link}")

    return SkillSource(
        name=name,
        path=path,
        expected_hash=expected_hash,
        resource=resource,
        resource_path=resource_path,
        doc_links=frozenset(doc_links),
    )


def _validate_generated_skill(manifest: dict[str, Any], source: SkillSource) -> None:
    """Validate one generated resource and the two manifest-owned digests."""
    path = source.path
    resource = source.resource
    resource_path = source.resource_path
    if not resource_path.is_file():
        raise ValidationError(f"{resource_path}: path must be a regular file")
    if not resource_path.parent.is_dir():
        raise ValidationError(f"{resource_path.parent}: references must be a real directory")

    actual_hash = hashlib.sha256(path.read_bytes()).hexdigest()
    if actual_hash != source.expected_hash:
        raise ValidationError(
            f"{path}: SHA-256 mismatch: manifest={source.expected_hash}, actual={actual_hash}"
        )
    resource_payload = resource_path.read_bytes()
    _read_utf8_lf(resource_path)
    try:
        actual_compatibility = json.loads(resource_payload)
    except json.JSONDecodeError as exc:
        raise ValidationError(f"{resource_path}: invalid JSON: {exc}") from exc
    if actual_compatibility != compatibility_document(manifest):
        raise ValidationError(f"{resource_path}: generated compatibility does not match manifest")
    actual_resource_hash = hashlib.sha256(resource_payload).hexdigest()
    if actual_resource_hash != resource["sha256"]:
        raise ValidationError(
            f"{resource_path}: SHA-256 mismatch: "
            f"manifest={resource['sha256']}, actual={actual_resource_hash}"
        )


def _validate_core_checkout(core_repo: Path, core: dict[str, Any], doc_links: set[str]) -> None:
    if not core_repo.is_dir():
        raise ValidationError(f"core repository does not exist: {core_repo}")
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=core_repo,
            check=True,
            capture_output=True,
            text=True,
        )
    except (OSError, subprocess.CalledProcessError) as exc:
        raise ValidationError(f"could not read Core checkout identity: {exc}") from exc
    expected_commit = str(core["commit"])
    actual_commit = result.stdout.strip()
    if actual_commit != expected_commit:
        raise ValidationError(
            f"Core checkout commit mismatch: expected={expected_commit}, actual={actual_commit}"
        )
    docs_base = str(core["docs_base"]).rstrip("/")
    for link in sorted(doc_links):
        relative = link.removeprefix(f"{docs_base}/")
        object_name = f"{expected_commit}:docs/{relative}"
        try:
            subprocess.run(
                ["git", "cat-file", "-e", object_name],
                cwd=core_repo,
                check=True,
                capture_output=True,
                text=True,
            )
        except (OSError, subprocess.CalledProcessError) as exc:
            raise ValidationError(
                f"Core documentation target is missing at baseline: {object_name}"
            ) from exc


def _load_repository_layout(
    repo_root: Path,
) -> tuple[dict[str, Any], dict[str, Any], list[dict[str, Any]]]:
    manifest = _load_manifest(repo_root / "manifest.toml")
    core = _validate_manifest_header(manifest)
    entries = manifest.get("skills")
    if not isinstance(entries, list) or not entries:
        raise ValidationError("manifest: at least one [[skills]] entry is required")
    if not all(isinstance(entry, dict) for entry in entries):
        raise ValidationError("manifest: every [[skills]] entry must be a table")

    names = [_manifest_string(entry, "name", context="manifest.skills") for entry in entries]
    if names != sorted(names):
        raise ValidationError("manifest: skills must be sorted by name")
    if len(names) != len(set(names)):
        raise ValidationError("manifest: skill names must be unique")
    skill_root = repo_root / "skills"
    if not skill_root.is_dir():
        raise ValidationError(f"skill directory is missing: {skill_root}")
    actual_directories = sorted(path.name for path in skill_root.iterdir() if path.is_dir())
    if actual_directories != names:
        raise ValidationError(
            f"manifest: skill directory set mismatch: manifest={names}, actual={actual_directories}"
        )
    return manifest, core, entries


def _load_validated_sources(
    repo_root: Path, core_repo: Path | None = None
) -> tuple[dict[str, Any], list[dict[str, Any]], list[SkillSource]]:
    manifest, core, entries = _load_repository_layout(repo_root)
    docs_base = str(core["docs_base"]).rstrip("/")
    sources = [
        _validate_skill_source(repo_root=repo_root, entry=entry, docs_base=docs_base)
        for entry in entries
    ]
    if core_repo is not None:
        doc_links = {link for source in sources for link in source.doc_links}
        _validate_core_checkout(core_repo.resolve(), core, doc_links)
    return manifest, entries, sources


def _render_manifest_hashes(repo_root: Path, payloads: dict[str, bytes]) -> bytes:
    """Update canonical hash fields by paths supplied by the parsed manifest."""
    manifest_path = repo_root / "manifest.toml"
    if manifest_path.is_symlink():
        raise ValidationError("manifest: refusing to replace a symlink")
    lines = _read_utf8_lf(manifest_path).splitlines(keepends=True)
    section_starts = [
        index
        for index, line in enumerate(lines)
        if line.rstrip("\n") in {"[[skills]]", "[[skills.resources]]"}
    ]
    seen: set[str] = set()
    for position, start in enumerate(section_starts):
        stop = section_starts[position + 1] if position + 1 < len(section_starts) else len(lines)
        path_rows = [
            (index, match.group(1))
            for index in range(start + 1, stop)
            if (match := re.fullmatch(r'path = "([^"]+)"\n', lines[index])) is not None
        ]
        sha_rows = [
            index
            for index in range(start + 1, stop)
            if re.fullmatch(r'sha256 = "[0-9a-f]{64}"\n', lines[index]) is not None
        ]
        if len(path_rows) != 1 or len(sha_rows) != 1:
            raise ValidationError(
                "manifest: hash regeneration requires one declared path and one canonical "
                "sha256 per distributed-file section"
            )
        _, declared_path = path_rows[0]
        if declared_path not in payloads or declared_path in seen:
            raise ValidationError(
                f"manifest: unexpected or duplicate hash section for {declared_path}"
            )
        seen.add(declared_path)
        digest = hashlib.sha256(payloads[declared_path]).hexdigest()
        lines[sha_rows[0]] = f'sha256 = "{digest}"\n'
    if seen != set(payloads):
        missing = sorted(set(payloads) - seen)
        raise ValidationError(f"manifest: hash sections do not match parsed files: missing={missing}")
    return "".join(lines).encode("utf-8")


def _pending_generated_files(
    repo_root: Path,
    manifest: dict[str, Any],
    sources: list[SkillSource],
) -> dict[Path, bytes]:
    compatibility = compatibility_bytes(manifest)
    payloads: dict[str, bytes] = {}
    pending: dict[Path, bytes] = {}
    for source in sources:
        entry = next(entry for entry in manifest["skills"] if entry["name"] == source.name)
        payloads[entry["path"]] = source.path.read_bytes()
        payloads[source.resource["path"]] = compatibility
        pending[source.resource_path.relative_to(repo_root)] = compatibility
    pending[Path("manifest.toml")] = _render_manifest_hashes(repo_root, payloads)
    return pending


def _validate_pending_repository(
    repo_root: Path,
    entries: list[dict[str, Any]],
    pending: dict[Path, bytes],
) -> None:
    with tempfile.TemporaryDirectory(prefix="rpacore-skills-write-") as directory:
        candidate = Path(directory)
        (candidate / "manifest.toml").write_bytes(pending[Path("manifest.toml")])
        for entry in entries:
            destination = repository_path(candidate, entry["path"], context="pending manifest.skills")
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(
                repository_path(
                    repo_root, entry["path"], context="manifest.skills", require_file=True
                ).read_bytes()
            )
            for resource in entry["resources"]:
                resource_destination = repository_path(
                    candidate,
                    resource["path"],
                    context="pending manifest.skills.resources",
                )
                resource_destination.parent.mkdir(parents=True, exist_ok=True)
                source_resource = repository_path(
                    repo_root, resource["path"], context="manifest.skills.resources"
                )
                resource_destination.write_bytes(
                    pending[source_resource.relative_to(repo_root)]
                )
        validate_repository(candidate)


def regenerate_repository(
    repo_root: Path | str, *, core_repo: Path | str | None = None
) -> dict[str, Any]:
    """Validate source inputs, validate generated state, then replace with rollback."""
    repo_root = Path(repo_root).resolve()
    resolved_core = Path(core_repo).resolve() if core_repo is not None else None
    manifest, entries, sources = _load_validated_sources(repo_root, resolved_core)
    pending = _pending_generated_files(repo_root, manifest, sources)
    _validate_pending_repository(repo_root, entries, pending)
    replace_files(
        repo_root,
        pending,
        lambda: validate_repository(repo_root, core_repo=resolved_core),
    )
    return _load_manifest(repo_root / "manifest.toml")


def validate_repository(
    repo_root: Path | str,
    *,
    core_repo: Path | str | None = None,
    write_hashes: bool = False,
) -> dict[str, Any]:
    """Validate the repository, or regenerate then validate when explicitly requested."""
    if write_hashes:
        return regenerate_repository(repo_root, core_repo=core_repo)

    repo_root = Path(repo_root).resolve()
    resolved_core = Path(core_repo).resolve() if core_repo is not None else None
    manifest, _, sources = _load_validated_sources(repo_root, resolved_core)
    for source in sources:
        _validate_generated_skill(manifest, source)
    return manifest


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=Path.cwd())
    parser.add_argument("--core-repo", type=Path)
    parser.add_argument("--write", action="store_true", help="Validate first, then update only skill hashes.")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    try:
        validate_repository(args.repo_root, core_repo=args.core_repo, write_hashes=args.write)
    except (ValidationError, OSError) as exc:
        print(f"Agent Skills validation failed: {exc}", file=sys.stderr)
        return 1
    print("Agent Skills validation passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

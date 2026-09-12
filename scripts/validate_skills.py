#!/usr/bin/env python3
"""Validate the portable RPA Core Agent Skills repository."""

from __future__ import annotations

import argparse
import hashlib
import re
import subprocess
import sys
import tempfile
import tomllib
from pathlib import Path, PurePosixPath
from typing import Any, Sequence


NAME_PATTERN = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
VERSION_PATTERN = re.compile(r"^\d+\.\d+\.\d+(?:-[0-9A-Za-z.-]+)?$")
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
EXPECTED_SKILL_FIELDS = {"name", "path", "sha256"}


class ValidationError(ValueError):
    """A bounded repository contract violation."""


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


def _skill_path(repo_root: Path, value: str) -> Path:
    relative = PurePosixPath(value)
    if relative.is_absolute() or ".." in relative.parts:
        raise ValidationError(f"manifest: unsafe skill path: {value}")
    candidate = repo_root.joinpath(*relative.parts)
    try:
        candidate.resolve().relative_to(repo_root.resolve())
    except ValueError as exc:
        raise ValidationError(f"manifest: skill path escapes repository: {value}") from exc
    return candidate


def _validate_manifest_header(manifest: dict[str, Any]) -> dict[str, Any]:
    _require_exact_fields(manifest, EXPECTED_MANIFEST_FIELDS, context="manifest")
    if manifest.get("schema_version") != 1:
        raise ValidationError("manifest: schema_version must be 1")
    version = _manifest_string(manifest, "companion_version", context="manifest")
    if VERSION_PATTERN.fullmatch(version) is None:
        raise ValidationError(f"manifest: invalid companion_version: {version}")
    status = _manifest_string(manifest, "status", context="manifest")
    if status != "development-only":
        raise ValidationError("manifest: the unreleased foundation must remain development-only")
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


def _validate_skill(
    *,
    repo_root: Path,
    entry: dict[str, Any],
    docs_base: str,
    verify_hash: bool = True,
) -> str:
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

    path = _skill_path(repo_root, path_value)
    if not path.is_file():
        raise ValidationError(f"{path}: skill file is missing")
    if path.is_symlink() or path.parent.is_symlink():
        raise ValidationError(f"{path}: skill path must not use symlinks")
    directory_entries = sorted(path.parent.iterdir(), key=lambda candidate: candidate.name)
    if directory_entries != [path]:
        extra = ", ".join(
            str(candidate.relative_to(repo_root))
            for candidate in directory_entries
            if candidate != path
        )
        raise ValidationError(f"{path.parent}: instruction-only skill contains extra entries: {extra}")

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
    if "rpacore version" not in body or "manifest.toml" not in body:
        raise ValidationError(
            f"{path}: body must route compatibility through rpacore version and manifest.toml"
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

    actual_hash = hashlib.sha256(payload).hexdigest()
    if verify_hash and actual_hash != expected_hash:
        raise ValidationError(
            f"{path}: SHA-256 mismatch: manifest={expected_hash}, actual={actual_hash}"
        )
    return name


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


def validate_repository(
    repo_root: Path, *, core_repo: Path | None = None, write_hashes: bool = False
) -> dict[str, Any]:
    """Validate the complete repository and return its validated manifest.

    In write mode, return the manifest after hash regeneration. Callers do not
    need to parse the file again or depend on private validation helpers.
    """
    repo_root = repo_root.resolve()
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

    docs_base = str(core["docs_base"]).rstrip("/")
    all_doc_links: set[str] = set()
    for entry in entries:
        name = _validate_skill(
            repo_root=repo_root, entry=entry, docs_base=docs_base,
            verify_hash=not write_hashes,
        )
        path = repo_root / "skills" / name / "SKILL.md"
        all_doc_links.update(
            link for link in MARKDOWN_LINK_PATTERN.findall(_read_utf8_lf(path)) if "/docs/" in link
        )
    if core_repo is not None:
        _validate_core_checkout(core_repo.resolve(), core, all_doc_links)
    if write_hashes:
        _write_hashes(repo_root, entries)
        manifest = _load_manifest(repo_root / "manifest.toml")
    return manifest


def _write_hashes(repo_root: Path, entries: list[dict[str, Any]]) -> None:
    """Replace only hash values after every other validation has succeeded."""
    path = repo_root / "manifest.toml"
    if path.is_symlink():
        raise ValidationError("manifest: refusing to replace a symlink")
    original = _read_utf8_lf(path)
    # This is a deliberately bounded edit of our canonical manifest layout,
    # not a general TOML serializer. Parsing/contract validation happens first;
    # these exact block/hash forms preserve comments and every unrelated byte.
    # Fail closed on other valid TOML spellings rather than guessing at edits.
    blocks = re.split(r"(?m)(?=^\[\[skills\]\]$)", original)
    if len(blocks) != len(entries) + 1:
        raise ValidationError("manifest: hash regeneration requires one [[skills]] block per entry")
    for index, entry in enumerate(entries, 1):
        digest = hashlib.sha256(_skill_path(repo_root, entry["path"]).read_bytes()).hexdigest()
        blocks[index], count = re.subn(
            r'(?m)^sha256 = "[0-9a-f]{64}"$',
            f'sha256 = "{digest}"', blocks[index],
        )
        if count != 1:
            raise ValidationError("manifest: expected one canonical sha256 line per skill block")
    updated = "".join(blocks)
    if updated == original:
        return
    temporary: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", newline="\n", dir=repo_root,
            prefix=".manifest-", suffix=".tmp", delete=False,
        ) as stream:
            temporary = Path(stream.name)
            stream.write(updated)
        temporary.replace(path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


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

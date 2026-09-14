#!/usr/bin/env python3
"""Build or check deterministic portable RPA Core skill packages."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
from typing import Any, Iterator, Sequence
import zipfile

from validate_skills import (
    PACKAGING_INPUTS,
    ValidationError,
    distributed_files,
    repository_path,
    validate_repository,
)


PROFILE = "portable"
PACK_NAME = "rpacore-agent-skills"
ZIP_TIMESTAMP = (1980, 1, 1, 0, 0, 0)


def sha256_of(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _git_identity(source: Path) -> tuple[str, bool]:
    def git(*args: str) -> str:
        result = subprocess.run(
            ["git", "-c", f"safe.directory={source}", *args],
            cwd=source,
            check=True,
            capture_output=True,
            text=True,
        )
        return result.stdout.strip()

    commit = git("rev-parse", "HEAD")
    if len(commit) != 40 or any(character not in "0123456789abcdef" for character in commit):
        raise ValidationError("source Git commit is not a full lowercase SHA-1")
    dirty = bool(git("status", "--porcelain", "--untracked-files=all"))
    return commit, dirty


def _require_ignored_output(source: Path, output: Path) -> None:
    """Allow in-tree output only when Git explicitly ignores that exact path."""
    try:
        relative = output.relative_to(source)
    except ValueError:
        return
    result = subprocess.run(
        [
            "git",
            "-c",
            f"safe.directory={source}",
            "check-ignore",
            "--quiet",
            "--",
            relative.as_posix(),
        ],
        cwd=source,
        capture_output=True,
        text=True,
    )
    if result.returncode == 0:
        return
    if result.returncode == 1:
        raise ValidationError(
            "output below the source must be explicitly Git-ignored: "
            f"{relative.as_posix()}"
        )
    raise subprocess.CalledProcessError(
        result.returncode, result.args, output=result.stdout, stderr=result.stderr
    )


def _copy(source: Path, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_bytes(source.read_bytes())


def _write_zip(source: Path, destination: Path, prefix: str) -> None:
    files = tuple(_iter_files(source))  # Finish path checks before creating output.
    destination.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(destination, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for relative, path in files:
            info = zipfile.ZipInfo(f"{prefix}/{relative}", ZIP_TIMESTAMP)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.create_system = 3
            info.external_attr = 0o100644 << 16
            archive.writestr(info, path.read_bytes(), compresslevel=9)


def _iter_files(root: Path, relative_root: str | None = None) -> Iterator[tuple[str, Path]]:
    base = root if relative_root is None else root / relative_root
    if base.is_symlink() or not base.is_dir():
        raise ValidationError(f"package output must be a real directory: {base}")
    for path in sorted(base.rglob("*")):
        if path.is_symlink():
            raise ValidationError(f"package output must not contain symlinks: {path}")
        if path.is_file():
            yield path.relative_to(root).as_posix(), path


def _walk_files(root: Path, relative_root: str | None = None) -> dict[str, bytes]:
    return {
        relative: path.read_bytes()
        for relative, path in _iter_files(root, relative_root)
    }


def _file_hashes(root: Path, relative_root: str) -> dict[str, str]:
    return {
        relative: sha256_of(path)
        for relative, path in _iter_files(root, relative_root)
    }


def _source_file(source: Path, relative: str) -> Path:
    return repository_path(source, relative, context="package input", require_file=True)


def _common_files(source: Path) -> dict[str, Path]:
    return {
        "INSTALL.md": _source_file(source, "docs/distribution.md"),
        "LICENSE": _source_file(source, "LICENSE"),
        "NOTICE": _source_file(source, "NOTICE"),
    }


def _stage_full(
    source: Path, output: Path, manifest: dict[str, Any], common: dict[str, Path]
) -> None:
    full = output / "full"
    for relative in distributed_files(manifest):
        path = _source_file(source, relative)
        _copy(path, full / path.relative_to(source))
    for destination, path in common.items():
        _copy(path, full / destination)


def _stage_individuals(
    source: Path, output: Path, manifest: dict[str, Any], common: dict[str, Path]
) -> None:
    for entry in manifest["skills"]:
        name = entry["name"]
        individual = output / "individual" / name
        skill_file = _source_file(source, entry["path"])
        _copy(skill_file, individual / "SKILL.md")
        for resource in entry["resources"]:
            resource_file = _source_file(source, resource["path"])
            resource_suffix = resource_file.relative_to(skill_file.parent)
            _copy(resource_file, individual / resource_suffix)
        for destination, path in common.items():
            _copy(path, individual / destination)


def _write_archives(output: Path, manifest: dict[str, Any]) -> None:
    archives = output / "archives"
    _write_zip(output / "full", archives / f"{PACK_NAME}-portable.zip", PACK_NAME)
    for entry in manifest["skills"]:
        name = entry["name"]
        _write_zip(output / "individual" / name, archives / f"{name}.zip", name)


def _build_inventory(
    source: Path,
    output: Path,
    manifest: dict[str, Any],
    *,
    commit: str,
    dirty: bool,
) -> dict[str, Any]:
    files = {}
    files.update(_file_hashes(output, "full"))
    files.update(_file_hashes(output, "individual"))
    artifacts = _file_hashes(output, "archives")
    inventory = {
        "schema_version": 1,
        "profile": PROFILE,
        "source": {"git_commit": commit, "working_tree_dirty": dirty},
        "companion": {
            "version": manifest["companion_version"],
            "status": manifest["status"],
            "license": manifest["license"],
        },
        "core": manifest["core"],
        "files": dict(sorted(files.items())),
        "artifacts": dict(sorted(artifacts.items())),
        "packaging_inputs": {
            relative: sha256_of(_source_file(source, relative))
            for relative in PACKAGING_INPUTS
        },
    }
    inventory_path = output / "release-inventory.json"
    inventory_path.write_text(
        json.dumps(inventory, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n"
    )
    (output / "release-inventory.sha256").write_text(
        f"{sha256_of(inventory_path)}  release-inventory.json\n",
        encoding="utf-8",
        newline="\n",
    )
    return inventory


def _write_package(source: Path, output: Path, *, frozen: bool) -> dict[str, Any]:
    manifest = validate_repository(source)
    commit, dirty = _git_identity(source)
    if frozen and dirty:
        raise ValidationError("frozen package input must be a clean Git worktree")
    common = _common_files(source)
    _stage_full(source, output, manifest, common)
    _stage_individuals(source, output, manifest, common)
    _write_archives(output, manifest)
    return _build_inventory(
        source, output, manifest, commit=commit, dirty=dirty
    )


def build(
    source: Path, output: Path, *, profile: str = PROFILE, frozen: bool = False
) -> dict[str, Any]:
    if profile != PROFILE:
        raise ValidationError(f"unsupported package profile: {profile}")
    source = source.resolve()
    output = output.resolve()
    if output == source or output in source.parents:
        raise ValidationError("output must not be the source or one of its parents")
    _require_ignored_output(source, output)
    if output.exists() or output.is_symlink():
        raise ValidationError(f"build output already exists: {output}")
    output.mkdir(parents=True)
    try:
        return _write_package(source, output, frozen=frozen)
    except Exception:
        shutil.rmtree(output)
        raise


def _output_files(root: Path) -> dict[str, bytes]:
    return _walk_files(root)


def check(
    source: Path, output: Path, *, profile: str = PROFILE, frozen: bool = False
) -> None:
    source = source.resolve()
    output = output.resolve()
    actual = _output_files(output)
    with tempfile.TemporaryDirectory(prefix="rpacore-skills-check-") as directory:
        expected_root = Path(directory) / "expected"
        build(source, expected_root, profile=profile, frozen=frozen)
        expected = _output_files(expected_root)
    if set(actual) != set(expected):
        missing = sorted(set(expected) - set(actual))
        extra = sorted(set(actual) - set(expected))
        raise ValidationError(f"package inventory mismatch: missing={missing}, extra={extra}")
    changed = [path for path in expected if actual[path] != expected[path]]
    if changed:
        raise ValidationError(f"package content mismatch: {changed}")


def _add_common_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--repo-root", type=Path, required=True, help="Canonical source repository")
    parser.add_argument("--profile", choices=[PROFILE], required=True)
    parser.add_argument("--output", type=Path, required=True, help="Build or check directory")
    parser.add_argument(
        "--frozen",
        action="store_true",
        help="Require HEAD-clean tracked files and no non-ignored untracked files",
    )


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    _add_common_arguments(commands.add_parser("build", help="Create a new deterministic output"))
    _add_common_arguments(commands.add_parser("check", help="Check an output without changing it"))
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        if args.command == "build":
            build(args.repo_root, args.output, profile=args.profile, frozen=args.frozen)
        else:
            check(args.repo_root, args.output, profile=args.profile, frozen=args.frozen)
    except (ValidationError, OSError, subprocess.CalledProcessError, zipfile.BadZipFile) as exc:
        print(f"Skill packaging failed: {exc}", file=sys.stderr)
        return 1
    print(f"Skill packaging {args.command} passed: {args.output.resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Verify downloaded portable release assets and rehearse detached installs."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import shutil
import stat
import subprocess
import sys
from typing import Any, Sequence
import zipfile

from package_skills import (
    ArchiveSpec,
    INVENTORY_CHECKSUM_NAME,
    INVENTORY_NAME,
    PROFILE,
    archive_specs,
    check,
    file_hashes,
    inventory_checksum_text,
    sha256_of,
)
from validate_skills import ValidationError, repository_path, validate_repository


SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")


def _load_inventory(assets: Path) -> dict[str, Any]:
    if assets.is_symlink() or not assets.is_dir():
        raise ValidationError(f"release assets must be a real directory: {assets}")
    inventory_path = assets / INVENTORY_NAME
    checksum_path = assets / INVENTORY_CHECKSUM_NAME
    try:
        inventory_bytes = inventory_path.read_bytes()
        checksum_bytes = checksum_path.read_bytes()
        checksum_text = checksum_bytes.decode("utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        raise ValidationError(f"release inventory/checksum is missing or invalid: {exc}") from exc
    expected_checksum = inventory_checksum_text(
        hashlib.sha256(inventory_bytes).hexdigest()
    )
    if checksum_text != expected_checksum:
        raise ValidationError("release inventory checksum mismatch")
    try:
        inventory = json.loads(inventory_bytes)
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise ValidationError("release inventory is not valid UTF-8 JSON") from exc
    if not isinstance(inventory, dict) or inventory.get("schema_version") != 1:
        raise ValidationError("release inventory schema_version must be 1")
    return inventory


def _validate_asset_set(
    assets: Path, manifest: dict[str, Any], inventory: dict[str, Any]
) -> dict[str, ArchiveSpec]:
    specs = archive_specs(manifest)
    expected_artifacts = {f"archives/{name}" for name in specs}
    artifacts = inventory.get("artifacts")
    if not isinstance(artifacts, dict) or set(artifacts) != expected_artifacts:
        raise ValidationError("release inventory artifact allowlist mismatch")
    expected_assets = set(specs) | {INVENTORY_NAME, INVENTORY_CHECKSUM_NAME}
    entries = list(assets.iterdir())
    if any(path.is_symlink() or not path.is_file() for path in entries):
        raise ValidationError("release asset directory must contain regular files only")
    actual_assets = {path.name for path in entries}
    if actual_assets != expected_assets:
        missing = sorted(expected_assets - actual_assets)
        extra = sorted(actual_assets - expected_assets)
        raise ValidationError(f"release asset allowlist mismatch: missing={missing}, extra={extra}")
    for archive_name in specs:
        relative = f"archives/{archive_name}"
        digest = artifacts[relative]
        if not isinstance(digest, str) or SHA256_PATTERN.fullmatch(digest) is None:
            raise ValidationError(f"release inventory has invalid SHA-256: {relative}")
        archive = assets / archive_name
        if sha256_of(archive) != digest:
            raise ValidationError(f"release archive SHA-256 mismatch: {archive.name}")
    return specs


def _archive_payloads(
    assets: Path,
    specs: dict[str, ArchiveSpec],
    inventory: dict[str, Any],
) -> dict[str, bytes]:
    files = inventory.get("files")
    if not isinstance(files, dict):
        raise ValidationError("release inventory files must be an object")
    if any(
        not isinstance(relative, str)
        or not isinstance(digest, str)
        or SHA256_PATTERN.fullmatch(digest) is None
        for relative, digest in files.items()
    ):
        raise ValidationError("release inventory contains an invalid file identity")

    payloads: dict[str, bytes] = {}
    for archive_name, spec in specs.items():
        source_prefix = f"{spec.staged_dir}/"
        expected = {
            f"{spec.prefix}/{relative.removeprefix(source_prefix)}": (relative, digest)
            for relative, digest in files.items()
            if relative.startswith(source_prefix)
        }
        if not expected:
            raise ValidationError(f"release inventory has no files for {archive_name}")
        with zipfile.ZipFile(assets / archive_name) as archive:
            infos = archive.infolist()
            names = [info.filename for info in infos]
            if len(names) != len(set(names)) or set(names) != set(expected):
                raise ValidationError(f"release archive member allowlist mismatch: {archive_name}")
            for info in infos:
                mode = info.external_attr >> 16
                if info.is_dir() or stat.S_ISLNK(mode):
                    raise ValidationError(
                        f"release archive must contain regular files only: {archive_name}"
                    )
                relative, digest = expected[info.filename]
                payload = archive.read(info)
                if hashlib.sha256(payload).hexdigest() != digest:
                    raise ValidationError(
                        f"release archive member SHA-256 mismatch: {info.filename}"
                    )
                if relative in payloads and payloads[relative] != payload:
                    raise ValidationError(f"conflicting release archive member: {relative}")
                payloads[relative] = payload
    if set(payloads) != set(files):
        raise ValidationError("release archives do not cover the inventory file set")
    return payloads


def _require_new_siblings(assets: Path, output: Path, install_root: Path) -> None:
    if output.exists() or output.is_symlink():
        raise ValidationError(f"reconstructed output already exists: {output}")
    if install_root.exists() or install_root.is_symlink():
        raise ValidationError(f"install rehearsal output already exists: {install_root}")
    pairs = ((assets, output), (assets, install_root), (output, install_root))
    if any(left == right or left in right.parents or right in left.parents for left, right in pairs):
        raise ValidationError("assets, reconstructed output, and install output must not overlap")


def _write_candidate(
    assets: Path,
    output: Path,
    payloads: dict[str, bytes],
    specs: dict[str, ArchiveSpec],
) -> None:
    for relative, payload in payloads.items():
        destination = repository_path(output, relative, context="release inventory")
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(payload)
    archives = output / "archives"
    archives.mkdir()
    for archive_name in specs:
        shutil.copyfile(assets / archive_name, archives / archive_name)
    shutil.copyfile(assets / INVENTORY_NAME, output / INVENTORY_NAME)
    shutil.copyfile(
        assets / INVENTORY_CHECKSUM_NAME, output / INVENTORY_CHECKSUM_NAME
    )


def _rehearse_installs(
    output: Path,
    install_root: Path,
    manifest: dict[str, Any],
    inventory: dict[str, Any],
) -> None:
    inventory_files = inventory["files"]
    for layout in ("full", "individual"):
        for entry in manifest["skills"]:
            name = entry["name"]
            relative_source = (
                f"full/skills/{name}" if layout == "full" else f"individual/{name}"
            )
            source = output / relative_source
            destination = install_root / layout / name
            shutil.copytree(source, destination)
            source_prefix = f"{relative_source}/"
            expected = {
                relative.removeprefix(source_prefix): digest
                for relative, digest in inventory_files.items()
                if relative.startswith(source_prefix)
            }
            if file_hashes(destination) != expected:
                raise ValidationError(f"detached {layout} install mismatch: {name}")


def verify_release(
    repo_root: Path,
    assets: Path,
    output: Path,
    install_root: Path,
    *,
    profile: str = PROFILE,
    frozen: bool = False,
) -> dict[str, Any]:
    if profile != PROFILE:
        raise ValidationError(f"unsupported package profile: {profile}")
    for label, path in (
        ("release assets", assets),
        ("reconstructed output", output),
        ("install rehearsal output", install_root),
    ):
        if path.is_symlink():
            raise ValidationError(f"{label} must not be a symlink: {path}")
    repo_root = repo_root.resolve()
    assets = assets.resolve()
    output = output.resolve()
    install_root = install_root.resolve()
    _require_new_siblings(assets, output, install_root)
    manifest = validate_repository(repo_root)
    inventory = _load_inventory(assets)
    specs = _validate_asset_set(assets, manifest, inventory)
    payloads = _archive_payloads(assets, specs, inventory)
    created: list[Path] = []
    try:
        output.mkdir(parents=True)
        created.append(output)
        _write_candidate(assets, output, payloads, specs)
        check(repo_root, output, profile=profile, frozen=frozen)
        install_root.mkdir(parents=True)
        created.append(install_root)
        _rehearse_installs(output, install_root, manifest, inventory)
    except Exception:
        for path in reversed(created):
            shutil.rmtree(path, ignore_errors=True)
        raise
    return inventory


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, required=True)
    parser.add_argument("--assets", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--install-root", type=Path, required=True)
    parser.add_argument("--profile", choices=[PROFILE], required=True)
    parser.add_argument(
        "--frozen",
        action="store_true",
        help="Require the checked-out source to be HEAD-clean",
    )
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        verify_release(
            args.repo_root,
            args.assets,
            args.output,
            args.install_root,
            profile=args.profile,
            frozen=args.frozen,
        )
    except (ValidationError, OSError, subprocess.CalledProcessError, zipfile.BadZipFile) as exc:
        print(f"Release verification failed: {exc}", file=sys.stderr)
        return 1
    print(f"Release verification passed: {args.assets.resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Verify reference consumers against an exact source-matched installed wheel."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys
from typing import Any, Sequence
import zipfile

import validate_skills
from validate_skills import ValidationError, validate_repository


def sha256_of(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def wheel_contract(wheel: Path, core_repo: Path, commit: str, version: str) -> dict[str, str]:
    def git(*args: str) -> bytes:
        return subprocess.run(["git", *args], cwd=core_repo, check=True,
                              capture_output=True).stdout
    names = git("ls-tree", "-r", "--name-only", commit, "--", "rpacore").decode().splitlines()
    source_names = {name for name in names if name.endswith(".py")}
    try:
        archive = zipfile.ZipFile(wheel)
    except zipfile.BadZipFile as exc:
        raise ValidationError(f"invalid wheel archive: {wheel}") from exc
    with archive:
        all_names = archive.namelist()
        names = {name for name in all_names if name.startswith("rpacore/") and name.endswith(".py")}
        if names != source_names or len(all_names) != len(set(all_names)):
            raise ValidationError("wheel package files differ from the exact Core commit")
        metadata_name = f"rpacore-{version}.dist-info/METADATA"
        try:
            metadata_text = archive.read(metadata_name).decode("utf-8")
        except (KeyError, UnicodeDecodeError) as exc:
            raise ValidationError(f"wheel metadata is missing or invalid: {metadata_name}") from exc
        if f"Version: {version}" not in metadata_text.splitlines():
            raise ValidationError("wheel version differs from manifest")
        hashes = {}
        for name in sorted(names):
            payload = archive.read(name)
            # Windows checkout/archive attributes may convert Python source to
            # CRLF. Compare only that newline normalization; installed files
            # below must still match the wheel's actual bytes exactly.
            if payload.replace(b"\r\n", b"\n") != git("show", f"{commit}:{name}").replace(b"\r\n", b"\n"):
                raise ValidationError(f"wheel source differs from Core commit: {name}")
            hashes[name] = hashlib.sha256(payload).hexdigest()
    return hashes


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--core-repo", type=Path, required=True)
    parser.add_argument("--wheel", type=Path, required=True)
    parser.add_argument("--python", type=Path, required=True, help="Disposable environment with the wheel and pytest installed")
    evidence = parser.add_mutually_exclusive_group()
    evidence.add_argument("--receipt", type=Path, help="New local JSON evidence file; never overwritten")
    evidence.add_argument("--check-receipt", type=Path,
                          help="Rerun verification in the same environment, including its absolute paths")
    return parser.parse_args(argv)


def run_checks(args: argparse.Namespace) -> tuple[dict[str, Any], dict[str, Any]]:
    repo = args.repo_root.resolve()
    manifest = validate_repository(repo, core_repo=args.core_repo)
    version = manifest["core"]["version_spec"].removeprefix("==")
    contract = wheel_contract(args.wheel, args.core_repo, manifest["core"]["commit"], version)
    # POSIX virtual-environment interpreters are commonly symlinks to the base
    # Python. Keep the absolute venv entrypoint instead of resolving out of the
    # environment that owns the installed wheel.
    command = [str(args.python.absolute()), "-I", "-B", str(repo / "tests/consumer_scenarios.py")]
    result = subprocess.run(command, input=json.dumps({"version": version, "files": contract}),
                            capture_output=True, text=True, timeout=300)
    print(result.stderr, file=sys.stderr, end="")
    if result.returncode:
        raise ValidationError("installed consumer scenarios failed; no success receipt written")
    try:
        outcomes = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise ValidationError("consumer scenarios did not return valid JSON results") from exc
    if not isinstance(outcomes, dict):
        raise ValidationError("consumer scenarios must return a JSON results object")
    return manifest, outcomes


def build_receipt(repo: Path, manifest: dict[str, Any], wheel: Path,
                  outcomes: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": 2,
        "evidence_kind": "reference-consumer-validation",
        "companion_version": manifest["companion_version"],
        "manifest_sha256": sha256_of(repo / "manifest.toml"),
        "distributed_files": validate_skills.distributed_files(manifest),
        "packaging_inputs": {
            relative: sha256_of(
                validate_skills.repository_path(
                    repo, relative, context="receipt packaging input", require_file=True
                )
            )
            for relative in validate_skills.PACKAGING_INPUTS
        },
        "core_commit": manifest["core"]["commit"],
        "core_version": manifest["core"]["version_spec"].removeprefix("=="),
        "wheel_sha256": sha256_of(wheel),
        "wheel_source_matches_commit": True,
        "source_comparison": "Python file set and content, CRLF normalized to LF",
        "validator_sha256": sha256_of(Path(validate_skills.__file__)),
        "consumer_verifier_sha256": sha256_of(Path(__file__)),
        "consumer_scenarios_sha256": sha256_of(repo / "tests/consumer_scenarios.py"),
        "documentation_base": manifest["core"]["docs_base"],
        "results": outcomes,
        "distribution_channel": None,
        "agent_generated_output_evaluated": False,
    }


def emit_or_check_receipt(receipt: dict[str, Any], *, receipt_path: Path | None = None,
                          check_path: Path | None = None) -> None:
    if check_path is not None:
        try:
            previous = json.loads(check_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError) as exc:
            raise ValidationError(f"receipt is not valid UTF-8 JSON: {check_path}") from exc
        previous_schema = previous.get("schema_version") if isinstance(previous, dict) else None
        current_schema = receipt.get("schema_version")
        if isinstance(previous, dict) and previous_schema != current_schema:
            raise ValidationError(
                f"receipt schema {previous_schema!r} is incompatible with the "
                f"schema-{current_schema!r} verifier; schema-1 or missing-schema "
                "evidence is superseded by schema 2, so retain the matching original "
                "verifier with that evidence or regenerate a current receipt"
            )
        if previous != receipt:
            raise ValidationError(
                "receipt is stale or describes different verification inputs/results; "
                "Python version, executable and installed Core paths are part of its identity"
            )
    encoded = json.dumps(receipt, indent=2) + "\n"
    if receipt_path is not None:
        with receipt_path.open("x", encoding="utf-8", newline="\n") as stream:
            stream.write(encoded)
    print(encoded, end="")


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        manifest, outcomes = run_checks(args)
        receipt = build_receipt(args.repo_root.resolve(), manifest, args.wheel, outcomes)
        emit_or_check_receipt(receipt, receipt_path=args.receipt, check_path=args.check_receipt)
    except ValidationError as exc:
        print(f"Consumer verification failed: {exc}", file=sys.stderr)
        return 1
    except subprocess.TimeoutExpired as exc:
        print(f"Consumer verification command timed out after {exc.timeout}s", file=sys.stderr)
        return 1
    except subprocess.CalledProcessError as exc:
        print(f"Consumer verification command failed (exit {exc.returncode}): {exc.cmd}", file=sys.stderr)
        print(exc.stderr.decode(errors="replace") if isinstance(exc.stderr, bytes) else exc.stderr or "",
              file=sys.stderr)
        return 1
    except zipfile.BadZipFile as exc:
        print(f"Consumer verification wheel archive failed: {exc}", file=sys.stderr)
        return 1
    except OSError as exc:
        print(f"Consumer verification I/O failed: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

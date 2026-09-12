#!/usr/bin/env python3
"""Build and verify the pinned Core baseline in fresh, retained run directories."""
from __future__ import annotations

import argparse
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from typing import Sequence

from validate_skills import ValidationError, validate_repository
import verify_consumer


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=Path(__file__).resolve().parents[1])
    commands = parser.add_subparsers(dest="command", required=True)
    ref = commands.add_parser("core-ref", help="Read the validated manifest's Core commit")
    ref.add_argument("--github-output", action="store_true", help="Append commit to GITHUB_OUTPUT")
    verify = commands.add_parser("verify", help="Build, install and verify in a fresh run directory")
    verify.add_argument("--core-repo", type=Path, required=True)
    verify.add_argument("--evidence-root", type=Path, default=Path("validation-artifacts"))
    return parser.parse_args(argv)


def run(*args: str | Path) -> None:
    subprocess.run([str(arg) for arg in args], check=True, timeout=600)


def venv_python(directory: Path) -> Path:
    return directory / ("Scripts/python.exe" if os.name == "nt" else "bin/python")


def prepare_consumer(core_repo: Path, run_dir: Path) -> tuple[Path, Path]:
    wheels = run_dir / "wheels"
    wheels.mkdir(parents=True, exist_ok=True)
    build_env = run_dir / "build-venv"
    run(sys.executable, "-m", "venv", build_env)
    build_python = venv_python(build_env)
    run(build_python, "-m", "pip", "install", "setuptools==80.10.2", "wheel==0.47.0")
    run(build_python, "-m", "pip", "wheel", "--no-build-isolation", "--no-deps",
        "--wheel-dir", wheels, core_repo)
    built = list(wheels.glob("rpacore-*.whl"))
    if len(built) != 1:
        raise ValidationError("expected exactly one Core wheel in the fresh run directory")
    consumer_env = run_dir / "consumer-venv"
    run(sys.executable, "-m", "venv", consumer_env)
    consumer_python = venv_python(consumer_env)
    run(consumer_python, "-m", "pip", "install", "--no-deps", built[0])
    run(consumer_python, "-m", "pip", "install", "pytest==9.0.3")
    return built[0], consumer_python


def verify_baseline(repo: Path, core_repo: Path, evidence_root: Path) -> Path:
    validate_repository(repo, core_repo=core_repo)
    evidence_root.mkdir(parents=True, exist_ok=True)
    # A rerun retains earlier receipts and cannot accidentally reuse their wheel
    # or environment. Failed runs remain inspectable, without a success receipt.
    run_dir = Path(tempfile.mkdtemp(prefix="run-", dir=evidence_root))
    print(f"Baseline run directory: {run_dir}", file=sys.stderr)
    wheel, consumer_python = prepare_consumer(core_repo, run_dir)
    receipt = run_dir / "consumer.json"
    result = verify_consumer.main([
        "--repo-root", str(repo), "--core-repo", str(core_repo),
        "--wheel", str(wheel), "--python", str(consumer_python), "--receipt", str(receipt),
    ])
    if result:
        raise ValidationError(f"consumer verification failed; inspect {run_dir}")
    return receipt


def emit_core_ref(repo: Path, *, github_output: bool) -> None:
    commit = validate_repository(repo)["core"]["commit"]
    if github_output:
        destination = os.environ.get("GITHUB_OUTPUT")
        if not destination:
            raise ValidationError("--github-output requires GITHUB_OUTPUT")
        with Path(destination).open("a", encoding="utf-8", newline="\n") as stream:
            stream.write(f"commit={commit}\n")
    else:
        print(commit)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        repo = args.repo_root.resolve()
        if args.command == "core-ref":
            emit_core_ref(repo, github_output=args.github_output)
        else:
            verify_baseline(repo, args.core_repo.resolve(), args.evidence_root.resolve())
    except ValidationError as exc:
        print(f"Baseline validation failed: {exc}", file=sys.stderr)
        return 1
    except subprocess.TimeoutExpired as exc:
        print(f"Baseline command timed out after {exc.timeout}s: {exc.cmd}", file=sys.stderr)
        return 1
    except subprocess.CalledProcessError as exc:
        print(f"Baseline command failed (exit {exc.returncode}): {exc.cmd}", file=sys.stderr)
        return 1
    except OSError as exc:
        print(f"Baseline I/O failed: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

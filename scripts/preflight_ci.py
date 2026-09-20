#!/usr/bin/env python3
"""Run release-critical Windows and WSL checks before committing."""

from __future__ import annotations

import argparse
from contextlib import contextmanager
from dataclasses import dataclass
import hashlib
import json
from pathlib import Path, PurePosixPath
import subprocess
import sys
import tempfile
from typing import Callable, Iterator, Sequence

from package_skills import INVENTORY_NAME, compare
from repository_paths import canonical_repository_path
from validate_skills import ValidationError, validate_repository


COMMAND_TIMEOUT_SECONDS = 1800
PATH_TIMEOUT_SECONDS = 30
PROFILE = "portable"


@dataclass(frozen=True)
class SourceState:
    """Git-visible source identity held constant across both platforms."""

    git_commit: str
    working_tree_dirty: bool
    fingerprint: str


@dataclass(frozen=True)
class PlatformPaths:
    """Paths expressed in the syntax understood by one platform."""

    repo_root: str
    core_repo: str
    candidate: str
    evidence: str


@dataclass(frozen=True)
class Step:
    """One existing repository command reused by the preflight."""

    label: str
    argv: tuple[str, ...]


CommandWrapper = Callable[[Sequence[str]], Sequence[str]]


def _git_output(repo_root: Path, *args: str) -> bytes:
    result = subprocess.run(
        ["git", "-c", f"safe.directory={repo_root}", *args],
        cwd=repo_root,
        check=True,
        capture_output=True,
        timeout=PATH_TIMEOUT_SECONDS,
    )
    return result.stdout


def _decode_git_paths(payload: bytes) -> list[str]:
    try:
        paths = [item.decode("utf-8") for item in payload.split(b"\0") if item]
    except UnicodeDecodeError as exc:
        raise ValidationError("Git returned a repository path that is not UTF-8") from exc
    return sorted(paths)


def source_state(repo_root: Path) -> SourceState:
    """Fingerprint tracked, staged, and non-ignored untracked source state."""
    repo_root = repo_root.resolve()
    validate_repository(repo_root)
    head = _git_output(repo_root, "rev-parse", "HEAD").decode("ascii").strip()
    if len(head) != 40 or any(character not in "0123456789abcdef" for character in head):
        raise ValidationError("preflight source HEAD is not a full lowercase SHA-1")
    status = _git_output(
        repo_root, "status", "--porcelain=v1", "-z", "--untracked-files=all"
    )
    index = _git_output(repo_root, "ls-files", "--stage", "-z")
    names = _decode_git_paths(
        _git_output(
            repo_root,
            "-c",
            "core.quotepath=false",
            "ls-files",
            "--cached",
            "--others",
            "--exclude-standard",
            "-z",
        )
    )

    digest = hashlib.sha256()
    for label, payload in ((b"HEAD", head.encode("ascii")), (b"STATUS", status), (b"INDEX", index)):
        digest.update(label + b"\0" + payload + b"\0")
    for relative in names:
        pure = PurePosixPath(relative)
        path = canonical_repository_path(
            repo_root,
            Path(*pure.parts),
            error_factory=ValidationError,
        )
        digest.update(b"PATH\0" + relative.encode("utf-8") + b"\0")
        if not path.exists():
            digest.update(b"MISSING\0")
        elif not path.is_file():
            raise ValidationError(f"preflight source path must be a regular file: {relative}")
        else:
            digest.update(hashlib.sha256(path.read_bytes()).digest())
    return SourceState(head, bool(status), digest.hexdigest())


def _join(root: str, relative: str) -> str:
    return f"{root.rstrip('/')}/{relative}"


def platform_steps(python: str, paths: PlatformPaths) -> tuple[Step, ...]:
    """Build the shared command manifest for native or WSL execution."""
    validate = _join(paths.repo_root, "scripts/validate_skills.py")
    package = _join(paths.repo_root, "scripts/package_skills.py")
    baseline = _join(paths.repo_root, "scripts/check_core_baseline.py")
    return (
        Step(
            "validate skills",
            (python, validate, "--repo-root", paths.repo_root),
        ),
        Step(
            "run tests",
            (
                python,
                "-m",
                "unittest",
                "discover",
                "-s",
                _join(paths.repo_root, "tests"),
                "-t",
                paths.repo_root,
                "-v",
            ),
        ),
        Step(
            "build portable candidate",
            (
                python,
                package,
                "build",
                "--repo-root",
                paths.repo_root,
                "--profile",
                PROFILE,
                "--output",
                paths.candidate,
            ),
        ),
        Step(
            "check portable candidate",
            (
                python,
                package,
                "check",
                "--repo-root",
                paths.repo_root,
                "--profile",
                PROFILE,
                "--output",
                paths.candidate,
            ),
        ),
        Step(
            "validate exact Core documentation",
            (
                python,
                validate,
                "--repo-root",
                paths.repo_root,
                "--core-repo",
                paths.core_repo,
            ),
        ),
        Step(
            "verify exact Core consumer",
            (
                python,
                baseline,
                "--repo-root",
                paths.repo_root,
                "verify",
                "--core-repo",
                paths.core_repo,
                "--evidence-root",
                paths.evidence,
            ),
        ),
    )


def _identity(command: Sequence[str]) -> Sequence[str]:
    return command


def wsl_command(
    distribution: str,
    command: Sequence[str],
    *,
    repo_root: str,
    core_repo: str,
) -> tuple[str, ...]:
    """Wrap one argv without invoking a shell or changing WSL configuration."""
    git_environment = (
        "env",
        "GIT_CONFIG_COUNT=2",
        "GIT_CONFIG_KEY_0=safe.directory",
        f"GIT_CONFIG_VALUE_0={repo_root}",
        "GIT_CONFIG_KEY_1=safe.directory",
        f"GIT_CONFIG_VALUE_1={core_repo}",
    )
    return (
        "wsl.exe",
        "--distribution",
        distribution,
        "--exec",
        *git_environment,
        *command,
    )


def _run_command(command: Sequence[str]) -> None:
    subprocess.run(list(command), check=True, timeout=COMMAND_TIMEOUT_SECONDS)


def _capture_command(command: Sequence[str], *, label: str) -> str:
    result = subprocess.run(
        list(command),
        check=False,
        capture_output=True,
        text=True,
        timeout=PATH_TIMEOUT_SECONDS,
    )
    if result.returncode:
        detail = (result.stderr or result.stdout).strip()
        suffix = f": {detail}" if detail else ""
        raise ValidationError(f"{label} failed with exit {result.returncode}{suffix}")
    value = (result.stdout or result.stderr).strip()
    if not value:
        raise ValidationError(f"{label} returned no output")
    return value


def wsl_path(path: Path, distribution: str) -> str:
    converted = _capture_command(
        (
            "wsl.exe",
            "--distribution",
            distribution,
            "--exec",
            "wslpath",
            "-a",
            "-u",
            str(path.resolve()),
        ),
        label=f"WSL path conversion for {path}",
    )
    if not converted.startswith("/") or "\n" in converted or "\r" in converted:
        raise ValidationError(f"WSL returned an invalid absolute path for {path}")
    return converted


def remove_wsl_evidence(
    distribution: str,
    evidence: str,
    workspace: str,
) -> None:
    """Remove only the internally named WSL evidence child from owned workspace."""
    evidence_path = PurePosixPath(evidence)
    workspace_path = PurePosixPath(workspace)
    if evidence_path.parent != workspace_path or evidence_path.name != "evidence-linux":
        raise ValidationError("refusing to remove non-owned WSL evidence path")
    _run_command(
        (
            "wsl.exe",
            "--distribution",
            distribution,
            "--exec",
            "rm",
            "-rf",
            "--",
            evidence,
        )
    )


def _require_unchanged(repo_root: Path, expected: SourceState, label: str) -> None:
    actual = source_state(repo_root)
    if actual != expected:
        raise ValidationError(f"source or index changed during preflight after {label}")


def run_platform(
    name: str,
    steps: Sequence[Step],
    wrapper: CommandWrapper,
    *,
    repo_root: Path,
    expected_state: SourceState,
) -> None:
    for step in steps:
        print(f"[{name}] {step.label}", file=sys.stderr)
        _run_command(wrapper(step.argv))
        _require_unchanged(repo_root, expected_state, f"{name} {step.label}")


def _candidate_identity(candidate: Path, expected: SourceState, name: str) -> None:
    inventory_path = candidate / INVENTORY_NAME
    try:
        inventory = json.loads(inventory_path.read_text(encoding="utf-8"))
        source = inventory["source"]
        commit = source["git_commit"]
        dirty = source["working_tree_dirty"]
    except (OSError, json.JSONDecodeError, KeyError, TypeError) as exc:
        raise ValidationError(f"{name} candidate has an invalid release inventory") from exc
    if commit != expected.git_commit or dirty is not expected.working_tree_dirty:
        raise ValidationError(
            f"{name} candidate source identity does not match the preflight input"
        )


def _validate_output_root(output_root: Path, repo_root: Path, core_repo: Path) -> Path:
    output_root = output_root.resolve()
    for boundary, label in ((repo_root, "source"), (core_repo, "Core")):
        boundary = boundary.resolve()
        if (
            output_root == boundary
            or output_root in boundary.parents
            or boundary in output_root.parents
        ):
            raise ValidationError(f"preflight output must be outside the {label} repository")
    if output_root.exists() or output_root.is_symlink():
        raise ValidationError(f"preflight output already exists: {output_root}")
    if not output_root.parent.is_dir():
        raise ValidationError(f"preflight output parent does not exist: {output_root.parent}")
    output_root.mkdir()
    return output_root


def clone_core_baseline(source: Path, destination: Path, commit: str) -> None:
    """Create an isolated local clone without copying ignored build residue."""
    _run_command(
        (
            "git",
            "-c",
            f"safe.directory={source}",
            "clone",
            "--quiet",
            "--no-hardlinks",
            "--no-checkout",
            str(source),
            str(destination),
        )
    )
    _run_command(
        (
            "git",
            "-c",
            f"safe.directory={destination}",
            "-C",
            str(destination),
            "checkout",
            "--quiet",
            "--detach",
            commit,
        )
    )


@contextmanager
def output_workspace(
    output_root: Path | None, repo_root: Path, core_repo: Path
) -> Iterator[Path]:
    if output_root is not None:
        yield _validate_output_root(output_root, repo_root, core_repo)
        return
    with tempfile.TemporaryDirectory(prefix="rpacore-skills-preflight-") as directory:
        yield Path(directory)


def run_preflight(
    repo_root: Path,
    core_repo: Path,
    *,
    windows_python: Path,
    linux_python: str,
    wsl_distribution: str,
    output_root: Path | None = None,
) -> dict[str, object]:
    repo_root = repo_root.resolve()
    core_repo = core_repo.resolve()
    windows_python = windows_python.resolve()
    if not windows_python.is_file():
        raise ValidationError(f"Windows Python does not exist: {windows_python}")
    if not linux_python or not wsl_distribution:
        raise ValidationError("Linux Python and WSL distribution must be non-empty")
    manifest = validate_repository(repo_root, core_repo=core_repo)
    expected_state = source_state(repo_root)

    with output_workspace(output_root, repo_root, core_repo) as workspace:
        core_commit = manifest["core"]["commit"]
        windows_core = workspace / "core-windows"
        linux_core = workspace / "core-linux"
        clone_core_baseline(core_repo, windows_core, core_commit)
        clone_core_baseline(core_repo, linux_core, core_commit)
        _require_unchanged(repo_root, expected_state, "Core baseline cloning")

        windows_paths = PlatformPaths(
            repo_root.as_posix(),
            windows_core.as_posix(),
            (workspace / "windows").as_posix(),
            (workspace / "evidence-windows").as_posix(),
        )
        linux_paths = PlatformPaths(
            wsl_path(repo_root, wsl_distribution),
            wsl_path(linux_core, wsl_distribution),
            wsl_path(workspace / "linux", wsl_distribution),
            wsl_path(workspace / "evidence-linux", wsl_distribution),
        )
        wrap_linux = lambda command: wsl_command(
            wsl_distribution,
            command,
            repo_root=linux_paths.repo_root,
            core_repo=linux_paths.core_repo,
        )

        windows_version = _capture_command(
            (str(windows_python), "--version"), label="Windows Python"
        )
        linux_version = _capture_command(
            wrap_linux((linux_python, "--version")), label="WSL Linux Python"
        )
        _require_unchanged(repo_root, expected_state, "Python prerequisite checks")

        run_platform(
            "Windows",
            platform_steps(str(windows_python), windows_paths),
            _identity,
            repo_root=repo_root,
            expected_state=expected_state,
        )
        try:
            run_platform(
                "WSL/Linux",
                platform_steps(linux_python, linux_paths),
                wrap_linux,
                repo_root=repo_root,
                expected_state=expected_state,
            )
        finally:
            if output_root is None:
                remove_wsl_evidence(
                    wsl_distribution,
                    linux_paths.evidence,
                    wsl_path(workspace, wsl_distribution),
                )

        windows_candidate = workspace / "windows"
        linux_candidate = workspace / "linux"
        _candidate_identity(windows_candidate, expected_state, "Windows")
        _candidate_identity(linux_candidate, expected_state, "WSL/Linux")
        asset_hashes = compare(repo_root, windows_candidate, linux_candidate)
        _require_unchanged(repo_root, expected_state, "asset comparison")

        return {
            "source": {
                "git_commit": expected_state.git_commit,
                "working_tree_dirty": expected_state.working_tree_dirty,
                "fingerprint": expected_state.fingerprint,
            },
            "platforms": {
                "windows": {"python": windows_version},
                "linux": {
                    "python": linux_version,
                    "wsl_distribution": wsl_distribution,
                },
            },
            "assets": asset_hashes,
        }


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, required=True)
    parser.add_argument("--core-repo", type=Path, required=True)
    parser.add_argument(
        "--windows-python",
        type=Path,
        default=Path(sys.executable),
        help="Native Windows Python executable (default: current interpreter)",
    )
    parser.add_argument("--linux-python", default="python3")
    parser.add_argument("--wsl-distribution", required=True)
    parser.add_argument(
        "--output-root",
        type=Path,
        help="New external directory to retain candidates and baseline evidence",
    )
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        result = run_preflight(
            args.repo_root,
            args.core_repo,
            windows_python=args.windows_python,
            linux_python=args.linux_python,
            wsl_distribution=args.wsl_distribution,
            output_root=args.output_root,
        )
    except ValidationError as exc:
        print(f"Local CI preflight failed: {exc}", file=sys.stderr)
        return 1
    except subprocess.TimeoutExpired as exc:
        print(f"Local CI preflight timed out after {exc.timeout}s: {exc.cmd}", file=sys.stderr)
        return 1
    except subprocess.CalledProcessError as exc:
        print(
            f"Local CI preflight command failed (exit {exc.returncode}): {exc.cmd}",
            file=sys.stderr,
        )
        return 1
    except OSError as exc:
        print(f"Local CI preflight I/O failed: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

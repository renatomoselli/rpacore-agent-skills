from __future__ import annotations

from pathlib import Path
import shutil
import subprocess


REPO_ROOT = Path(__file__).resolve().parents[1]


def make_git_source(destination: Path) -> Path:
    shutil.copytree(
        REPO_ROOT,
        destination,
        ignore=shutil.ignore_patterns(
            ".git", "validation-artifacts", "__pycache__", "*.pyc"
        ),
    )
    commands = (
        ("git", "init", "--quiet"),
        ("git", "config", "user.email", "distribution@example.invalid"),
        ("git", "config", "user.name", "Distribution Test"),
        ("git", "add", "."),
        ("git", "commit", "--quiet", "-m", "fixture"),
    )
    for command in commands:
        subprocess.run(
            command,
            cwd=destination,
            check=True,
            capture_output=True,
            text=True,
        )
    return destination

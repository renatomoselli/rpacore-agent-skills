"""Shared repository containment and symlink policy."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path


class RepositoryPathError(ValueError):
    """A path cannot be used within the selected repository boundary."""


ErrorFactory = Callable[[str], Exception]


def _resolve(path: Path, error_factory: ErrorFactory) -> Path:
    try:
        return path.resolve()
    except (OSError, RuntimeError) as exc:
        raise error_factory(f"could not resolve repository path: {path}") from exc


def canonical_repository_path(
    repo_root: Path,
    relative_path: Path,
    *,
    error_factory: ErrorFactory = RepositoryPathError,
) -> Path:
    """Resolve one repository-relative path without traversing symlinks."""
    if relative_path.is_absolute() or ".." in relative_path.parts:
        raise error_factory(f"unsafe repository-relative path: {relative_path}")
    repo_root = _resolve(repo_root, error_factory)
    candidate = repo_root / relative_path
    target = _resolve(candidate, error_factory)
    try:
        target.relative_to(repo_root)
    except ValueError as exc:
        raise error_factory(f"path escapes repository: {relative_path}") from exc

    current = candidate
    while current != repo_root:
        if current.is_symlink():
            raise error_factory(f"path must not use symlinks: {relative_path}")
        current = current.parent
    return target

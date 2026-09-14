"""Best-effort rollback for caught generated-file replacement failures.

This process-local helper does not provide crash durability or filesystem-wide
atomicity; an abrupt process or machine failure can leave applied replacements.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
import os
from pathlib import Path
import stat
import tempfile

from repository_paths import canonical_repository_path


TEMP_PREFIX = ".skills-write-"


class FileTransactionError(OSError):
    """A replacement was rejected or caught-failure rollback was incomplete."""


def replace_files(
    repo_root: Path, pending: Mapping[Path, bytes], validate: Callable[[], None]
) -> None:
    """Replace repository-relative files and restore them after a caught failure."""
    repo_root = canonical_repository_path(
        repo_root, Path("."), error_factory=FileTransactionError
    )
    changed: dict[Path, tuple[bytes | None, int | None, bytes]] = {}
    for relative_path, payload in pending.items():
        path = canonical_repository_path(
            repo_root, relative_path, error_factory=FileTransactionError
        )
        original = path.read_bytes() if path.exists() else None
        original_mode = stat.S_IMODE(path.stat().st_mode) if original is not None else None
        if original != payload:
            changed[path] = (original, original_mode, payload)
    if not changed:
        validate()
        return

    staged: dict[Path, Path] = {}
    applied: list[Path] = []
    created_directories: list[Path] = []
    try:
        for path, (_, original_mode, payload) in changed.items():
            with tempfile.NamedTemporaryFile(
                mode="wb", dir=repo_root, prefix=TEMP_PREFIX, suffix=".tmp", delete=False
            ) as stream:
                temporary = Path(stream.name)
                stream.write(payload)
            os.chmod(temporary, original_mode if original_mode is not None else 0o644)
            staged[path] = temporary

        for path in changed:
            missing: list[Path] = []
            parent = path.parent
            while parent != repo_root and not parent.exists():
                missing.append(parent)
                parent = parent.parent
            path.parent.mkdir(parents=True, exist_ok=True)
            created_directories.extend(reversed(missing))
            staged[path].replace(path)
            applied.append(path)
        validate()
    except BaseException as exc:
        rollback_errors: list[str] = []
        for path in reversed(applied):
            original, original_mode, _ = changed[path]
            try:
                if original is None:
                    path.unlink(missing_ok=True)
                else:
                    path.write_bytes(original)
                    os.chmod(path, original_mode)
            except OSError as rollback_exc:
                rollback_errors.append(f"{path}: {rollback_exc}")
        for directory in reversed(created_directories):
            try:
                directory.rmdir()
            except OSError:
                pass
        if rollback_errors:
            raise FileTransactionError(
                f"generated-file update failed and rollback was incomplete: {rollback_errors}"
            ) from exc
        raise
    finally:
        for temporary in staged.values():
            temporary.unlink(missing_ok=True)

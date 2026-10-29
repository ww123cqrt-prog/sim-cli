"""Safe file access helpers for sim-server's transfer workspace."""
from __future__ import annotations

import os
import re
from pathlib import Path


class WorkspacePathError(ValueError):
    """Raised when a requested workspace path is unsafe or invalid."""


_WINDOWS_DRIVE_RE = re.compile(r"^[a-zA-Z]:[\\/]")
DEFAULT_MAX_UPLOAD_BYTES = 512 * 1024 * 1024


def max_upload_bytes() -> int:
    raw = os.environ.get("SIM_WORKSPACE_MAX_UPLOAD_BYTES")
    if raw is None:
        return DEFAULT_MAX_UPLOAD_BYTES
    try:
        value = int(raw)
    except ValueError:
        return DEFAULT_MAX_UPLOAD_BYTES
    return max(value, 0)


def workspace_root() -> Path:
    """Return the server-local workspace root, creating it if needed."""
    direct_root = os.environ.get("SIM_WORKSPACE_ROOT")
    if direct_root:
        root = Path(direct_root)
        root.mkdir(parents=True, exist_ok=True)
        return root

    sim_dir = Path(os.environ.get("SIM_DIR") or (Path.cwd() / ".sim"))
    root = sim_dir / "workspace"
    root.mkdir(parents=True, exist_ok=True)
    return root


def _ensure_inside(root: Path, candidate: Path) -> Path:
    root_resolved = root.resolve()
    resolved = candidate.resolve(strict=False)
    if resolved == root_resolved or root_resolved not in resolved.parents:
        raise WorkspacePathError("path escapes workspace")
    return resolved


def resolve_workspace_path(root: Path, remote_path: str) -> Path:
    """Resolve a user-supplied relative path under ``root``.

    The returned path is guaranteed to stay inside ``root`` after resolving
    existing symlinks in parent directories.
    """
    if not remote_path or remote_path == ".":
        raise WorkspacePathError("path must name a file or directory below workspace")
    if "\x00" in remote_path:
        raise WorkspacePathError("path contains NUL byte")
    if _WINDOWS_DRIVE_RE.match(remote_path):
        raise WorkspacePathError("absolute Windows paths are not allowed")

    path = Path(remote_path)
    if path.is_absolute():
        raise WorkspacePathError("absolute paths are not allowed")

    root.mkdir(parents=True, exist_ok=True)
    candidate = root / path
    return _ensure_inside(root, candidate)


def list_workspace_files(root: Path, remote_path: str = ".") -> list[dict]:
    """List files below a workspace directory in stable relative-path order."""
    root.mkdir(parents=True, exist_ok=True)
    if remote_path == ".":
        start = root
    else:
        start = resolve_workspace_path(root, remote_path)
    if not start.exists():
        raise WorkspacePathError("path does not exist")
    if not start.is_dir():
        raise WorkspacePathError("path is not a directory")

    rows: list[dict] = []
    for path in sorted(p for p in start.rglob("*") if p.is_file()):
        rows.append({
            "path": path.relative_to(root).as_posix(),
            "kind": "file",
            "size": path.stat().st_size,
        })
    return rows

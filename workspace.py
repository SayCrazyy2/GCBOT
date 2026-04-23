"""Workspace helpers — path-safe file operations confined to WORKSPACE_DIR.

All public functions resolve paths relative to the workspace root and raise
``WorkspaceError`` if the resolved path would escape the workspace.
"""

from __future__ import annotations

import os
import shutil
from pathlib import Path

import config


class WorkspaceError(Exception):
    """Raised when an operation is rejected for safety reasons."""


def _root() -> Path:
    return Path(config.WORKSPACE_DIR).resolve()


def ensure_workspace() -> None:
    """Create the workspace root (and any parents) if it does not exist."""
    _root().mkdir(parents=True, exist_ok=True)


def safe_path(rel: str, base: str | None = None) -> Path:
    """Resolve *rel* relative to *base* (default: workspace root).

    Raises ``WorkspaceError`` if the resolved path is outside the workspace.
    """
    root = _root()
    base_path = Path(base).resolve() if base else root
    # Ensure the base itself is inside the workspace.
    try:
        base_path.relative_to(root)
    except ValueError:
        raise WorkspaceError(f"Base directory '{base_path}' is outside the workspace.")

    resolved = (base_path / rel).resolve()
    try:
        resolved.relative_to(root)
    except ValueError:
        raise WorkspaceError(
            f"Path '{rel}' resolves outside the workspace. Only paths inside "
            f"'{root}' are allowed."
        )
    return resolved


def list_dir(rel: str = ".", base: str | None = None) -> str:
    """Return a formatted directory listing for *rel*."""
    path = safe_path(rel, base)
    if not path.exists():
        raise WorkspaceError(f"'{rel}' does not exist.")
    if not path.is_dir():
        raise WorkspaceError(f"'{rel}' is not a directory.")

    entries = sorted(path.iterdir(), key=lambda p: (not p.is_dir(), p.name.lower()))
    if not entries:
        return "(empty directory)"

    lines: list[str] = []
    for entry in entries:
        if entry.is_symlink():
            lines.append(f"🔗 {entry.name}")
        elif entry.is_dir():
            lines.append(f"📁 {entry.name}/")
        else:
            size = entry.stat().st_size
            lines.append(f"📄 {entry.name}  ({_human_size(size)})")
    return "\n".join(lines)


def read_file(rel: str, base: str | None = None) -> str:
    """Return the text content of *rel*."""
    path = safe_path(rel, base)
    if not path.exists():
        raise WorkspaceError(f"'{rel}' does not exist.")
    if not path.is_file():
        raise WorkspaceError(f"'{rel}' is not a file.")
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except Exception as exc:
        raise WorkspaceError(f"Cannot read '{rel}': {exc}") from exc


def write_file(rel: str, content: str, base: str | None = None) -> Path:
    """Write *content* to *rel*, creating parent directories as needed."""
    path = safe_path(rel, base)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return path


def delete_path(rel: str, base: str | None = None) -> None:
    """Delete file or directory tree at *rel*."""
    path = safe_path(rel, base)
    if not path.exists():
        raise WorkspaceError(f"'{rel}' does not exist.")
    if path.is_dir():
        shutil.rmtree(path)
    else:
        path.unlink()


def make_dir(rel: str, base: str | None = None) -> Path:
    """Create directory *rel* (and parents) if it does not exist."""
    path = safe_path(rel, base)
    path.mkdir(parents=True, exist_ok=True)
    return path


def workspace_info() -> str:
    """Return a summary of the workspace (path, size, top-level items)."""
    root = _root()
    ensure_workspace()
    total = sum(
        f.stat().st_size for f in root.rglob("*") if f.is_file()
    )
    top = sorted(root.iterdir(), key=lambda p: (not p.is_dir(), p.name.lower()))
    items = "\n".join(
        f"  📁 {p.name}/" if p.is_dir() else f"  📄 {p.name}" for p in top[:20]
    )
    if len(top) > 20:
        items += f"\n  … and {len(top) - 20} more"
    return (
        f"📂 Workspace: `{root}`\n"
        f"💾 Total size: {_human_size(total)}\n\n"
        f"{items or '(empty)'}"
    )


def rel_display(abs_path: str) -> str:
    """Return path relative to workspace root for display purposes."""
    try:
        return str(Path(abs_path).resolve().relative_to(_root()))
    except ValueError:
        return abs_path


# ── internal ──────────────────────────────────────────────────────────────────

def _human_size(n: int) -> str:
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024:
            return f"{n:.0f} {unit}"
        n /= 1024  # type: ignore[assignment]
    return f"{n:.1f} TB"

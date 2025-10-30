"""Path utilities for finding gryt repo root and config files."""
from __future__ import annotations

from pathlib import Path
from typing import Optional


GRYT_DIRNAME = ".gryt"
GIT_DIRNAME = ".git"


def find_repo_root(start_path: Optional[Path] = None) -> Optional[Path]:
    """Find the gryt repository root by walking up the directory tree.

    Searches for a .gryt folder with a .git folder at the same level to ensure
    we're in a valid git repository and haven't wandered outside the repo.

    Args:
        start_path: Starting directory (defaults to current working directory)

    Returns:
        Path to repo root (directory containing .gryt), or None if not found

    Example:
        >>> # From REPO/src/foo/bar, finds REPO
        >>> root = find_repo_root()
        >>> print(root)
        /path/to/REPO
    """
    if start_path is None:
        start_path = Path.cwd()

    current = start_path.resolve()

    # Walk up the directory tree
    for parent in [current] + list(current.parents):
        gryt_dir = parent / GRYT_DIRNAME
        git_dir = parent / GIT_DIRNAME

        # Found .gryt folder
        if gryt_dir.exists() and gryt_dir.is_dir():
            # Safety check: ensure .git exists at same level
            if git_dir.exists() and git_dir.is_dir():
                return parent

            # Found .gryt but no .git - this might be a nested .gryt folder
            # Continue searching up, but warn
            # (We could log a warning here if we had logging configured)
            continue

    return None


def get_repo_gryt_dir(start_path: Optional[Path] = None) -> Optional[Path]:
    """Get the .gryt directory for the current repo.

    Args:
        start_path: Starting directory (defaults to current working directory)

    Returns:
        Path to .gryt directory, or None if not in a gryt repo
    """
    root = find_repo_root(start_path)
    if root:
        return root / GRYT_DIRNAME
    return None


def get_repo_config_path(start_path: Optional[Path] = None) -> Optional[Path]:
    """Get the local config file path for the current repo.

    Args:
        start_path: Starting directory (defaults to current working directory)

    Returns:
        Path to .gryt/config file, or None if not in a gryt repo
    """
    gryt_dir = get_repo_gryt_dir(start_path)
    if gryt_dir:
        return gryt_dir / "config"
    return None


def get_repo_db_path(start_path: Optional[Path] = None) -> Optional[Path]:
    """Get the database path for the current repo.

    Args:
        start_path: Starting directory (defaults to current working directory)

    Returns:
        Path to .gryt/gryt.db file, or None if not in a gryt repo
    """
    gryt_dir = get_repo_gryt_dir(start_path)
    if gryt_dir:
        return gryt_dir / "gryt.db"
    return None


def ensure_in_repo() -> Path:
    """Ensure we're in a gryt repository and return the root.

    Raises:
        RuntimeError: If not in a gryt repository

    Returns:
        Path to repo root
    """
    root = find_repo_root()
    if not root:
        raise RuntimeError(
            "Not in a gryt repository. Run 'gryt init' to initialize, "
            "or navigate to a directory within a gryt repository."
        )
    return root

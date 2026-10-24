"""Tiny git helpers (branch detection for the status bar)."""

from __future__ import annotations

from pathlib import Path


def _git_dir(root: Path) -> Path | None:
    for parent in (root, *root.parents):
        candidate = parent / ".git"
        if candidate.is_dir():
            return candidate
        if candidate.is_file():
            # Worktree or submodule: ".git" contains "gitdir: <path>".
            try:
                content = candidate.read_text(encoding="utf-8").strip()
            except OSError:
                return None
            if content.startswith("gitdir:"):
                return (parent / content.split(":", 1)[1].strip()).resolve()
    return None


def git_branch(root: str | Path) -> str | None:
    """Return the current branch name (or short SHA) for ``root``."""
    git_dir = _git_dir(Path(root))
    if git_dir is None:
        return None
    try:
        head = (git_dir / "HEAD").read_text(encoding="utf-8").strip()
    except OSError:
        return None
    if head.startswith("ref:"):
        ref = head.split(":", 1)[1].strip()
        return ref.rsplit("/", 1)[-1] or None
    return head[:8] if head else None


def is_git_repo(root: str | Path) -> bool:
    return _git_dir(Path(root)) is not None

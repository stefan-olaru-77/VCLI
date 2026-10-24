"""Lazy file tree used by the explorer sidebar and quick open."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

IGNORED_DIRS = {
    ".git",
    ".hg",
    ".svn",
    ".idea",
    ".vscode",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    ".tox",
    ".venv",
    "venv",
    "env",
    "node_modules",
    "__pycache__",
    "dist",
    "build",
    "target",
    ".next",
    ".cache",
    "coverage",
    ".eggs",
    "site-packages",
}

IGNORED_SUFFIXES = {
    ".pyc",
    ".pyo",
    ".swp",
    ".swo",
    ".tmp",
    ".o",
    ".obj",
    ".class",
    ".so",
    ".dylib",
}

MAX_QUICK_OPEN_FILES = 50_000


@dataclass
class Node:
    path: Path
    depth: int
    is_dir: bool
    expanded: bool = False
    children: list[Node] | None = field(default=None, repr=False)

    @property
    def name(self) -> str:
        return self.path.name or str(self.path)

    @property
    def key(self) -> str:
        return str(self.path)


class Workspace:
    """A single-folder workspace with lazily expanded directories."""

    def __init__(self, root: str | Path, show_hidden: bool = False) -> None:
        self.root = Path(root).expanduser().resolve()
        self.show_hidden = show_hidden
        self.selected = 0
        self._expanded: set[str] = set()
        self._flat: list[Node] = []
        self._flat_dirty = True
        self.nodes: list[Node] = []
        self.reload()

    # ------------------------------------------------------------- scanning
    def _ignored_dir(self, name: str) -> bool:
        return name in IGNORED_DIRS

    def _visible(self, name: str) -> bool:
        if name in IGNORED_DIRS:
            return False
        if not self.show_hidden and name.startswith("."):
            return False
        return True

    def _scan(self, directory: Path, depth: int) -> list[Node]:
        try:
            with os.scandir(directory) as iterator:
                entries = list(iterator)
        except OSError:
            return []
        nodes: list[Node] = []
        for entry in entries:
            name = entry.name
            if not self._visible(name):
                continue
            try:
                is_dir = entry.is_dir(follow_symlinks=False)
            except OSError:
                continue
            if not is_dir and Path(name).suffix.lower() in IGNORED_SUFFIXES:
                continue
            node = Node(path=Path(entry.path), depth=depth, is_dir=is_dir)
            if is_dir and node.key in self._expanded:
                node.expanded = True
                node.children = self._scan(node.path, depth + 1)
            nodes.append(node)
        nodes.sort(key=lambda n: (not n.is_dir, n.name.lower()))
        return nodes

    def reload(self) -> None:
        self.nodes = self._scan(self.root, 0)
        self._flat_dirty = True
        self.selected = max(0, min(self.selected, len(self.flatten()) - 1))

    def refresh_node(self, node: Node) -> None:
        if not node.is_dir:
            return
        if node.key in self._expanded:
            node.children = self._scan(node.path, node.depth + 1)
        self._flat_dirty = True

    # ------------------------------------------------------------- navigation
    def flatten(self) -> list[Node]:
        if not self._flat_dirty:
            return self._flat
        flat: list[Node] = []

        def walk(nodes: list[Node]) -> None:
            for node in nodes:
                flat.append(node)
                if node.is_dir and node.expanded and node.children:
                    walk(node.children)

        walk(self.nodes)
        self._flat = flat
        self._flat_dirty = False
        return flat

    def toggle(self, node: Node | None = None) -> None:
        node = node or self.selected_node()
        if node is None or not node.is_dir:
            return
        if node.expanded:
            node.expanded = False
            self._expanded.discard(node.key)
        else:
            node.expanded = True
            self._expanded.add(node.key)
            node.children = self._scan(node.path, node.depth + 1)
        self._flat_dirty = True
        self._clamp_selection()

    def expand(self, node: Node | None = None) -> None:
        node = node or self.selected_node()
        if node is None or not node.is_dir or node.expanded:
            return
        self.toggle(node)

    def collapse(self, node: Node | None = None) -> None:
        node = node or self.selected_node()
        if node is None or not node.is_dir or not node.expanded:
            return
        self.toggle(node)

    def _clamp_selection(self) -> None:
        count = len(self.flatten())
        self.selected = max(0, min(self.selected, count - 1))

    def select(self, index: int) -> Node | None:
        flat = self.flatten()
        if not flat:
            self.selected = 0
            return None
        self.selected = max(0, min(index, len(flat) - 1))
        return flat[self.selected]

    def move_selection(self, delta: int) -> Node | None:
        return self.select(self.selected + delta)

    def selected_node(self) -> Node | None:
        flat = self.flatten()
        if not flat:
            return None
        self.selected = max(0, min(self.selected, len(flat) - 1))
        return flat[self.selected]

    def parent_of_selected(self) -> Node | None:
        node = self.selected_node()
        if node is None:
            return None
        flat = self.flatten()
        for candidate in reversed(flat[: self.selected]):
            if candidate.is_dir and node.path.parent == candidate.path:
                return candidate
        return None

    # ---------------------------------------------------------------- helpers
    def relative(self, path: str | Path) -> str:
        try:
            return str(Path(path).resolve().relative_to(self.root))
        except (ValueError, OSError):
            return str(path)

    def reveal(self, path: str | Path) -> Node | None:
        """Expand all parent directories of ``path`` and select it."""
        target = Path(path).expanduser()
        try:
            target = target.resolve()
            target.relative_to(self.root)
        except (ValueError, OSError):
            return None
        parts = target.relative_to(self.root).parts
        nodes = self.nodes
        current: Node | None = None
        for part in parts:
            match = next((n for n in nodes if n.path.name == part), None)
            if match is None:
                self.reload()
                return None
            current = match
            if part != parts[-1]:
                if match.is_dir and not match.expanded:
                    self._expanded.add(match.key)
                    match.expanded = True
                    match.children = self._scan(match.path, match.depth + 1)
                    self._flat_dirty = True
                nodes = match.children or []
        if current is not None:
            flat = self.flatten()
            try:
                self.selected = flat.index(current)
            except ValueError:
                pass
        return current

    def visible_files(
        self, limit: int = MAX_QUICK_OPEN_FILES
    ) -> list[Path]:
        """Recursively list files for quick open, honouring ignores."""
        result: list[Path] = []
        stack = [self.root]
        while stack and len(result) < limit:
            directory = stack.pop()
            try:
                with os.scandir(directory) as iterator:
                    entries = list(iterator)
            except OSError:
                continue
            for entry in entries:
                if len(result) >= limit:
                    break
                name = entry.name
                if not self._visible(name):
                    continue
                try:
                    if entry.is_dir(follow_symlinks=False):
                        stack.append(Path(entry.path))
                    elif entry.is_file(follow_symlinks=False):
                        if Path(name).suffix.lower() in IGNORED_SUFFIXES:
                            continue
                        result.append(Path(entry.path))
                except OSError:
                    continue
        result.sort(key=lambda p: self.relative(p).lower())
        return result

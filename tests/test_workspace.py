"""Tests for the lazy explorer tree and quick-open scan."""

from __future__ import annotations

from pathlib import Path

from vcli.workspace import Workspace


def test_scan_sorts_dirs_first_and_hides_ignored(workspace: Path):
    ws = Workspace(workspace)
    names = [node.name for node in ws.nodes]
    assert names == ["src", "README.md"]
    assert ws.nodes[0].is_dir
    assert ws.nodes[0].expanded is False


def test_show_hidden(workspace: Path):
    ws = Workspace(workspace, show_hidden=True)
    names = [node.name for node in ws.nodes]
    assert ".hidden" in names
    assert ".git" not in names


def test_toggle_expand_and_flatten(workspace: Path):
    ws = Workspace(workspace)
    src = ws.nodes[0]
    ws.toggle(src)
    assert src.expanded is True
    flat = ws.flatten()
    assert [node.name for node in flat] == ["src", "main.py", "README.md"]

    ws.toggle(src)
    assert [node.name for node in ws.flatten()] == ["src", "README.md"]

    # Expanded directories survive a reload.
    ws.toggle(src)
    ws.reload()
    assert ws.flatten()[1].name == "main.py"


def test_selection_and_navigation(workspace: Path):
    ws = Workspace(workspace)
    assert ws.selected_node().name == "src"
    ws.move_selection(1)
    assert ws.selected_node().name == "README.md"
    ws.move_selection(10)
    assert ws.selected_node().name == "README.md"
    ws.move_selection(-10)
    assert ws.selected_node().name == "src"
    assert ws.parent_of_selected() is None


def test_reveal_expands_parents(workspace: Path):
    ws = Workspace(workspace)
    target = workspace / "src" / "main.py"
    node = ws.reveal(target)
    assert node is not None
    assert node.name == "main.py"
    assert ws.selected_node().name == "main.py"
    assert ws.nodes[0].expanded is True

    assert ws.reveal(Path("/etc/hosts")) is None


def test_visible_files(workspace: Path):
    ws = Workspace(workspace)
    files = [ws.relative(path) for path in ws.visible_files()]
    assert files == ["README.md", "src/main.py"]
    assert ws.relative(workspace / "src" / "main.py") == "src/main.py"


def test_visible_files_limit(workspace: Path):
    ws = Workspace(workspace)
    assert len(ws.visible_files(limit=1)) == 1

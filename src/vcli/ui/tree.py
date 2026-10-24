"""Explorer sidebar file tree.

Implemented as a custom ``UIControl`` so it can render folder chevrons,
selection, the active-file marker and mouse hit testing directly.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from prompt_toolkit.data_structures import Point
from prompt_toolkit.formatted_text import StyleAndTextTuples
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.layout.controls import UIContent, UIControl
from prompt_toolkit.mouse_events import MouseEventType

from ..workspace import Node

if TYPE_CHECKING:  # pragma: no cover
    from ..app import EditorApp


class FileTreeControl(UIControl):
    def __init__(self, app: EditorApp) -> None:
        self.app = app
        self.scroll = 0
        self._rows: list[Node] = []
        self._keys: KeyBindings | None = None

    def is_focusable(self) -> bool:
        return True

    # ------------------------------------------------------------------ render
    def create_content(self, width: int, height: int) -> UIContent:
        workspace = self.app.workspace
        flat = workspace.flatten()
        selected = workspace.selected

        if flat:
            if selected < self.scroll:
                self.scroll = selected
            elif selected >= self.scroll + height:
                self.scroll = selected - height + 1
        else:
            self.scroll = 0
        self.scroll = max(0, min(self.scroll, max(0, len(flat) - height)))
        rows = flat[self.scroll : self.scroll + height]
        self._rows = rows

        active_path = None
        pane = self.app.active_pane
        if pane is not None and pane.path is not None:
            active_path = pane.path

        fragments: StyleAndTextTuples = []
        lines: list[StyleAndTextTuples] = []
        for offset, node in enumerate(rows):
            index = self.scroll + offset
            is_selected = index == selected
            is_active = active_path is not None and node.path == active_path
            classes = ["class:sidebar.item"]
            if node.is_dir:
                classes.append("class:sidebar.dir")
            if is_active and not node.is_dir:
                classes.append("class:sidebar.item.active")
            if is_selected:
                classes.append("class:sidebar.item.selected")
            style = " ".join(classes)

            indent = "  " * node.depth
            if node.is_dir:
                chevron = "\u25be " if node.expanded else "\u25b8 "
                chevron_style = "class:sidebar.chevron"
            else:
                chevron = "  "
                chevron_style = "class:sidebar.item"
            handler = self._row_handler(index, node)
            fragments = []
            fragments.append((style, indent))
            fragments.append((chevron_style, chevron, handler))
            name = node.name + ("/" if node.is_dir else "")
            fragments.append((style, name, handler))
            used = len(indent) + 2 + len(name)
            fragments.append(("class:sidebar", " " * max(0, width - used)))
            lines.append(fragments)

        for _ in range(height - len(rows)):
            lines.append([("class:sidebar", " " * width)])

        return UIContent(
            lambda y: lines[y] if 0 <= y < len(lines) else [],
            line_count=height,
            cursor_position=Point(0, 0),
        )

    def _row_handler(self, index: int, node: Node):
        def handler(event):
            self.app.layout.focus(self)
            self.app.workspace.selected = index
            if event.event_type == MouseEventType.MOUSE_UP:
                if node.is_dir:
                    self.app.workspace.toggle(node)
                else:
                    self.app.open_path(node.path)
            self.app.invalidate()

        return handler

    # ------------------------------------------------------------------- mouse
    def mouse_handler(self, mouse_event):
        self.app.layout.focus(self)
        row = mouse_event.position.y + self.scroll
        if 0 <= row < len(self._rows):
            self.app.workspace.selected = row
            node = self._rows[row]
            if mouse_event.event_type == MouseEventType.MOUSE_UP:
                if node.is_dir:
                    self.app.workspace.toggle(node)
                else:
                    self.app.open_path(node.path)
            self.app.invalidate()
            return None
        return NotImplemented

    # ------------------------------------------------------------------ keys
    def get_key_bindings(self) -> KeyBindings:
        if self._keys is not None:
            return self._keys
        keys = KeyBindings()
        workspace = self.app.workspace

        def selected_node() -> Node | None:
            return workspace.selected_node()

        @keys.add("up")
        @keys.add("k")
        def _up(event) -> None:
            workspace.move_selection(-1)
            self._ensure_visible()
            self.app.invalidate()

        @keys.add("down")
        @keys.add("j")
        def _down(event) -> None:
            workspace.move_selection(1)
            self._ensure_visible()
            self.app.invalidate()

        @keys.add("home")
        def _home(event) -> None:
            workspace.select(0)
            self._ensure_visible()
            self.app.invalidate()

        @keys.add("end")
        def _end(event) -> None:
            workspace.select(len(workspace.flatten()) - 1)
            self._ensure_visible()
            self.app.invalidate()

        @keys.add("pageup")
        def _page_up(event) -> None:
            workspace.move_selection(-10)
            self._ensure_visible()
            self.app.invalidate()

        @keys.add("pagedown")
        def _page_down(event) -> None:
            workspace.move_selection(10)
            self._ensure_visible()
            self.app.invalidate()

        @keys.add("right")
        @keys.add("l")
        def _expand(event) -> None:
            node = selected_node()
            if node is None:
                return
            if node.is_dir and not node.expanded:
                workspace.expand(node)
            elif node.is_dir and node.expanded:
                workspace.move_selection(1)
            self.app.invalidate()

        @keys.add("left")
        @keys.add("h")
        def _collapse(event) -> None:
            node = selected_node()
            if node is None:
                return
            if node.is_dir and node.expanded:
                workspace.collapse(node)
            else:
                parent = workspace.parent_of_selected()
                if parent is not None:
                    flat = workspace.flatten()
                    workspace.selected = flat.index(parent)
            self._ensure_visible()
            self.app.invalidate()

        @keys.add("enter")
        @keys.add("space")
        def _open(event) -> None:
            node = selected_node()
            if node is None:
                return
            if node.is_dir:
                workspace.toggle(node)
            else:
                self.app.open_path(node.path)
            self.app.invalidate()

        @keys.add("r")
        def _refresh(event) -> None:
            workspace.reload()
            self.app.notify("Explorer refreshed")
            self.app.invalidate()

        @keys.add("escape")
        @keys.add("tab")
        def _to_editor(event) -> None:
            self.app.focus_editor()

        self._keys = keys
        return keys

    def _ensure_visible(self) -> None:
        self.scroll = min(self.scroll, self.app.workspace.selected)

"""Clickable top-level File and Edit menus."""

from __future__ import annotations

from typing import TYPE_CHECKING

from prompt_toolkit.data_structures import Point
from prompt_toolkit.formatted_text import StyleAndTextTuples
from prompt_toolkit.layout.controls import UIContent, UIControl
from prompt_toolkit.mouse_events import MouseEventType
from prompt_toolkit.utils import get_cwidth

if TYPE_CHECKING:  # pragma: no cover
    from ..app import EditorApp


class MenuBarControl(UIControl):
    def __init__(self, app: EditorApp) -> None:
        self.app = app
        self._spans: list[tuple[int, int, str]] = []

    def is_focusable(self) -> bool:
        return False

    def create_content(self, width: int, height: int) -> UIContent:
        fragments: StyleAndTextTuples = []
        spans: list[tuple[int, int, str]] = []
        x = 0
        for label in ("File", "Edit"):
            text = f" {label} "
            cell_width = get_cwidth(text)
            fragments.append(("class:menubar.item", text))
            spans.append((x, x + cell_width, label.lower()))
            x += cell_width
        fragments.append(("class:menubar", " " * max(0, width - x)))
        self._spans = spans
        return UIContent(
            lambda lineno: fragments if lineno == 0 else [],
            line_count=1,
            cursor_position=Point(0, 0),
        )

    def mouse_handler(self, mouse_event):
        if mouse_event.event_type not in (MouseEventType.MOUSE_DOWN, MouseEventType.MOUSE_UP):
            return None
        x = mouse_event.position.x
        for start, end, menu in self._spans:
            if start <= x < end:
                self.app.open_menu(menu)
                return None
        return NotImplemented

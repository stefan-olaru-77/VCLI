"""The VSCode-style document tab bar."""

from __future__ import annotations

from typing import TYPE_CHECKING

from prompt_toolkit.data_structures import Point
from prompt_toolkit.formatted_text import StyleAndTextTuples
from prompt_toolkit.layout.controls import UIContent, UIControl
from prompt_toolkit.mouse_events import MouseEventType
from prompt_toolkit.utils import get_cwidth

if TYPE_CHECKING:  # pragma: no cover
    from ..app import EditorApp

MAX_TAB_TITLE = 26


class TabBarControl(UIControl):
    def __init__(self, app: EditorApp) -> None:
        self.app = app
        # Set after a close triggered by MOUSE_DOWN so that the matching
        # MOUSE_UP (which may land on a different tab now) is swallowed.
        self._suppress_up = False

    def is_focusable(self) -> bool:
        return False

    def create_content(self, width: int, height: int) -> UIContent:
        fragments: StyleAndTextTuples = []
        spans: list[tuple[int, int, str, int]] = []
        x = 0
        documents = self.app.documents

        if not documents:
            fragments.append(("class:tabbar", "  \u2039 no open editors \u203a"))
            return UIContent(
                lambda lineno: fragments if lineno == 0 else [],
                line_count=1,
                cursor_position=Point(0, 0),
            )

        active = self.app.active_index
        for index, pane in enumerate(documents):
            title = pane.display_name
            if len(title) > MAX_TAB_TITLE:
                title = title[: MAX_TAB_TITLE - 1] + "\u2026"
            if pane.dirty:
                title = "\u25cf " + title
            selected = index == active
            style = "class:tabbar.tab.active" if selected else "class:tabbar.tab"
            text = f" {title} "
            cell_width = get_cwidth(text)
            if x + cell_width + 3 > width:
                fragments.append(("class:tabbar.overflow", " \u2026 "))
                break
            fragments.append((style, text))
            spans.append((x, x + cell_width, "activate", index))
            x += cell_width
            close_style = (
                "class:tabbar.close.active" if selected else "class:tabbar.close"
            )
            fragments.append((close_style, " \u2715 "))
            spans.append((x, x + 3, "close", index))
            x += 3
            fragments.append(("class:tabbar.separator", "\u2502"))
            x += 1

        remaining = max(0, width - x)
        if remaining:
            fragments.append(("class:tabbar", " " * remaining))
        self._spans = spans

        return UIContent(
            lambda lineno: fragments if lineno == 0 else [],
            line_count=1,
            cursor_position=Point(0, 0),
        )

    def mouse_handler(self, mouse_event):
        if self._suppress_up:
            if mouse_event.event_type == MouseEventType.MOUSE_UP:
                self._suppress_up = False
                return None
            # A new gesture starts; do not swallow its release.
            if mouse_event.event_type == MouseEventType.MOUSE_DOWN:
                self._suppress_up = False
        x = mouse_event.position.x
        spans = getattr(self, "_spans", [])
        for start, end, action, index in spans:
            if start <= x < end:
                if action == "close":
                    # Close on press (like VSCode): a release that drifts a
                    # cell away from the tiny cross must not cancel the click,
                    # and terminals that only report button presses still work.
                    if mouse_event.event_type in (
                        MouseEventType.MOUSE_DOWN,
                        MouseEventType.MOUSE_UP,
                    ):
                        self._suppress_up = (
                            mouse_event.event_type == MouseEventType.MOUSE_DOWN
                        )
                        self.app.request_close(index)
                elif mouse_event.event_type == MouseEventType.MOUSE_DOWN:
                    self.app.activate(index)
                return None
        return NotImplemented

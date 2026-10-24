"""The bottom status bar."""

from __future__ import annotations

from typing import TYPE_CHECKING

from prompt_toolkit.formatted_text import StyleAndTextTuples
from prompt_toolkit.layout.containers import VSplit, Window
from prompt_toolkit.layout.controls import FormattedTextControl

if TYPE_CHECKING:  # pragma: no cover
    from ..app import EditorApp


class StatusBar:
    def __init__(self, app: EditorApp) -> None:
        self.app = app
        self.left = FormattedTextControl(self._left_text, focusable=False)
        self.right = FormattedTextControl(self._right_text, focusable=False)
        self.container = VSplit(
            [
                Window(self.left, dont_extend_width=True, style="class:statusbar"),
                Window(style="class:statusbar"),
                Window(
                    self.right,
                    dont_extend_width=True,
                    style="class:statusbar",
                ),
            ],
            height=1,
            style="class:statusbar",
        )

    def _left_text(self) -> StyleAndTextTuples:
        fragments: StyleAndTextTuples = [("class:statusbar.item", " ")]
        branch = self.app.git_branch
        if branch:
            fragments.append(("class:statusbar.branch", f"\ue0a0 {branch}  "))
        pane = self.app.active_pane
        if pane is not None:
            fragments.append(("class:statusbar.item", pane.display_name))
            if pane.dirty:
                fragments.append(("class:statusbar.modified", " \u25cf"))
            fragments.append(("class:statusbar.item", "  "))
        if self.app.message:
            style = (
                "class:statusbar.error" if self.app.message_error else "class:statusbar.message"
            )
            fragments.append((style, self.app.message))
        return fragments

    def _right_text(self) -> StyleAndTextTuples:
        pane = self.app.active_pane
        if pane is None:
            return [("class:statusbar.item", " Welcome ")]
        items = [
            f"Ln {pane.cursor_line}, Col {pane.cursor_column}",
            pane.indent_label,
            "UTF-8" if pane.encoding.lower() in ("utf-8", "utf-8-sig") else pane.encoding,
            "CRLF" if pane.eol == "\r\n" else "LF",
            pane.language.name,
        ]
        fragments: StyleAndTextTuples = []
        for item in items:
            fragments.append(("class:statusbar.item", f" {item}  "))
        fragments.append(("class:statusbar.item", " "))
        return fragments

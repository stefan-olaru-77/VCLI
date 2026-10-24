"""VSCode-style line number gutter."""

from __future__ import annotations

from collections.abc import Callable

from prompt_toolkit.formatted_text import StyleAndTextTuples
from prompt_toolkit.layout.containers import WindowRenderInfo
from prompt_toolkit.layout.controls import UIContent
from prompt_toolkit.layout.margins import Margin

from ..config import Config


class GutterMargin(Margin):
    """Right-aligned line numbers with a highlighted current line.

    Works with word wrap: continuation rows of a wrapped line get blank gutter
    cells instead of a duplicated number.
    """

    def __init__(self, get_config: Callable[[], Config]) -> None:
        self._get_config = get_config

    def get_width(self, get_ui_content: Callable[[], UIContent]) -> int:
        line_count = max(1, get_ui_content().line_count)
        digits = len(str(line_count))
        # One leading and one trailing space keeps the gutter readable.
        return max(3, digits) + 2

    def create_margin(
        self, window_render_info: WindowRenderInfo, width: int, height: int
    ) -> StyleAndTextTuples:
        config = self._get_config()
        current_lineno = window_render_info.ui_content.cursor_position.y
        relative = config.relative_line_numbers
        digits = max(1, width - 2)
        result: StyleAndTextTuples = []
        last_lineno: int | None = None
        rows = 0

        for lineno in window_render_info.displayed_lines:
            if lineno != last_lineno and lineno is not None:
                if lineno == current_lineno:
                    label = str(lineno + 1)
                    style = "class:line-number.current"
                elif relative:
                    label = str(abs(lineno - current_lineno))
                    style = "class:line-number"
                else:
                    label = str(lineno + 1)
                    style = "class:line-number"
                result.append((style, f" {label:>{digits}} "))
            else:
                result.append(("class:line-number", " " * width))
            result.append(("", "\n"))
            rows += 1
            last_lineno = lineno

        # Fill the remaining rows so the gutter background stays uniform.
        while rows < height:
            result.append(("class:line-number", " " * width))
            result.append(("", "\n"))
            rows += 1

        return result

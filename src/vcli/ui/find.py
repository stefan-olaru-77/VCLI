"""The find / replace widget and match highlighting provider."""

from __future__ import annotations

import bisect
from typing import TYPE_CHECKING

from prompt_toolkit.buffer import Buffer
from prompt_toolkit.document import Document
from prompt_toolkit.filters import Condition, has_selection
from prompt_toolkit.formatted_text import StyleAndTextTuples
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.keys import Keys
from prompt_toolkit.layout.containers import (
    ConditionalContainer,
    HSplit,
    VSplit,
    Window,
)
from prompt_toolkit.layout.controls import BufferControl, FormattedTextControl
from prompt_toolkit.selection import SelectionState, SelectionType

from ..search import Match, find_matches, replacement_for
from .processors import SpanProvider

if TYPE_CHECKING:  # pragma: no cover
    from ..app import EditorApp

MAX_HIGHLIGHT_MATCHES = 5_000


class FindBar(SpanProvider):
    """VSCode-like find/replace bar with live match highlighting."""

    def __init__(self, app: EditorApp) -> None:
        self.app = app
        self.active = False
        self.replace_mode = False
        self.case_sensitive = False
        self.whole_word = False
        self.regex = False
        self.matches: list[Match] = []
        self.index = -1
        self.error: str | None = None
        self._origin = 0
        self._suppress = False
        self._version = 0
        self._cache_doc: Document | None = None
        self._cache_version = -1
        self._spans: dict[int, list[tuple[int, int, str]]] = {}

        self.query_buffer = Buffer(
            name="find",
            multiline=False,
            on_text_changed=self._on_query_changed,
        )
        self.replace_buffer = Buffer(name="replace", multiline=False)
        self.query_control = BufferControl(
            buffer=self.query_buffer,
            key_bindings=self.keys,
            focusable=True,
        )
        self.replace_control = BufferControl(
            buffer=self.replace_buffer,
            key_bindings=self.keys,
            focusable=True,
        )

        label = Window(
            FormattedTextControl(lambda: [("class:findbar.label", " Find    ")]),
            width=9,
            style="class:findbar",
        )
        self.count_control = FormattedTextControl(self._count_text, focusable=False)
        self.toggle_control = FormattedTextControl(
            self._toggle_text, focusable=False, style="class:findbar"
        )
        row1 = VSplit(
            [
                label,
                Window(self.query_control, height=1, style="class:findbar.input"),
                Window(self.count_control, width=14, style="class:findbar"),
                Window(
                    self.toggle_control,
                    dont_extend_width=True,
                    style="class:findbar",
                ),
                Window(
                    FormattedTextControl(lambda: [("class:findbar.hint", "  ")]),
                    width=2,
                    style="class:findbar",
                ),
            ],
            height=1,
        )

        replace_label = Window(
            FormattedTextControl(lambda: [("class:findbar.label", " Replace ")]),
            width=9,
            style="class:findbar",
        )
        row2 = VSplit(
            [
                replace_label,
                Window(
                    self.replace_control,
                    height=1,
                    style="class:findbar.input",
                ),
                Window(
                    FormattedTextControl(
                        lambda: [
                            (
                                "class:findbar.hint",
                                "  Enter: replace   F5: replace all",
                            )
                        ]
                    ),
                    dont_extend_width=True,
                    style="class:findbar",
                ),
            ],
            height=1,
        )

        self.container = HSplit(
            [
                row1,
                ConditionalContainer(row2, Condition(lambda: self.replace_mode)),
            ]
        )

    # ------------------------------------------------------------- lifecycle
    def open(self, replace: bool = False) -> None:
        pane = self.app.active_pane
        if pane is None:
            return
        self.active = True
        self.replace_mode = replace
        self._origin = pane.buffer.cursor_position
        prefill = self._prefill(pane)
        self._suppress = True
        try:
            if prefill:
                # Select the prefilled word so typing replaces it, like VSCode.
                self.query_buffer.document = Document(
                    prefill, cursor_position=len(prefill)
                )
                self.query_buffer.selection_state = SelectionState(
                    0, SelectionType.CHARACTERS
                )
            elif not self.query_buffer.text:
                self.query_buffer.document = Document("")
        finally:
            self._suppress = False
        self.refresh(jump=False)
        if self.matches:
            self._jump_from(self._origin)
        self.app.layout.focus(self.query_control)
        self.app.invalidate()

    def close(self) -> None:
        if not self.active:
            return
        self.active = False
        self.matches = []
        self.index = -1
        self.error = None
        self._version += 1
        pane = self.app.active_pane
        if pane is not None:
            self.app.layout.focus(pane.buffer)
        self.app.invalidate()

    @staticmethod
    def _prefill(pane) -> str:
        selected = pane.selected_text()
        if selected and "\n" not in selected:
            return selected
        from ..actions import word_at

        found = word_at(pane.buffer.text, pane.buffer.cursor_position)
        return found[2] if found else ""

    # ----------------------------------------------------------------- search
    def _on_query_changed(self, _buffer: Buffer) -> None:
        if self._suppress or not self.active:
            return
        self.refresh(jump=False)
        if self.matches:
            self._jump_from(self._origin)
        else:
            self.index = -1
        self.app.invalidate()

    def refresh(self, jump: bool = False) -> None:
        pane = self.app.active_pane
        self._version += 1
        if pane is None or not self.active:
            self.matches = []
            self.error = None
            return
        query = self.query_buffer.text
        self.matches, self.error = find_matches(
            pane.buffer.text,
            query,
            case_sensitive=self.case_sensitive,
            whole_word=self.whole_word,
            regex=self.regex,
            limit=MAX_HIGHLIGHT_MATCHES,
        )
        if not self.matches:
            self.index = -1
        elif not 0 <= self.index < len(self.matches):
            self.index = 0

    def next_match(self, direction: int = 1) -> None:
        if not self.matches:
            return
        if self.index < 0:
            self.index = 0 if direction > 0 else len(self.matches) - 1
        else:
            self.index = (self.index + direction) % len(self.matches)
        self._select(self.index)

    def _jump_from(self, origin: int) -> None:
        if not self.matches:
            return
        starts = [m.start for m in self.matches]
        position = bisect.bisect_left(starts, origin)
        if position >= len(self.matches):
            position = 0
        self.index = position
        self._select(position)

    def _select(self, index: int) -> None:
        pane = self.app.active_pane
        if pane is None or not (0 <= index < len(self.matches)):
            return
        self.index = index
        match = self.matches[index]
        pane.set_selection(match.start, match.end)
        self.app.invalidate()

    def current_match(self) -> Match | None:
        if 0 <= self.index < len(self.matches):
            return self.matches[self.index]
        return None

    # -------------------------------------------------------------- replacing
    def replace_current(self) -> None:
        pane = self.app.active_pane
        match = self.current_match()
        if pane is None or match is None:
            return
        text = pane.buffer.text
        replacement = replacement_for(
            text,
            match,
            self.query_buffer.text,
            self.replace_buffer.text,
            case_sensitive=self.case_sensitive,
            whole_word=self.whole_word,
            regex=self.regex,
        )
        new_text = text[: match.start] + replacement + text[match.end :]
        cursor = match.start + len(replacement)
        pane.begin_edit()
        pane.buffer.document = Document(new_text, cursor_position=cursor)
        self._origin = cursor
        self.refresh()
        self._jump_from(self._origin)
        self.app.invalidate()

    def replace_all(self) -> None:
        pane = self.app.active_pane
        if pane is None or not self.matches:
            return
        text = pane.buffer.text
        query = self.query_buffer.text
        replacements = [
            replacement_for(
                text,
                match,
                query,
                self.replace_buffer.text,
                case_sensitive=self.case_sensitive,
                whole_word=self.whole_word,
                regex=self.regex,
            )
            for match in self.matches
        ]
        chunks: list[str] = []
        cursor = 0
        for match, replacement in zip(self.matches, replacements):
            chunks.append(text[cursor : match.start])
            chunks.append(replacement)
            cursor = match.end
        chunks.append(text[cursor:])
        new_text = "".join(chunks)
        pane.begin_edit()
        pane.buffer.document = Document(
            new_text, cursor_position=min(pane.buffer.cursor_position, len(new_text))
        )
        count = len(self.matches)
        self.refresh()
        self.app.notify(f"Replaced {count} occurrence{'s' if count != 1 else ''}")
        self.app.invalidate()

    # ------------------------------------------------------------- toggles UI
    def _count_text(self) -> StyleAndTextTuples:
        if self.error:
            return [("class:findbar.error", " invalid regex ")]
        query = self.query_buffer.text
        if not query:
            return [("class:findbar.count", "")]
        if not self.matches:
            return [("class:findbar.count", " No results ")]
        current = self.index + 1 if self.index >= 0 else 0
        return [("class:findbar.count", f" {current} of {len(self.matches)} ")]

    def _toggle_text(self) -> StyleAndTextTuples:
        def fragment(active: bool, label: str, action):
            style = "class:findbar.toggle.on" if active else "class:findbar.toggle"

            def handler(_event):
                action()

            return (style, label, handler)

        return [
            fragment(self.case_sensitive, " Aa ", self.toggle_case),
            fragment(self.whole_word, " ab ", self.toggle_word),
            fragment(self.regex, " .* ", self.toggle_regex),
            ("class:findbar.toggle", "  "),
            (
                "class:findbar.toggle",
                " \u2715 ",
                lambda _event: (self.close(), None)[1],
            ),
        ]

    def toggle_case(self) -> None:
        self.case_sensitive = not self.case_sensitive
        self.refresh()
        self.app.invalidate()

    def toggle_word(self) -> None:
        self.whole_word = not self.whole_word
        self.refresh()
        self.app.invalidate()

    def toggle_regex(self) -> None:
        self.regex = not self.regex
        self.refresh()
        self.app.invalidate()

    # --------------------------------------------------------- highlighting
    def spans_for_line(
        self, document: Document, lineno: int
    ) -> list[tuple[int, int, str]]:
        if not self.active or not self.matches:
            return []
        if document is not self._cache_doc or self._cache_version != self._version:
            self._build_cache(document)
        return self._spans.get(lineno, [])

    def _build_cache(self, document: Document) -> None:
        self._cache_doc = document
        self._cache_version = self._version
        self._spans = {}
        text = document.text
        line_starts = [0]
        for index, char in enumerate(text):
            if char == "\n":
                line_starts.append(index + 1)
        for match_index, match in enumerate(self.matches):
            style = (
                "class:search.match.current"
                if match_index == self.index
                else "class:search.match"
            )
            position = match.start
            while position < match.end:
                line = bisect.bisect_right(line_starts, position) - 1
                line_end = (
                    line_starts[line + 1] - 1
                    if line + 1 < len(line_starts)
                    else len(text)
                )
                segment_end = min(match.end, line_end)
                if segment_end > position:
                    self._spans.setdefault(line, []).append(
                        (
                            position - line_starts[line],
                            segment_end - line_starts[line],
                            style,
                        )
                    )
                position = line_end + 1

    # -------------------------------------------------------------- bindings
    @property
    def keys(self) -> KeyBindings:
        if not hasattr(self, "_keys"):
            keys = KeyBindings()

            @keys.add("enter")
            def _next(event) -> None:
                if self.app.layout.current_control is self.replace_control:
                    self.replace_current()
                else:
                    self.next_match(1)

            @keys.add("c-n")
            def _next_ctrl(event) -> None:
                self.next_match(1)

            @keys.add("c-p")
            def _previous(event) -> None:
                self.next_match(-1)

            @keys.add("escape")
            def _close(event) -> None:
                self.close()

            @keys.add("tab")
            @keys.add("s-tab")
            def _toggle_field(event) -> None:
                if not self.replace_mode:
                    return
                if self.app.layout.current_control is self.query_control:
                    self.app.layout.focus(self.replace_control)
                else:
                    self.app.layout.focus(self.query_control)

            @keys.add("f6")
            def _case(event) -> None:
                self.toggle_case()

            @keys.add("f7")
            def _word(event) -> None:
                self.toggle_word()

            @keys.add("f8")
            def _regex(event) -> None:
                self.toggle_regex()

            @keys.add("f5")
            def _replace_all(event) -> None:
                self.replace_all()

            @keys.add(Keys.Any, filter=has_selection)
            def _type_over_selection(event) -> None:
                if not event.data or not event.data.isprintable():
                    return
                event.current_buffer.cut_selection()
                event.current_buffer.insert_text(event.data)

            self._keys = keys
        return self._keys

    # ------------------------------------------------------------------ focus
    def focus_next_field(self) -> None:
        if self.app.layout.current_control is self.query_control:
            self.app.layout.focus(self.replace_control)
        else:
            self.app.layout.focus(self.query_control)

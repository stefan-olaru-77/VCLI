"""An editor pane: one open document, its gutter and its prompt_toolkit window."""

from __future__ import annotations

import re
from pathlib import Path
from typing import TYPE_CHECKING

from prompt_toolkit.buffer import Buffer
from prompt_toolkit.completion import Completer, Completion
from prompt_toolkit.document import Document
from prompt_toolkit.filters import Condition
from prompt_toolkit.layout.containers import ScrollOffsets, Window
from prompt_toolkit.layout.controls import BufferControl
from prompt_toolkit.layout.margins import ConditionalMargin
from prompt_toolkit.layout.processors import (
    HighlightMatchingBracketProcessor,
    TabsProcessor,
)
from prompt_toolkit.lexers import DynamicLexer
from prompt_toolkit.mouse_events import MouseEvent, MouseEventType
from prompt_toolkit.selection import SelectionState, SelectionType

from .. import actions
from ..config import Config
from ..emmet import expand_abbreviation
from ..fileio import LoadedFile, write_file
from ..languages import PLAIN_TEXT, Language, language_for_path
from .margin import GutterMargin
from .processors import (
    BracketPairColorizer,
    ColorDecorator,
    MultiSelectionHighlighter,
    SearchHighlighter,
    SemanticIdentifierColorizer,
)

if TYPE_CHECKING:  # pragma: no cover
    from ..app import EditorApp

WORD_SCAN_LIMIT = 2_000_000
HIGHLIGHT_LIMIT = 1_500_000


class LineHeightBufferControl(BufferControl):
    """BufferControl that adds visual spacing between logical lines."""

    def __init__(
        self,
        *args,
        line_height,
        hidden_lines=None,
        on_mouse_selection=None,
        cursor_visible=None,
        **kwargs,
    ) -> None:
        super().__init__(*args, **kwargs)
        self._line_height = line_height
        self._hidden_lines = hidden_lines or (lambda: set())
        self._on_mouse_selection = on_mouse_selection
        self._cursor_visible = cursor_visible or (lambda: True)

    def create_content(self, width: int, height: int, preview_search: bool = False):
        base = super().create_content(width, height, preview_search)
        line_height = max(1, int(self._line_height()))
        hidden = set(self._hidden_lines())
        visible_lines = [
            line for line in range(base.line_count) if line not in hidden
        ]
        if not visible_lines:
            visible_lines = [0]

        def get_line(index: int):
            logical, offset = divmod(index, line_height)
            if logical >= len(visible_lines) or offset:
                return []
            return base.get_line(visible_lines[logical])

        def display_row(row: int) -> int:
            if row in visible_lines:
                return visible_lines.index(row)
            previous = [index for index, line in enumerate(visible_lines) if line < row]
            return previous[-1] if previous else 0

        from prompt_toolkit.layout.controls import UIContent

        return UIContent(
            get_line=get_line,
            line_count=len(visible_lines) * line_height,
            cursor_position=base.cursor_position._replace(
                y=display_row(base.cursor_position.y) * line_height
            ),
            menu_position=(
                base.menu_position._replace(
                    y=display_row(base.menu_position.y) * line_height
                )
                if base.menu_position is not None
                else None
            ),
            show_cursor=base.show_cursor and self._cursor_visible(),
        )

    def mouse_handler(self, mouse_event):
        line_height = max(1, int(self._line_height()))
        position = mouse_event.position
        hidden = set(self._hidden_lines())
        line_count = self.buffer.document.line_count
        visible_lines = [line for line in range(line_count) if line not in hidden]
        if not visible_lines:
            visible_lines = [0]
        display_row = min(position.y // line_height, len(visible_lines) - 1)
        result = super().mouse_handler(
            MouseEvent(
                position=position._replace(y=visible_lines[display_row]),
                event_type=mouse_event.event_type,
                button=mouse_event.button,
                modifiers=mouse_event.modifiers,
            )
        )
        if (
            mouse_event.event_type == MouseEventType.MOUSE_UP
            and self._on_mouse_selection is not None
        ):
            self._on_mouse_selection()
        return result


class BufferWordCompleter(Completer):
    """VSCode-ish word completion based on the current document."""

    def __init__(self, get_buffer, minimum_length: int = 2) -> None:
        self._get_buffer = get_buffer
        self.minimum_length = minimum_length

    def get_completions(self, document: Document, complete_event):
        text = document.text
        if len(text) > WORD_SCAN_LIMIT:
            text = text[:WORD_SCAN_LIMIT]
        prefix = document.get_word_before_cursor()
        if len(prefix) < self.minimum_length:
            return
        seen: set[str] = set()
        pattern = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")
        matches: list[str] = []
        lowered = prefix.lower()
        for match in pattern.finditer(text):
            word = match.group(0)
            if word == prefix or word in seen:
                continue
            if word.lower().startswith(lowered):
                seen.add(word)
                matches.append(word)
                if len(matches) >= 200:
                    break
        for word in matches:
            yield Completion(word, start_position=-len(prefix))


class EditorPane:
    """One editable document plus its view.

    Undo/redo is delegated to prompt_toolkit's ``Buffer``; every custom text
    transformation first calls :meth:`begin_edit` so it becomes one undo step.
    """

    def __init__(
        self,
        app: EditorApp,
        title: str,
        text: str = "",
        path: Path | None = None,
        loaded: LoadedFile | None = None,
        language: Language | None = None,
    ) -> None:
        self.app = app
        self.path = path
        self.title = title
        self.encoding = loaded.encoding if loaded else "utf-8"
        self.eol = loaded.newline if loaded else "\n"
        self.mtime = loaded.mtime if loaded else 0.0
        self.warnings = list(loaded.warnings) if loaded else []
        self.language = language or self._detected_language(path)
        self.saved_text = text
        self.dirty = False
        self.highlight_enabled = len(text) <= HIGHLIGHT_LIMIT
        self._closed = False
        self.folded_lines: set[int] = set()
        self.multi_selections: list[tuple[int, int]] = []

        detected = (
            actions.detect_indentation(text) if app.config.detect_indentation else None
        )
        if detected is not None:
            self.use_spaces, self.tab_size = detected
        else:
            self.use_spaces = app.config.use_spaces
            self.tab_size = app.config.tab_size

        self.lexer = self._make_lexer()
        self.buffer: Buffer = Buffer(
            name=title,
            document=Document(text=text, cursor_position=0),
            multiline=True,
            completer=BufferWordCompleter(lambda: self.buffer),
            complete_while_typing=False,
            on_text_changed=self._on_text_changed,
            on_cursor_position_changed=self._on_cursor_moved,
        )
        self.gutter = GutterMargin(self._config)
        self.search_highlighter = SearchHighlighter(app.find)
        self.control = LineHeightBufferControl(
            buffer=self.buffer,
            lexer=DynamicLexer(
                lambda: self.lexer if self.highlight_enabled else None
            ),
            input_processors=[
                TabsProcessor(
                    tabstop=lambda: self.tab_size,
                    char1=" ",
                    char2=" ",
                    style="class:editor",
                ),
                SemanticIdentifierColorizer(lambda: self.language),
                MultiSelectionHighlighter(self._multi_selection_spans),
                HighlightMatchingBracketProcessor(chars="()[]{}"),
                self.search_highlighter,
                BracketPairColorizer(lambda: self._config().bracket_pair_colorization),
                ColorDecorator(lambda: self._config().color_decorators),
            ],
            include_default_input_processors=True,
            focus_on_click=True,
            line_height=lambda: self._config().line_height,
            hidden_lines=lambda: self.folded_lines if self._config().code_folding else set(),
            on_mouse_selection=self._copy_mouse_selection,
            cursor_visible=self.app.cursor_visible,
        )
        self.window = Window(
            content=self.control,
            left_margins=[
                ConditionalMargin(
                    self.gutter, Condition(lambda: self._config().line_numbers)
                )
            ],
            wrap_lines=Condition(lambda: self._config().word_wrap),
            cursorline=Condition(lambda: self._config().highlight_current_line),
            scroll_offsets=ScrollOffsets(
                top=self._config().scroll_off,
                bottom=self._config().scroll_off,
            ),
            allow_scroll_beyond_bottom=False,
            char=" ",
            style="class:editor",
        )

    # ------------------------------------------------------------- lifecycle
    def _config(self) -> Config:
        return self.app.config

    def _detected_language(self, path: Path | None) -> Language:
        return language_for_path(path) if self.app.config.detect_language else PLAIN_TEXT

    def _make_lexer(self):
        if not self.highlight_enabled:
            return None
        from ..languages import lexer_for

        return lexer_for(self.language)

    def _on_text_changed(self, buffer: Buffer) -> None:
        self.dirty = buffer.text != self.saved_text
        self.app.reset_blink()
        self.app.on_editor_text_changed(self)

    def _on_cursor_moved(self, buffer: Buffer) -> None:
        self.app.reset_blink()
        self.app.invalidate()

    def _multi_selection_spans(self, line_number: int) -> list[tuple[int, int]]:
        line_start = self.buffer.document.translate_row_col_to_index(line_number, 0)
        line_end = line_start + len(self.buffer.document.lines[line_number])
        return [
            (max(0, start - line_start), min(line_end, end) - line_start)
            for start, end in self.multi_selections
            if start < line_end and end > line_start and end > start
        ]

    def _copy_mouse_selection(self) -> None:
        if not self.app.config.copy_on_select:
            return
        selection = self.selection()
        if not selection.empty:
            self.app.set_clipboard(self.buffer.text[selection.start : selection.end])

    @property
    def is_untitled(self) -> bool:
        return self.path is None

    @property
    def display_name(self) -> str:
        return self.path.name if self.path else self.title

    @property
    def label(self) -> str:
        if self.dirty:
            return f"\u25cf {self.display_name}"
        return self.display_name

    @property
    def cursor_line(self) -> int:
        return self.buffer.document.cursor_position_row + 1

    @property
    def cursor_column(self) -> int:
        return self.buffer.document.cursor_position_col + 1

    @property
    def indent_unit(self) -> str:
        return " " * self.tab_size if self.use_spaces else "\t"

    @property
    def indent_label(self) -> str:
        return f"Spaces: {self.tab_size}" if self.use_spaces else "Tab Size: " + str(
            self.tab_size
        )

    # ------------------------------------------------------------ primitives
    def begin_edit(self) -> None:
        self.buffer.save_to_undo_stack()

    def set_text(
        self,
        text: str,
        cursor: int,
        selection: tuple[int, int] | None = None,
    ) -> None:
        self.multi_selections.clear()
        self.begin_edit()
        clamped = max(0, min(cursor, len(text)))
        self.buffer.document = Document(text, cursor_position=clamped)
        if selection is not None:
            start, end = selection
            start = max(0, min(start, len(text)))
            end = max(0, min(end, len(text)))
            if start != end:
                self.buffer.exit_selection()
                self.buffer.selection_state = SelectionState(
                    start, SelectionType.CHARACTERS
                )
                self.buffer.cursor_position = end

    def set_selection(self, start: int, end: int) -> None:
        text = self.buffer.text
        start = max(0, min(start, len(text)))
        end = max(0, min(end, len(text)))
        self.buffer.exit_selection()
        self.buffer.cursor_position = end
        if start != end:
            self.buffer.selection_state = SelectionState(
                start, SelectionType.CHARACTERS
            )
            self.buffer.cursor_position = end

    def selection(self) -> actions.Selection:
        document = self.buffer.document
        ranges = list(document.selection_ranges())
        if ranges:
            start, end = ranges[0]
            return actions.Selection(start, end)
        cursor = self.buffer.cursor_position
        return actions.Selection(cursor, cursor)

    def selected_text(self) -> str:
        sel = self.selection()
        return self.buffer.text[sel.start : sel.end]

    def replace_selection(self, text: str) -> None:
        """Replace the selection (or insert at the cursor) as one undo step."""
        sel = self.selection()
        current = self.buffer.text
        new_text = current[: sel.start] + text + current[sel.end :]
        self.set_text(new_text, sel.start + len(text))

    def line_column(self) -> tuple[int, int]:
        return self.cursor_line, self.cursor_column

    # ------------------------------------------------------------ editing ops
    def newline(self, pair_aware: bool = True) -> None:
        text = self.buffer.text
        cursor = self.buffer.cursor_position
        if self.app.config.auto_indent:
            payload, offset = actions.auto_indent_newline(
                text, cursor, self.indent_unit, pair_aware=pair_aware
            )
        else:
            payload, offset = "\n", 1
        if self.app.config.auto_closing_comments and self.language.line_comment:
            line_start = actions.line_start(text, cursor)
            before = text[line_start:cursor].lstrip()
            if before.startswith(self.language.line_comment):
                marker = self.language.line_comment
                payload += marker + " "
                offset = len(payload)
        self.set_text(text[:cursor] + payload + text[cursor:], cursor + offset)

    def refresh_preferences(self) -> None:
        """Apply language and indentation detection changes to this pane."""
        self.language = self._detected_language(self.path)
        detected = (
            actions.detect_indentation(self.buffer.text)
            if self.app.config.detect_indentation
            else None
        )
        if detected is not None:
            self.use_spaces, self.tab_size = detected
        else:
            self.use_spaces = self.app.config.use_spaces
            self.tab_size = self.app.config.tab_size
        self.lexer = self._make_lexer()
        self.app.invalidate()

    def toggle_fold(self) -> None:
        """Fold or unfold the indented block following the current line."""
        if not self.app.config.code_folding:
            self.app.notify("Code folding is disabled", error=True)
            return
        lines = self.buffer.text.split("\n")
        header = self.buffer.document.cursor_position_row
        if header >= len(lines) - 1:
            return
        current = lines[header]
        indent = len(current) - len(current.lstrip(" \t"))
        descendants: set[int] = set()
        for index in range(header + 1, len(lines)):
            line = lines[index]
            if line.strip():
                level = len(line) - len(line.lstrip(" \t"))
                if level <= indent:
                    break
            descendants.add(index)
        if not descendants:
            self.app.notify("No foldable block on this line")
            return
        if descendants.issubset(self.folded_lines):
            self.folded_lines.difference_update(descendants)
            self.app.notify("Block unfolded")
        else:
            self.folded_lines.update(descendants)
            self.app.notify("Block folded")
        self.app.invalidate()

    def indent(self) -> None:
        sel = self.selection()
        text = self.buffer.text
        if sel.empty:
            new_text, cursor = actions.indent_at_cursor(
                text, sel.start, self.tab_size, self.use_spaces
            )
            self.set_text(new_text, cursor)
        else:
            new_text, start, end = actions.indent_lines(text, sel.start, sel.end, self.indent_unit)
            self.set_text(new_text, end, (start, end))

    def outdent(self) -> None:
        sel = self.selection()
        text = self.buffer.text
        if sel.empty:
            new_text, cursor = actions.outdent_at_cursor(text, sel.start, self.tab_size)
            self.set_text(new_text, cursor)
        else:
            new_text, start, end = actions.outdent_lines(
                text, sel.start, sel.end, self.tab_size, self.use_spaces
            )
            self.set_text(new_text, end, (start, end))

    def toggle_comment(self) -> bool:
        sel = self.selection()
        text = self.buffer.text
        cursor = self.buffer.cursor_position
        if self.language.line_comment:
            new_text, start, end = actions.toggle_comment(
                text, sel.start, sel.end, self.language.line_comment
            )
        elif self.language.block_comment:
            opening, closing = self.language.block_comment
            new_text, start, end = actions.wrap_block_comment(
                text, sel.start, sel.end, opening, closing
            )
        else:
            self.app.notify(f"{self.language.name} has no comment syntax")
            return False
        if sel.empty:
            column = cursor - actions.line_start(text, cursor)
            line_begin = actions.line_start(new_text, min(start, len(new_text) - 1))
            new_cursor = min(line_begin + column, actions.line_end(new_text, line_begin))
            self.set_text(new_text, new_cursor)
        else:
            self.set_text(new_text, end, (start, end))
        return True

    def duplicate_line(self) -> None:
        text = self.buffer.text
        sel = self.selection()
        cursor = self.buffer.cursor_position
        new_text, start, end, new_cursor = actions.duplicate_lines(
            text, sel.start, sel.end, cursor
        )
        if sel.empty:
            self.set_text(new_text, new_cursor)
        else:
            self.set_text(new_text, new_cursor, (start, end))

    def move_line(self, direction: int) -> None:
        text = self.buffer.text
        sel = self.selection()
        result = actions.move_lines(text, sel.start, sel.end, direction)
        if result is None:
            return
        new_text, start, end, cursor = result
        if sel.empty:
            self.set_text(new_text, cursor)
        else:
            self.set_text(new_text, cursor, (start, end))

    def delete_line(self) -> None:
        text = self.buffer.text
        sel = self.selection()
        new_text, cursor = actions.delete_lines(text, sel.start, sel.end)
        self.set_text(new_text, cursor)

    def select_all(self) -> None:
        self.set_selection(0, len(self.buffer.text))

    def select_line(self) -> None:
        """Select the complete current line, including its line ending."""
        text = self.buffer.text
        start, end = actions.line_bounds(text, self.buffer.cursor_position)
        if end < len(text):
            end += 1
        self.set_selection(start, end)

    def select_word(self) -> None:
        """Select the word under the cursor."""
        boundaries = self.buffer.document.find_boundaries_of_current_word()
        if boundaries[0] == boundaries[1]:
            return
        cursor = self.buffer.cursor_position
        self.set_selection(cursor + boundaries[0], cursor + boundaries[1])

    def add_next_occurrence(self) -> None:
        """Add the next occurrence of the current word/selection."""
        current = self.selection()
        if current.empty:
            boundaries = self.buffer.document.find_boundaries_of_current_word()
            if boundaries[0] == boundaries[1]:
                return
            start = self.buffer.cursor_position + boundaries[0]
            end = self.buffer.cursor_position + boundaries[1]
            current = actions.Selection(start, end)
            self.set_selection(start, end)
        needle = self.buffer.text[current.start : current.end]
        if not needle:
            return
        if not self.multi_selections:
            self.multi_selections = [(current.start, current.end)]
        search_from = current.end
        next_start = self.buffer.text.find(needle, search_from)
        if next_start < 0:
            next_start = self.buffer.text.find(needle)
        candidate = (next_start, next_start + len(needle)) if next_start >= 0 else None
        if candidate is None or candidate in self.multi_selections:
            self.app.notify("No more occurrences")
            return
        self.multi_selections.append(candidate)
        self.set_selection(*candidate)
        self.app.invalidate()

    def has_multi_selection(self) -> bool:
        return len(self.multi_selections) > 1

    def replace_multi_selection(self, replacement: str) -> None:
        if not self.has_multi_selection():
            self.replace_selection(replacement)
            return
        text = self.buffer.text
        for start, end in sorted(self.multi_selections, reverse=True):
            text = text[:start] + replacement + text[end:]
        first = min(start for start, _ in self.multi_selections)
        self.multi_selections.clear()
        self.set_text(text, first + len(replacement))

    def undo(self) -> None:
        self.buffer.undo()
        self.dirty = self.buffer.text != self.saved_text
        self.app.on_editor_text_changed(self)

    def redo(self) -> None:
        self.buffer.redo()
        self.dirty = self.buffer.text != self.saved_text
        self.app.on_editor_text_changed(self)

    def copy(self) -> None:
        sel = self.selection()
        if not sel.empty:
            self.app.set_clipboard(self.buffer.text[sel.start : sel.end])
        else:
            text = self.buffer.text
            start, end = actions.line_bounds(text, self.buffer.cursor_position)
            chunk = text[start:end]
            if end < len(text):
                chunk += "\n"
            self.app.set_clipboard(chunk)

    def cut(self) -> None:
        sel = self.selection()
        if sel.empty:
            self.copy()
            self.delete_line()
            return
        self.app.set_clipboard(self.buffer.text[sel.start : sel.end])
        text = self.buffer.text
        self.set_text(text[: sel.start] + text[sel.end :], sel.start)

    def paste(self) -> None:
        payload = self.app.get_clipboard()
        if payload:
            self.replace_selection(payload)

    def expand_abbreviation(self) -> None:
        """Expand the Emmet abbreviation immediately before the cursor."""
        text = self.buffer.text
        cursor = self.buffer.cursor_position
        line_start = text.rfind("\n", 0, cursor) + 1
        prefix = text[line_start:cursor]
        match = re.search(r"[^\s]+$", prefix)
        if not match:
            self.app.notify("No Emmet abbreviation before the cursor", error=True)
            return
        abbreviation = match.group(0)
        try:
            leading = prefix[: match.start()]
            base = leading if not leading.strip() else ""
            replacement = expand_abbreviation(abbreviation, self.indent_unit, base)
        except ValueError:
            self.app.notify(f"Cannot expand abbreviation: {abbreviation}", error=True)
            return
        start = line_start + match.start()
        self.set_text(text[:start] + replacement + text[cursor:], start + len(replacement))

    # ------------------------------------------------------------------- save
    def save(self, path: Path | None = None, force: bool = False) -> bool:
        target = path or self.path
        if target is None:
            self.app.notify("No file name: use File: Save As")
            return False
        target = Path(target).expanduser()
        if path is not None:
            self.path = target
            self.title = target.name
            self.language = self._detected_language(target)
            self.lexer = self._make_lexer()

        text = self.buffer.text
        if self.app.config.trim_trailing_whitespace_on_save or self.app.config.format_on_save:
            trimmed = actions.trim_trailing_whitespace(text)
            if trimmed != text:
                cursor = min(self.buffer.cursor_position, len(trimmed))
                self.buffer.document = Document(trimmed, cursor_position=cursor)
                text = trimmed

        if (
            not force
            and target.exists()
            and self.mtime
            and abs(target.stat().st_mtime - self.mtime) > 1e-6
            and self.dirty
        ):
            self.app.notify(
                "File changed on disk. Press Ctrl+S again to overwrite."
            )
            self.mtime = target.stat().st_mtime
            return False

        try:
            write_file(
                target,
                text,
                encoding=self.encoding,
                newline=self.eol,
                make_dirs=True,
            )
        except OSError as exc:
            self.app.notify(f"Could not save {target.name}: {exc}", error=True)
            return False

        self.saved_text = text
        self.dirty = False
        try:
            stat = target.stat()
            self.mtime = stat.st_mtime
        except OSError:
            self.mtime = 0.0
        self.app.config.remember_file(target)
        self.app.on_saved(self)
        return True

    def reload(self) -> bool:
        if self.path is None:
            return False
        from ..fileio import read_file

        try:
            loaded = read_file(self.path)
        except Exception as exc:
            self.app.notify(f"Reload failed: {exc}", error=True)
            return False
        self.buffer.document = Document(loaded.text, cursor_position=0)
        self.saved_text = loaded.text
        self.dirty = False
        self.encoding = loaded.encoding
        self.eol = loaded.newline
        self.mtime = loaded.mtime
        self.highlight_enabled = len(loaded.text) <= HIGHLIGHT_LIMIT
        self.lexer = self._make_lexer()
        self.app.notify(f"Reloaded {self.display_name}")
        return True

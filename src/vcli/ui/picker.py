"""Overlay used by the command palette, quick open, go-to-line and themes."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

from prompt_toolkit.buffer import Buffer
from prompt_toolkit.document import Document
from prompt_toolkit.filters import Condition, has_selection
from prompt_toolkit.formatted_text import StyleAndTextTuples
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.keys import Keys
from prompt_toolkit.layout.containers import (
    ConditionalContainer,
    Float,
    HSplit,
    VSplit,
    Window,
)
from prompt_toolkit.layout.controls import BufferControl, FormattedTextControl
from prompt_toolkit.mouse_events import MouseEventType

from ..fuzzy import filter_items
from ..theme import THEMES

if TYPE_CHECKING:  # pragma: no cover
    from ..app import EditorApp

RESULTS_ROWS = 10
SETTINGS_ROWS = 16


@dataclass
class PickerItem:
    label: str
    description: str = ""
    keys: str = ""
    action: Callable[[], None] | None = None
    search_text: str = ""
    extra: dict = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.search_text:
            self.search_text = f"{self.label} {self.description}"


class PickerOverlay:
    """A VSCode-style quick pick rendered as a floating panel."""

    def __init__(self, app: EditorApp) -> None:
        self.app = app
        self.active = False
        self.mode = "commands"
        self.title = "Command Palette"
        self.items: list[PickerItem] = []
        self.filtered: list[tuple[PickerItem, list[int]]] = []
        self.index = 0
        self._store: dict[str, object] = {}
        self._frame_width = 40
        self.settings_section = ""

        self.input_buffer = Buffer(
            name="picker",
            multiline=False,
            read_only=Condition(lambda: self.mode == "confirm"),
            on_text_changed=self._on_input_changed,
        )
        self.input_control = BufferControl(
            buffer=self.input_buffer,
            key_bindings=self.keys,
            focusable=True,
        )
        prompt = Window(
            FormattedTextControl(self._prompt_text),
            dont_extend_width=True,
            style="class:picker.input.title",
        )
        input_row = VSplit(
            [
                prompt,
                Window(self.input_control, height=1, style="class:picker.input"),
            ],
            height=1,
        )
        menu_header = ConditionalContainer(
            Window(
                FormattedTextControl(
                    lambda: [("class:picker.prompt", f" {self.title} ")]
                ),
                height=1,
                style="class:picker.input",
            ),
            Condition(lambda: self.mode == "menu"),
        )
        input_container = ConditionalContainer(
            input_row, Condition(lambda: self.mode != "menu")
        )
        self.settings_tabs = ConditionalContainer(
            Window(
                FormattedTextControl(self._settings_tabs_text, focusable=False),
                height=1,
                style="class:picker.tabs",
            ),
            Condition(lambda: self.mode == "settings"),
        )
        separator = Window(height=1, char="\u2500", style="class:picker.border")
        results = Window(
            FormattedTextControl(self._render_results, focusable=False),
            height=RESULTS_ROWS,
            style="class:picker",
        )
        self.results_window = results
        footer = Window(
            FormattedTextControl(self._footer_text, focusable=False),
            height=1,
            style="class:picker.footer",
        )
        self.container = HSplit(
            [menu_header, input_container, self.settings_tabs, separator, results, footer]
        )
        border_top = Window(
            FormattedTextControl(self._border_top), height=1, style="class:picker.border"
        )
        border_bottom = Window(
            FormattedTextControl(self._border_bottom), height=1, style="class:picker.border"
        )
        border_side = lambda: Window(
            width=1, char="\u2502", style="class:picker.border"
        )
        self.frame = HSplit(
            [
                border_top,
                VSplit([border_side(), self.container, border_side()]),
                border_bottom,
            ]
        )
        self.shadow_window = Window(char=" ", style="class:picker.shadow")
        self.shadow_float = Float(
            content=ConditionalContainer(
                self.shadow_window, Condition(lambda: self.active)
            ),
            top=3,
            left=3,
            width=40,
            height=RESULTS_ROWS + 5,
            z_index=9,
            transparent=False,
            allow_cover_cursor=True,
        )
        self.float = Float(
            content=ConditionalContainer(
                self.frame, Condition(lambda: self.active)
            ),
            top=2,
            left=2,
            width=40,
            height=RESULTS_ROWS + 5,
            z_index=10,
            transparent=False,
            allow_cover_cursor=True,
        )

    # --------------------------------------------------------------- opening
    def open_commands(self) -> None:
        items = [
            PickerItem(
                label=command.title,
                description=command.category,
                keys=command.keys,
                action=command.run,
            )
            for command in self.app.commands.all()
        ]
        self._open("commands", items, "Command Palette")

    def open_files(self) -> None:
        self.app.workspace.reload()
        root = self.app.workspace.root
        files = self.app.workspace.visible_files()
        items: list[PickerItem] = []
        for path in files:
            try:
                relative = str(path.relative_to(root))
            except ValueError:
                relative = str(path)
            items.append(
                PickerItem(
                    label=relative,
                    description="",
                    action=lambda p=path: self.app.open_path(p),
                )
            )
        self._open("files", items, "Go to File")
        self._store["root"] = root

    def open_menu(
        self,
        title: str,
        items: list[PickerItem],
        *,
        searchable: bool = False,
        anchor_x: int = 0,
    ) -> None:
        """Open a fixed menu or a searchable settings menu."""
        self._open("settings" if searchable else "menu", items, title)
        if not searchable:
            self.float.left = max(0, anchor_x)
            self.shadow_float.left = self.float.left + 1

    def open_line(self) -> None:
        pane = self.app.active_pane
        if pane is None:
            return
        self._open("lines", [], "Go to Line")
        self._store["cursor_line"] = pane.cursor_line

    def open_themes(self) -> None:
        items = []
        for key, spec in THEMES.items():
            selected = key == self.app.config.theme
            items.append(
                PickerItem(
                    label=spec.label,
                    description="\u2713" if selected else "",
                    action=lambda k=key: self.app.apply_theme(k),
                )
            )
        self._open("themes", items, "Color Theme")

    def open_input(
        self,
        title: str,
        initial: str,
        on_accept: Callable[[str], None],
    ) -> None:
        """Single-line prompt used by "Save As"."""
        self._open("input", [], title)
        self._store["accept"] = on_accept
        self.input_buffer.document = Document(initial)
        self.input_buffer.cursor_position = len(initial)
        self._on_input_changed()

    def confirm(
        self,
        title: str,
        message: str,
        choices: list[tuple[str, Callable[[], None]]],
    ) -> None:
        items = [
            PickerItem(label=label, action=action) for label, action in choices
        ]
        self._open("confirm", items, title)
        self._store["message"] = message

    def _open(
        self, mode: str, items: list[PickerItem], title: str
    ) -> None:
        self.mode = mode
        self.title = title
        self.items = items
        self.index = 0
        if mode == "settings":
            sections = self._settings_sections(items)
            self.settings_section = sections[0] if sections else ""
        self.active = True
        menu = mode == "menu"
        self.float.width = self._float_width() + 2
        self._frame_width = self.float.width
        self.float.height = self._float_height()
        if menu:
            self.float.top = 2
            self.float.left = 0
        else:
            self.float.top = max(0, (self.app.terminal_height - self.float.height) // 2)
            self.float.left = max(0, (self.app.terminal_width - self.float.width) // 2)
        self.shadow_float.top = self.float.top + 1
        self.shadow_float.left = self.float.left + 1
        self.shadow_float.width = self.float.width
        self.shadow_float.height = self.float.height
        self.results_window.height = self._results_rows()
        self.input_buffer.set_document(Document(""), bypass_readonly=True)
        self._on_input_changed()
        self.app.layout.focus(self.input_control)
        self.app.invalidate()

    def _border_top(self) -> StyleAndTextTuples:
        return [("class:picker.border", "\u250c" + "\u2500" * max(0, self._frame_width - 2) + "\u2510")]

    def _border_bottom(self) -> StyleAndTextTuples:
        return [("class:picker.border", "\u2514" + "\u2500" * max(0, self._frame_width - 2) + "\u2518")]

    def close(self) -> None:
        if not self.active:
            return
        self.active = False
        self.items = []
        self.filtered = []
        self.index = 0
        self._store = {}
        pane = self.app.active_pane
        if pane is not None:
            self.app.layout.focus(pane.buffer)
        elif self.app.tree_window is not None:
            self.app.layout.focus(self.app.tree_window)
        self.app.invalidate()

    # -------------------------------------------------------------- filtering
    def _on_input_changed(self, _buffer: Buffer | None = None) -> None:
        query = self.input_buffer.text
        if self.mode == "lines":
            self.filtered = [(item, []) for item in self._line_items(query)]
            self.index = 0
            self.app.invalidate()
            return
        if self.mode == "input":
            callback = self._store.get("accept")
            action = (
                (lambda cb=callback: cb(self.input_buffer.text))
                if callback is not None
                else None
            )
            item = PickerItem(
                label=query or "(empty path)",
                description="Enter to confirm",
                action=action,
            )
            self.filtered = [(item, [])]
            self.index = 0
            self.app.invalidate()
            return
        if self.mode == "menu":
            self.filtered = [(item, []) for item in self.items]
            self.index = 0
            self.app.invalidate()
            return
        if self.mode == "files":
            self.filtered = filter_items(
                query, self.items, key=lambda item: item.label
            )
            if query.strip():
                self.filtered = self.filtered[:2000]
                self._maybe_add_create_item(query)
        elif self.mode == "settings":
            section_items = [
                item for item in self.items if self._setting_section(item) == self.settings_section
            ]
            self.filtered = filter_items(
                query, section_items, key=lambda item: item.search_text
            )
        else:
            self.filtered = filter_items(
                query, self.items, key=lambda item: item.search_text
            )
        self.index = 0
        self.app.invalidate()

    def _maybe_add_create_item(self, query: str) -> None:
        root = self._store.get("root")
        if not isinstance(root, Path):
            return
        candidate = Path(query.strip())
        if candidate.is_absolute():
            target = candidate
        else:
            target = root / candidate
        try:
            target.relative_to(root)
        except ValueError:
            return
        if target.exists() or " " in query.strip():
            return
        label = f"Create file: {self.app.workspace.relative(target)}"
        self.filtered.append(
            (
                PickerItem(
                    label=label,
                    description="new file",
                    action=lambda p=target: self.app.create_file(p),
                ),
                [],
            )
        )

    def _line_items(self, query: str) -> list[PickerItem]:
        pane = self.app.active_pane
        if pane is None:
            return []
        digits = "".join(ch for ch in query if ch.isdigit())
        lines = pane.buffer.text.split("\n")
        if not digits:
            start = self._store.get("cursor_line", 1)
            start = max(1, int(start))
        else:
            start = max(1, int(digits))
        start = min(start, max(1, len(lines)))
        items: list[PickerItem] = []
        for number in range(start, min(start + RESULTS_ROWS, len(lines) + 1)):
            preview = lines[number - 1].strip()
            if len(preview) > 60:
                preview = preview[:57] + "..."
            items.append(
                PickerItem(
                    label=f"Line {number}",
                    description=preview,
                    action=lambda n=number: self.app.goto_line(n),
                )
            )
        return items

    # ---------------------------------------------------------------- display
    def _results_rows(self) -> int:
        return SETTINGS_ROWS if self.mode == "settings" else RESULTS_ROWS

    def _float_height(self) -> int:
        """Return the complete frame height, including borders and tabs."""
        extra = 6 if self.mode == "settings" else 5
        return self._results_rows() + extra

    @staticmethod
    def _setting_section(item: PickerItem) -> str:
        return item.label.split(":", 1)[0].strip() or "General"

    def _settings_sections(self, items: list[PickerItem] | None = None) -> list[str]:
        source = self.items if items is None else items
        return list(dict.fromkeys(self._setting_section(item) for item in source))

    def _select_settings_section(self, section: str) -> None:
        sections = self._settings_sections()
        if section not in sections:
            return
        self.settings_section = section
        self.index = 0
        self._on_input_changed()

    def _move_settings_section(self, delta: int) -> None:
        sections = self._settings_sections()
        if not sections:
            return
        current = sections.index(self.settings_section) if self.settings_section in sections else 0
        self._select_settings_section(sections[(current + delta) % len(sections)])

    def _settings_tabs_text(self) -> StyleAndTextTuples:
        fragments: StyleAndTextTuples = []
        for section in self._settings_sections():
            selected = section == self.settings_section
            style = "class:picker.tabs.selected" if selected else "class:picker.tabs.item"

            def handler(event, selected_section=section):
                if event.event_type in {MouseEventType.MOUSE_DOWN, MouseEventType.MOUSE_UP}:
                    self._select_settings_section(selected_section)

            fragments.append((style, f"  {section}  ", handler))
        return fragments

    def _float_width(self) -> int:
        if self.mode == "menu":
            widest = max(
                (
                    len(item.label)
                    + len(item.description)
                    + len(item.keys)
                    + 8
                    for item in self.items
                ),
                default=28,
            )
            return max(28, min(72, widest))
        if self.mode == "settings":
            return max(64, min(112, self.app.terminal_width - 6))
        return max(40, min(96, self.app.terminal_width - 8))

    def _prompt_text(self) -> StyleAndTextTuples:
        if self.mode == "confirm":
            message = str(self._store.get("message", ""))
            text = f" {self.title} - {message} "
            return [("class:picker.prompt", text)]
        icons = {
            "commands": "\u203a",
            "files": "\u2315",
            "lines": ":",
            "themes": "\u25d1",
            "input": "\u270e",
        }
        icon = icons.get(self.mode, "\u203a")
        if self.mode in {"input", "settings"}:
            return [("class:picker.prompt", f" {self.title}: ")]
        return [("class:picker.prompt", f" {icon} ")]

    def _footer_text(self) -> StyleAndTextTuples:
        if self.mode == "confirm":
            hint = "  \u2191\u2193 choose    Enter confirm    Esc cancel"
        elif self.mode == "lines":
            hint = "  type a line number    Enter go    Esc cancel"
        elif self.mode == "input":
            hint = "  type a path    Enter confirm    Esc cancel"
        elif self.mode == "files":
            hint = "  \u2191\u2193 navigate    Enter open    Esc cancel"
        elif self.mode == "menu":
            hint = "  \u2191\u2193 navigate    Enter run    Esc cancel"
        elif self.mode == "settings":
            hint = "  type to search    \u2191\u2193 navigate    Enter change    Esc cancel"
        else:
            hint = "  \u2191\u2193 navigate    Enter run    Esc cancel"
        return [("class:picker.footer", hint)]

    def _render_results(self) -> StyleAndTextTuples:
        fragments: StyleAndTextTuples = []
        visible = self._results_rows()
        if not self.filtered:
            fragments.append(("class:picker.empty", "   No matching results\n"))
            for _ in range(visible - 1):
                fragments.append(("class:picker", "\n"))
            return fragments

        start = 0
        if self.index >= visible:
            start = min(self.index - visible + 1, max(0, len(self.filtered) - visible))

        def mouse_handler(row: int) -> Callable:
            def handler(event):
                if event.event_type == MouseEventType.MOUSE_UP:
                    self.index = row
                    self._accept()
                elif event.event_type == MouseEventType.MOUSE_DOWN:
                    self.index = row
                    self.app.invalidate()

            return handler

        for row in range(visible):
            absolute = start + row
            if absolute >= len(self.filtered):
                fragments.append(("class:picker", "\n"))
                continue
            item, positions = self.filtered[absolute]
            selected = absolute == self.index
            item_class = "picker.menu.item" if self.mode == "menu" else "picker.item"
            base = f"class:{item_class}.selected" if selected else f"class:{item_class}"
            row_fragments: StyleAndTextTuples = self._highlight_label(
                item.label, positions, base, selected
            )
            if item.description:
                pad = max(2, 44 - len(item.label))
                desc_style = (
                    f"class:{item_class}.selected.description"
                    if selected
                    else f"class:{item_class}.description"
                )
                row_fragments.append((desc_style, " " * pad + item.description))
            if item.keys:
                key_style = (
                    f"class:{item_class}.selected.key"
                    if selected
                    else f"class:{item_class}.key"
                )
                row_fragments.append((key_style, "   " + item.keys))
            handler = mouse_handler(absolute)
            fragments.extend(
                (fragment[0], fragment[1], handler, *fragment[2:])
                for fragment in row_fragments
            )
            fragments.append(("class:picker", "\n"))
        return fragments

    @staticmethod
    def _highlight_label(
        label: str,
        positions: list[int],
        base: str,
        selected: bool,
    ) -> StyleAndTextTuples:
        match_style = (
            "class:picker.match.selected" if selected else "class:picker.match"
        )
        if not positions:
            return [(base, label)]
        fragments: StyleAndTextTuples = []
        position_set = set(positions)
        current = ""
        buffer = ""
        for index, char in enumerate(label):
            style = f"{base} {match_style}" if index in position_set else base
            if style != current and buffer:
                fragments.append((current, buffer))
                buffer = ""
            current = style
            buffer += char
        if buffer:
            fragments.append((current, buffer))
        return fragments

    # -------------------------------------------------------------- selection
    def _move(self, delta: int) -> None:
        if not self.filtered:
            return
        self.index = max(0, min(self.index + delta, len(self.filtered) - 1))
        self.app.invalidate()

    def _accept(self) -> None:
        if not self.filtered:
            if self.mode == "files":
                self.close()
            return
        item = self.filtered[self.index][0]
        action = item.action
        self.close()
        if action is not None:
            action()

    def _complete_query(self) -> None:
        if not self.filtered:
            return
        item = self.filtered[self.index][0]
        target = item.label
        self.input_buffer.text = target
        self.input_buffer.cursor_position = len(target)

    # --------------------------------------------------------------- bindings
    @property
    def keys(self) -> KeyBindings:
        if not hasattr(self, "_keys"):
            keys = KeyBindings()

            @keys.add("up")
            @keys.add("c-p")
            def _up(event) -> None:
                self._move(-1)

            @keys.add("down")
            @keys.add("c-n")
            def _down(event) -> None:
                self._move(1)

            @keys.add("pageup")
            def _page_up(event) -> None:
                self._move(-RESULTS_ROWS)

            @keys.add("pagedown")
            def _page_down(event) -> None:
                self._move(RESULTS_ROWS)

            @keys.add("enter")
            def _enter(event) -> None:
                self._accept()

            @keys.add("escape")
            @keys.add("c-c")
            def _escape(event) -> None:
                self.close()

            @keys.add("tab")
            def _tab(event) -> None:
                if self.mode == "settings":
                    self._move_settings_section(1)
                else:
                    self._complete_query()

            @keys.add("s-tab")
            def _shift_tab(event) -> None:
                if self.mode == "settings":
                    self._move_settings_section(-1)

            @keys.add("left")
            def _left(event) -> None:
                if self.mode == "settings":
                    self._move_settings_section(-1)

            @keys.add("right")
            def _right(event) -> None:
                if self.mode == "settings":
                    self._move_settings_section(1)

            @keys.add(Keys.Any, filter=has_selection)
            def _type_over_selection(event) -> None:
                if not event.data or not event.data.isprintable():
                    return
                event.current_buffer.cut_selection()
                event.current_buffer.insert_text(event.data)

            self._keys = keys
        return self._keys

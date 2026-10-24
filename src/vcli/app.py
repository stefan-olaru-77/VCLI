"""The vcli application: layout, commands, key bindings and document state."""

from __future__ import annotations

import shutil
from collections.abc import Sequence
from pathlib import Path

from prompt_toolkit import Application
from prompt_toolkit.application import get_app
from prompt_toolkit.clipboard import InMemoryClipboard
from prompt_toolkit.cursor_shapes import CursorShape
from prompt_toolkit.filters import Condition, has_completions, has_selection
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.keys import Keys
from prompt_toolkit.layout import Layout
from prompt_toolkit.layout.containers import (
    ConditionalContainer,
    DynamicContainer,
    FloatContainer,
    HSplit,
    VSplit,
    Window,
)
from prompt_toolkit.layout.controls import FormattedTextControl
from prompt_toolkit.layout.dimension import Dimension

from . import __version__
from .commands import CommandRegistry
from .config import Config
from .fileio import (
    BinaryFileError,
    FileTooLargeError,
    read_file,
    write_file,
)
from .theme import build_style, resolve_theme_key
from .ui.editor import EditorPane
from .ui.find import FindBar
from .ui.menubar import MenuBarControl
from .ui.picker import PickerItem, PickerOverlay
from .ui.statusbar import StatusBar
from .ui.tabs import TabBarControl
from .ui.tree import FileTreeControl
from .vcs import git_branch
from .workspace import Workspace


class EditorApp:
    def __init__(
        self,
        files: Sequence[str | Path] = (),
        config: Config | None = None,
        workspace_root: str | Path | None = None,
        *,
        config_file: str | Path | None = None,
        input=None,
        output=None,
    ) -> None:
        self.config = config or Config.load()
        self.config_file = Path(config_file).expanduser() if config_file else None
        root = Path(workspace_root).expanduser() if workspace_root else Path.cwd()
        self.workspace = Workspace(root, show_hidden=self.config.show_hidden_files)
        self.git_branch = git_branch(self.workspace.root)

        self.documents: list[EditorPane] = []
        self.active_index = -1
        self.message = ""
        self.message_error = False
        self._untitled_counter = 0
        self._quitting = False

        self.commands = CommandRegistry()
        self.find = FindBar(self)
        self.picker = PickerOverlay(self)
        self.tabbar = TabBarControl(self)
        self.menubar = MenuBarControl(self)
        self.tree_control = FileTreeControl(self)
        self.tree_window: Window | None = None
        self.statusbar = StatusBar(self)
        self.keys = KeyBindings()

        self._build_controls()
        self._register_commands()
        self._register_keys()

        self.layout = self._build_layout()
        self.application = Application(
            layout=self.layout,
            key_bindings=self.keys,
            style=build_style(self.config.theme),
            include_default_pygments_style=False,
            full_screen=True,
            mouse_support=Condition(lambda: self.config.mouse),
            clipboard=InMemoryClipboard(),
            cursor=CursorShape.BLINKING_BLOCK,
            input=input,
            output=output,
            on_reset=self._on_reset,
        )

        for path in files:
            self.open_path(path)

        if self.documents:
            self.activate(0)
        else:
            self.focus_editor()

    # ------------------------------------------------------------- properties
    @property
    def active_pane(self) -> EditorPane | None:
        if 0 <= self.active_index < len(self.documents):
            return self.documents[self.active_index]
        return None

    @property
    def terminal_width(self) -> int:
        try:
            return get_app().output.get_size().columns
        except Exception:
            return shutil.get_terminal_size((80, 24)).columns

    @property
    def terminal_height(self) -> int:
        try:
            return get_app().output.get_size().rows
        except Exception:
            return shutil.get_terminal_size((80, 24)).lines

    def run(self) -> None:
        self.application.run()

    # ------------------------------------------------------------ construction
    def _build_controls(self) -> None:
        self.welcome_window = Window(
            FormattedTextControl(self._welcome_text),
            style="class:welcome",
        )
        self.editor_host = DynamicContainer(self._editor_container)

    def _build_layout(self) -> Layout:
        config = self.config
        self.menubar_window = Window(self.menubar, height=1)
        self.menubar_separator = Window(
            height=1, char="\u2500", style="class:chrome.separator"
        )
        self.tabbar_window = ConditionalContainer(
            Window(self.tabbar, height=1), Condition(lambda: self.config.show_tab_bar)
        )
        self.tabbar_separator = ConditionalContainer(
            Window(height=1, char="\u2500", style="class:chrome.separator"),
            Condition(lambda: self.config.show_tab_bar),
        )

        header = Window(
            FormattedTextControl(
                lambda: [("class:sidebar.title", " EXPLORER")]
            ),
            height=1,
            width=Dimension.exact(config.sidebar_width),
            ignore_content_width=True,
            style="class:sidebar",
        )
        root_label = Window(
            FormattedTextControl(self._root_label),
            height=1,
            width=Dimension.exact(config.sidebar_width),
            ignore_content_width=True,
            style="class:sidebar",
        )
        self.tree_window = Window(
            self.tree_control,
            width=Dimension.exact(config.sidebar_width),
            style="class:sidebar",
        )
        sidebar = HSplit([header, root_label, self.tree_window])
        sidebar_container = ConditionalContainer(
            sidebar,
            Condition(
                lambda: self.config.show_sidebar and self.workspace.root.is_dir()
            ),
        )
        separator = Window(width=1, char="\u2502", style="class:separator")
        find_container = ConditionalContainer(
            self.find.container, Condition(lambda: self.find.active)
        )
        body = VSplit(
            [
                sidebar_container,
                separator,
                HSplit(
                    [
                        self.tabbar_window,
                        self.tabbar_separator,
                        find_container,
                        self.editor_host,
                    ]
                ),
            ],
            padding=0,
        )
        root = HSplit(
            [
                self.menubar_window,
                self.menubar_separator,
                body,
                ConditionalContainer(
                    self.statusbar.container,
                    Condition(lambda: self.config.show_status_bar),
                ),
            ]
        )
        floats = FloatContainer(
            content=root,
            floats=[self.picker.shadow_float, self.picker.float],
        )
        focused = self.tree_window if not self.documents else None
        return Layout(floats, focused_element=focused)

    def _editor_container(self):
        pane = self.active_pane
        return pane.window if pane is not None else self.welcome_window

    def _root_label(self):
        return [
            (
                "class:sidebar.title.root",
                f" {self.workspace.root.name.upper() or str(self.workspace.root)}",
            )
        ]

    def _welcome_text(self):
        return [
            ("class:welcome", "\n\n   "),
            ("class:welcome.title", "vcli"),
            ("class:welcome.muted", f"  {__version__}  \u2014 a VSCode-like editor for the terminal\n"),
            ("class:welcome.muted", "   " + "\u2500" * 52 + "\n\n"),
            ("class:welcome.key", "   Ctrl+P"),
            ("class:welcome", "  Quick open          "),
            ("class:welcome.key", "F1"),
            ("class:welcome", "      Command palette\n"),
            ("class:welcome.key", "   Ctrl+S"),
            ("class:welcome", "  Save                "),
            ("class:welcome.key", "Ctrl+B"),
            ("class:welcome", "  Toggle sidebar\n"),
            ("class:welcome.key", "   Ctrl+F"),
            ("class:welcome", "  Find                "),
            ("class:welcome.key", "Ctrl+R"),
            ("class:welcome", "  Replace\n"),
            ("class:welcome.key", "   Ctrl+G"),
            ("class:welcome", "  Go to line          "),
            ("class:welcome.key", "Ctrl+Q"),
            ("class:welcome", "  Quit\n\n"),
            ("class:welcome.muted", "   No open editors. Press Ctrl+N for a new file or Ctrl+P to open one.\n"),
        ]

    # ---------------------------------------------------------------- documents
    def _unique_title(self) -> str:
        self._untitled_counter += 1
        return f"Untitled-{self._untitled_counter}"

    def new_file(self) -> None:
        pane = EditorPane(self, self._unique_title())
        self.documents.append(pane)
        self.activate(len(self.documents) - 1)
        self.notify("New file")

    def open_path(self, path: str | Path) -> EditorPane | None:
        candidate = Path(path).expanduser()
        if not candidate.is_absolute():
            candidate = Path.cwd() / candidate
        try:
            resolved = candidate.resolve()
        except OSError:
            resolved = candidate

        for index, pane in enumerate(self.documents):
            if pane.path is not None and pane.path == resolved:
                self.activate(index)
                return pane

        if resolved.is_dir():
            self.notify(f"{resolved.name} is a directory", error=True)
            return None
        if not resolved.exists():
            pane = EditorPane(self, title=resolved.name, text="", path=resolved)
            self.documents.append(pane)
            self.activate(len(self.documents) - 1)
            self.notify(f"New file: {resolved.name}")
            return pane
        try:
            loaded = read_file(resolved)
        except BinaryFileError:
            self.notify(f"{resolved.name} looks binary; not opening", error=True)
            return None
        except FileTooLargeError as exc:
            self.notify(str(exc), error=True)
            return None
        except OSError as exc:
            self.notify(f"Could not open {resolved.name}: {exc}", error=True)
            return None

        pane = EditorPane(
            self,
            title=resolved.name,
            text=loaded.text,
            path=resolved,
            loaded=loaded,
        )
        self.documents.append(pane)
        self.activate(len(self.documents) - 1)
        if loaded.warnings:
            self.notify(" ".join(loaded.warnings))
        if not pane.highlight_enabled:
            self.notify("Large file: syntax highlighting disabled")
        self.workspace.reveal(resolved)
        return pane

    def create_file(self, path: Path) -> None:
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            if not path.exists():
                write_file(path, "")
        except OSError as exc:
            self.notify(f"Could not create file: {exc}", error=True)
            return
        self.workspace.reload()
        self.open_path(path)
        self.notify(f"Created {self.workspace.relative(path)}")

    def open_folder(self) -> None:
        def accept(value: str) -> None:
            candidate = Path(value.strip()).expanduser() if value.strip() else Path.cwd()
            try:
                candidate = candidate.resolve()
            except OSError:
                pass
            if not candidate.is_dir():
                self.notify(f"Folder not found: {candidate}", error=True)
                return
            if any(pane.dirty for pane in self.documents):
                self.notify("Save or close dirty files before opening a folder", error=True)
                return
            self.documents.clear()
            self.active_index = -1
            self.workspace = Workspace(candidate, show_hidden=self.workspace.show_hidden)
            self.git_branch = git_branch(self.workspace.root)
            self.tree_control.scroll = 0
            self.focus_editor()
            self.notify(f"Opened folder {candidate}")

        initial = str(self.workspace.root)
        self.picker.open_input("Open Folder", initial, accept)
        # A folder path is a suggestion, not a value the user should have to
        # erase character by character before typing a different path.
        self.picker.input_buffer.cursor_position = 0
        self.picker.input_buffer.start_selection()
        self.picker.input_buffer.cursor_position = len(initial)

    def open_menu(self, name: str, anchor_x: int = 0) -> None:
        if name == "file":
            items = [
                PickerItem("New File", "File", "Ctrl+N", self.new_file),
                PickerItem("Open File...", "File", "Ctrl+O", self.picker.open_files),
                PickerItem("Open Folder...", "File", "Ctrl+K Ctrl+O", self.open_folder),
                PickerItem("Settings...", "Preferences", "F1", self.open_settings),
            ]
        else:
            items = [
                PickerItem("Undo", "Edit", "Ctrl+Z", lambda: self._editor_op("undo")),
                PickerItem("Redo", "Edit", "Ctrl+Y", lambda: self._editor_op("redo")),
                PickerItem("Cut", "Edit", "Ctrl+X", lambda: self._editor_op("cut")),
                PickerItem("Copy", "Edit", "Ctrl+C", lambda: self._editor_op("copy")),
                PickerItem("Paste", "Edit", "Ctrl+V", lambda: self._editor_op("paste")),
                PickerItem("Emmet: Expand Abbreviation", "Edit", "Ctrl+Alt+E", lambda: self._editor_op("expand_abbreviation")),
            ]
        self.picker.open_menu(name.title(), items, anchor_x=anchor_x)

    def activate(self, index: int) -> None:
        if not 0 <= index < len(self.documents):
            return
        self.active_index = index
        pane = self.documents[index]
        if self.picker.active:
            self.layout.focus(self.picker.input_control)
        elif self.find.active:
            self.layout.focus(self.find.query_control)
        else:
            self.layout.focus(pane.buffer)
        if self.find.active:
            self.find.refresh()
        if pane.path is not None:
            self.workspace.reveal(pane.path)
        self.invalidate()

    def next_tab(self, delta: int = 1) -> None:
        if len(self.documents) < 2:
            return
        self.activate((self.active_index + delta) % len(self.documents))

    def request_close(self, index: int | None = None) -> None:
        index = self.active_index if index is None else index
        if not 0 <= index < len(self.documents):
            return
        pane = self.documents[index]

        def close_now() -> None:
            self._close(index)

        if not pane.dirty:
            close_now()
            return
        self.picker.confirm(
            "Unsaved changes",
            f"'{pane.display_name}' has unsaved changes.",
            [
                ("Save", lambda: self._save_then_close(index)),
                ("Don't Save", close_now),
                ("Cancel", lambda: None),
            ],
        )

    def _save_then_close(self, index: int) -> None:
        if not 0 <= index < len(self.documents):
            return
        pane = self.documents[index]
        self.active_index = index
        if pane.save():
            self._close(index, force=True)

    def _close(self, index: int, force: bool = False) -> None:
        if not 0 <= index < len(self.documents):
            return
        pane = self.documents[index]
        if pane.dirty and not force:
            self.request_close(index)
            return
        del self.documents[index]
        if not self.documents:
            self.active_index = -1
            self.focus_editor()
        else:
            self.active_index = min(index, len(self.documents) - 1)
            self.activate(self.active_index)
        self.invalidate()

    def focus_editor(self) -> None:
        pane = self.active_pane
        if pane is not None:
            self.layout.focus(pane.buffer)
        elif self.tree_window is not None and self.config.show_sidebar:
            self.layout.focus(self.tree_window)
        self.invalidate()

    # ------------------------------------------------------------------ commands
    def save_active(self, force: bool = False) -> None:
        pane = self.active_pane
        if pane is None:
            return
        if pane.save(force=force):
            self.notify(f"Saved {pane.display_name}")

    def save_as(self) -> None:
        pane = self.active_pane
        if pane is None:
            return
        if pane.path is not None:
            initial = str(pane.path)
        else:
            initial = str(self.workspace.root / (pane.title.lower() + ".txt"))

        def accept(value: str) -> None:
            if value.strip():
                if pane.save(Path(value.strip()), force=True):
                    self.notify(f"Saved {pane.display_name}")
                    self.workspace.reload()

        self.picker.open_input("Save As", initial, accept)

    def save_all(self) -> None:
        for pane in list(self.documents):
            if pane.dirty and pane.path is not None:
                pane.save()
        self.notify("All files saved")

    def quit_app(self) -> None:
        dirty = [pane for pane in self.documents if pane.dirty]
        if not dirty or not self.config.confirm_exit:
            self._do_quit()
            return

        def save_all_and_quit() -> None:
            for pane in dirty:
                if pane.path is None:
                    self.notify("Save untitled files first", error=True)
                    return
                if not pane.save():
                    return
            self._do_quit()

        self.picker.confirm(
            "Quit",
            f"{len(dirty)} unsaved file(s).",
            [
                ("Save All and Quit", save_all_and_quit),
                ("Quit Without Saving", self._do_quit),
                ("Cancel", lambda: None),
            ],
        )

    def _do_quit(self) -> None:
        self._quitting = True
        self.config.save(self.config_file)
        self.application.exit()

    def toggle_sidebar(self) -> None:
        self.config.show_sidebar = not self.config.show_sidebar
        self.invalidate()

    def toggle_word_wrap(self) -> None:
        self.config.word_wrap = not self.config.word_wrap
        self.notify(f"Word wrap: {'on' if self.config.word_wrap else 'off'}")

    def toggle_line_numbers(self) -> None:
        self.config.line_numbers = not self.config.line_numbers
        self.notify(f"Line numbers: {'on' if self.config.line_numbers else 'off'}")

    def toggle_relative_numbers(self) -> None:
        self.config.relative_line_numbers = not self.config.relative_line_numbers
        self.notify(
            f"Relative line numbers: {'on' if self.config.relative_line_numbers else 'off'}"
        )

    def toggle_mouse(self) -> None:
        self.config.mouse = not self.config.mouse
        self.notify(f"Mouse: {'on' if self.config.mouse else 'off'}")

    def toggle_hidden_files(self) -> None:
        self.workspace.show_hidden = not self.workspace.show_hidden
        self.config.show_hidden_files = self.workspace.show_hidden
        self.workspace.reload()
        self.notify(f"Hidden files: {'shown' if self.workspace.show_hidden else 'hidden'}")

    def open_settings(self) -> None:
        """Open the searchable, VSCode-like settings quick panel."""
        config = self.config

        def toggle(field: str) -> None:
            setattr(config, field, not getattr(config, field))
            if field == "show_hidden_files":
                self.workspace.show_hidden = config.show_hidden_files
                self.workspace.reload()
            if field in {"detect_indentation", "detect_language", "use_spaces"}:
                for pane in self.documents:
                    pane.refresh_preferences()
            config.save(self.config_file)
            self.invalidate()
            self.open_settings()

        def cycle_line_height() -> None:
            config.line_height = config.line_height % 3 + 1
            config.save(self.config_file)
            self.invalidate()
            self.open_settings()

        def cycle_tab_size() -> None:
            values = (2, 4, 8)
            config.tab_size = values[(values.index(config.tab_size) + 1) % len(values)] if config.tab_size in values else 4
            for pane in self.documents:
                if not config.detect_indentation:
                    pane.refresh_preferences()
            config.save(self.config_file)
            self.invalidate()
            self.open_settings()

        def bool_item(label: str, field: str) -> PickerItem:
            value = "On" if getattr(config, field) else "Off"
            return PickerItem(
                label,
                description=value,
                action=lambda f=field: toggle(f),
                search_text=f"{label} {value}",
            )

        def theme_item() -> PickerItem:
            return PickerItem(
                "Theme: Color Theme",
                description=config.theme,
                action=self.picker.open_themes,
                search_text=f"Theme Color Theme {config.theme}",
            )

        items = [
            PickerItem(
                "Editor: Tab Size",
                description=str(config.tab_size),
                action=cycle_tab_size,
                search_text="Editor Tab Size",
            ),
            bool_item("Editor: Use Spaces", "use_spaces"),
            bool_item("Editor: Detect Indentation", "detect_indentation"),
            bool_item("Editor: Detect Language", "detect_language"),
            bool_item("Editor: Highlight Current Line", "highlight_current_line"),
            PickerItem(
                "Editor: Line Height",
                description=str(config.line_height),
                action=cycle_line_height,
                search_text="Editor Line Height",
            ),
            bool_item("Editor: Word Wrap", "word_wrap"),
            bool_item("Editor: Line Numbers", "line_numbers"),
            bool_item("Editor: Relative Line Numbers", "relative_line_numbers"),
            bool_item("Editor: Auto Indent", "auto_indent"),
            bool_item("Editor: Auto Close Brackets", "auto_close_brackets"),
            bool_item("Editor: Auto Closing Quotes", "auto_closing_quotes"),
            bool_item("Editor: Auto Closing Comments", "auto_closing_comments"),
            bool_item("Editor: Bracket Pair Colorization", "bracket_pair_colorization"),
            bool_item("Editor: Color Decorators", "color_decorators"),
            bool_item("Editor: Format On Save", "format_on_save"),
            bool_item("Editor: Code Folding", "code_folding"),
            bool_item("Files: Show Hidden Files", "show_hidden_files"),
            bool_item("Workbench: Show Sidebar", "show_sidebar"),
            bool_item("Workbench: Show Tab Bar", "show_tab_bar"),
            bool_item("Workbench: Show Status Bar", "show_status_bar"),
            bool_item("Workbench: Mouse Support", "mouse"),
            bool_item("Files: Confirm Exit", "confirm_exit"),
            theme_item(),
        ]
        self.picker.open_menu("Settings", items, searchable=True)

    def apply_theme(self, name: str) -> None:
        name = resolve_theme_key(name)
        self.config.theme = name
        self.application.style = build_style(name)
        self.notify(f"Theme: {name}")
        self.invalidate()

    def goto_line(self, number: int) -> None:
        pane = self.active_pane
        if pane is None:
            return
        document = pane.buffer.document
        row = max(0, min(number - 1, document.line_count - 1))
        pane.buffer.exit_selection()
        pane.buffer.cursor_position = document.translate_row_col_to_index(row, 0)
        self.invalidate()

    def show_shortcuts(self) -> None:
        text = SHORTCUTS_TEXT.strip("\n")
        pane = EditorPane(self, "Keyboard Shortcuts", text=text)
        pane.saved_text = text
        pane.dirty = False
        pane.highlight_enabled = False
        self.documents.append(pane)
        self.activate(len(self.documents) - 1)

    def show_about(self) -> None:
        self.notify(f"vcli {__version__} \u2014 VSCode-like editor for the terminal")

    def reload_active(self) -> None:
        pane = self.active_pane
        if pane is None:
            return
        if pane.dirty:
            self.picker.confirm(
                "Reload",
                f"Discard unsaved changes in '{pane.display_name}'?",
                [
                    ("Reload from Disk", pane.reload),
                    ("Cancel", lambda: None),
                ],
            )
        else:
            pane.reload()
        self.invalidate()

    # ------------------------------------------------------------------- hooks
    def notify(self, message: str, error: bool = False) -> None:
        self.message = message
        self.message_error = error
        self.invalidate()

    def invalidate(self) -> None:
        application = getattr(self, "application", None)
        if application is not None:
            application.invalidate()

    def on_editor_text_changed(self, pane: EditorPane) -> None:
        if self.find.active and pane is self.active_pane:
            self.find.refresh(jump=False)
        self.invalidate()

    def on_saved(self, pane: EditorPane) -> None:
        self.workspace.reload()
        self.git_branch = git_branch(self.workspace.root)
        self.invalidate()

    def set_clipboard(self, text: str) -> None:
        self.application.clipboard.set_text(text)
        self.notify(f"{len(text.splitlines()) or 1} line(s) copied")

    def get_clipboard(self) -> str:
        return self.application.clipboard.get_data().text

    def _on_reset(self, app: Application) -> None:
        self.config.save(self.config_file)

    # --------------------------------------------------------------- commands
    def _register_commands(self) -> None:
        register = self.commands.register

        register("file.new", "File: New File", "File", self.new_file, "Ctrl+N")
        register("file.open", "File: Open File...", "File", self.picker.open_files, "Ctrl+O")
        register("file.openFolder", "File: Open Folder...", "File", self.open_folder, "Ctrl+K Ctrl+O")
        register("file.save", "File: Save", "File", self.save_active, "Ctrl+S")
        register("file.saveAs", "File: Save As...", "File", self.save_as)
        register("file.saveAll", "File: Save All", "File", self.save_all)
        register("file.close", "File: Close Editor", "File", self.request_close, "Ctrl+W")
        register("file.reload", "File: Reload from Disk", "File", self.reload_active)
        register("file.quit", "File: Quit", "File", self.quit_app, "Ctrl+Q")

        register("edit.undo", "Edit: Undo", "Edit", lambda: self._editor_op("undo"), "Ctrl+Z")
        register("edit.redo", "Edit: Redo", "Edit", lambda: self._editor_op("redo"), "Ctrl+Y")
        register("edit.cut", "Edit: Cut", "Edit", lambda: self._editor_op("cut"), "Ctrl+X")
        register("edit.copy", "Edit: Copy", "Edit", lambda: self._editor_op("copy"), "Ctrl+C")
        register("edit.paste", "Edit: Paste", "Edit", lambda: self._editor_op("paste"), "Ctrl+V")
        register("edit.emmet", "Emmet: Expand Abbreviation", "Edit", lambda: self._editor_op("expand_abbreviation"), "Ctrl+Alt+E")
        register("edit.selectAll", "Edit: Select All", "Edit", lambda: self._editor_op("select_all"), "Ctrl+A")
        register("edit.duplicate", "Edit: Duplicate Line", "Edit", lambda: self._editor_op("duplicate_line"), "Ctrl+D")
        register("edit.deleteLine", "Edit: Delete Line", "Edit", lambda: self._editor_op("delete_line"), "Ctrl+K")
        register("edit.moveUp", "Edit: Move Line Up", "Edit", lambda: self._editor_op("move_line", -1), "Ctrl+Up")
        register("edit.moveDown", "Edit: Move Line Down", "Edit", lambda: self._editor_op("move_line", 1), "Ctrl+Down")
        register("edit.comment", "Edit: Toggle Line Comment", "Edit", lambda: self._editor_op("toggle_comment"), "Ctrl+/")
        register("edit.indent", "Edit: Indent", "Edit", lambda: self._editor_op("indent"), "Tab")
        register("edit.outdent", "Edit: Outdent", "Edit", lambda: self._editor_op("outdent"), "Shift+Tab")
        register("edit.find", "Edit: Find", "Edit", lambda: self.find.open(False), "Ctrl+F")
        register("edit.replace", "Edit: Replace", "Edit", lambda: self.find.open(True), "Ctrl+R")
        register("edit.gotoLine", "Edit: Go to Line...", "Edit", self.picker.open_line, "Ctrl+G")

        register("view.commandPalette", "View: Command Palette", "View", self.picker.open_commands, "F1")
        register("view.quickOpen", "View: Go to File...", "View", self.picker.open_files, "Ctrl+P")
        register("view.sidebar", "View: Toggle Sidebar", "View", self.toggle_sidebar, "Ctrl+B")
        register("view.wordWrap", "View: Toggle Word Wrap", "View", self.toggle_word_wrap, "F10")
        register("view.lineNumbers", "View: Toggle Line Numbers", "View", self.toggle_line_numbers)
        register("view.relativeNumbers", "View: Toggle Relative Line Numbers", "View", self.toggle_relative_numbers)
        register("view.hiddenFiles", "View: Toggle Hidden Files", "View", self.toggle_hidden_files)
        register("view.mouse", "View: Toggle Mouse Support", "View", self.toggle_mouse)
        register("view.toggleFold", "View: Toggle Code Folding", "View", lambda: self._editor_op("toggle_fold"), "Ctrl+F9")
        register("view.theme", "Preferences: Color Theme", "View", self.picker.open_themes)
        register("preferences.settings", "Preferences: Open Settings", "Preferences", self.open_settings)

        register("go.nextTab", "Go: Next Editor", "Go", lambda: self.next_tab(1), "Ctrl+PageDown")
        register("go.prevTab", "Go: Previous Editor", "Go", lambda: self.next_tab(-1), "Ctrl+PageUp")
        register("go.nextMatch", "Go: Next Match", "Go", lambda: self.find.next_match(1), "F3")
        register("go.prevMatch", "Go: Previous Match", "Go", lambda: self.find.next_match(-1), "Shift+F3")
        register("go.explorer", "Go: Focus Explorer", "Go", lambda: self.layout.focus(self.tree_window) if self.tree_window else None)

        register("help.shortcuts", "Help: Keyboard Shortcuts", "Help", self.show_shortcuts)
        register("help.about", "Help: About vcli", "Help", self.show_about)

    def _editor_op(self, name: str, *args) -> None:
        pane = self.active_pane
        if pane is None:
            return
        method = getattr(pane, name)
        method(*args)
        self.invalidate()

    # -------------------------------------------------------------- key bindings
    def _editor_focused(self) -> bool:
        pane = self.active_pane
        return pane is not None and self.layout.current_control is pane.control

    def _register_keys(self) -> None:
        keys = self.keys
        editor = Condition(self._editor_focused)
        auto_pairs = Condition(lambda: self.config.auto_close_brackets)
        auto_quotes = Condition(lambda: self.config.auto_closing_quotes)

        # File / tab management (global).
        @keys.add("c-s")
        def _save(event) -> None:
            self.save_active()

        @keys.add("c-n")
        def _new(event) -> None:
            self.new_file()

        @keys.add("c-o")
        def _open(event) -> None:
            self.picker.open_files()

        @keys.add("c-k", "c-o")
        def _open_folder(event) -> None:
            self.open_folder()

        @keys.add("c-w")
        def _close(event) -> None:
            self.request_close()

        @keys.add("c-q")
        def _quit(event) -> None:
            self.quit_app()

        @keys.add("c-pagedown")
        def _next_tab(event) -> None:
            self.next_tab(1)

        @keys.add("c-pageup")
        def _prev_tab(event) -> None:
            self.next_tab(-1)

        # Navigation / overlays (global).
        @keys.add("f1")
        def _palette(event) -> None:
            self.picker.open_commands()

        @keys.add("c-p")
        def _quick_open(event) -> None:
            self.picker.open_files()

        @keys.add("c-g")
        def _goto(event) -> None:
            self.picker.open_line()

        @keys.add("c-f")
        def _find(event) -> None:
            self.find.open(False)

        @keys.add("c-r")
        def _replace(event) -> None:
            self.find.open(True)

        @keys.add("f3")
        def _next_match(event) -> None:
            if not self.find.active:
                self.find.open(False)
            else:
                self.find.next_match(1)

        @keys.add("f4")
        def _prev_match(event) -> None:
            if not self.find.active:
                self.find.open(False)
            else:
                self.find.next_match(-1)

        @keys.add("c-b")
        def _sidebar(event) -> None:
            self.toggle_sidebar()

        @keys.add("f10")
        def _wrap(event) -> None:
            self.toggle_word_wrap()

        @keys.add("f9")
        def _menu(event) -> None:
            self.open_menu("file")

        @keys.add("c-f9", filter=editor)
        def _fold(event) -> None:
            pane = self.active_pane
            if pane is not None:
                pane.toggle_fold()

        @keys.add("escape")
        def _escape(event) -> None:
            if self.picker.active:
                self.picker.close()
            elif self.find.active:
                self.find.close()
            elif self._editor_focused():
                pane = self.active_pane
                if pane is not None:
                    pane.buffer.exit_selection()
            else:
                self.focus_editor()

        # Editing (editor focused only).
        @keys.add("c-z", filter=editor)
        def _undo(event) -> None:
            pane = self.active_pane
            if pane is not None:
                pane.undo()

        @keys.add("c-y", filter=editor)
        def _redo(event) -> None:
            pane = self.active_pane
            if pane is not None:
                pane.redo()

        @keys.add("c-a", filter=editor)
        def _select_all(event) -> None:
            pane = self.active_pane
            if pane is not None:
                pane.select_all()

        @keys.add("c-c", filter=editor)
        def _copy(event) -> None:
            pane = self.active_pane
            if pane is not None:
                pane.copy()

        @keys.add("c-x", filter=editor)
        def _cut(event) -> None:
            pane = self.active_pane
            if pane is not None:
                pane.cut()

        @keys.add("c-v", filter=editor)
        def _paste(event) -> None:
            pane = self.active_pane
            if pane is not None:
                pane.paste()

        # Terminals commonly encode Ctrl+Alt+E as Escape followed by Ctrl+E.
        @keys.add("escape", "c-e", filter=editor)
        def _emmet(event) -> None:
            pane = self.active_pane
            if pane is not None:
                pane.expand_abbreviation()

        @keys.add("c-d", filter=editor)
        def _duplicate(event) -> None:
            pane = self.active_pane
            if pane is not None:
                pane.duplicate_line()

        @keys.add("c-k", filter=editor)
        def _delete_line(event) -> None:
            pane = self.active_pane
            if pane is not None:
                pane.delete_line()

        @keys.add("c-up", filter=editor)
        def _move_up(event) -> None:
            pane = self.active_pane
            if pane is not None:
                pane.move_line(-1)

        @keys.add("c-down", filter=editor)
        def _move_down(event) -> None:
            pane = self.active_pane
            if pane is not None:
                pane.move_line(1)

        @keys.add("c-s-up", filter=editor)
        @keys.add("c-s-down", filter=editor)
        def _duplicate_alt(event) -> None:
            pane = self.active_pane
            if pane is not None:
                pane.duplicate_line()

        @keys.add("c-_", filter=editor)
        def _comment(event) -> None:
            pane = self.active_pane
            if pane is not None:
                pane.toggle_comment()

        @keys.add("tab", filter=editor & ~has_completions)
        def _indent(event) -> None:
            pane = self.active_pane
            if pane is not None:
                pane.indent()

        @keys.add("s-tab", filter=editor)
        def _outdent(event) -> None:
            pane = self.active_pane
            if pane is not None:
                pane.outdent()

        @keys.add("enter", filter=editor)
        def _enter(event) -> None:
            pane = self.active_pane
            if pane is not None:
                pane.newline()

        @keys.add("backspace", filter=editor)
        def _backspace(event) -> None:
            pane = self.active_pane
            if pane is None:
                return
            buffer = pane.buffer
            text = buffer.text
            cursor = buffer.cursor_position
            if list(buffer.document.selection_ranges()):
                pane.replace_selection("")
                return
            previous = text[cursor - 1 : cursor]
            following = text[cursor : cursor + 1]
            bracket_pair = (previous, following) in {
                ("(", ")"), ("[", "]"), ("{", "}"),
            }
            quote_pair = (previous, following) in {
                ('"', '"'), ("'", "'"), ("`", "`"),
            }
            if (bracket_pair and auto_pairs()) or (quote_pair and auto_quotes()):
                    pane.set_text(
                        text[: cursor - 1] + text[cursor + 1 :], cursor - 1
                    )
                    return
            buffer.delete_before_cursor()

        @keys.add("c-space", filter=editor)
        def _complete(event) -> None:
            event.current_buffer.start_completion(select_first=False)

        # Typing over a selection replaces it (prompt_toolkit appends by
        # default). Explicit bindings such as brackets and Enter still win,
        # because wildcard bindings are matched last.
        @keys.add(Keys.Any, filter=editor & has_selection & ~has_completions)
        def _type_over_selection(event) -> None:
            pane = self.active_pane
            if pane is None or not event.data or not event.data.isprintable():
                return
            pane.replace_selection(event.data)

        # Auto-close pairs.
        for opening, closing in [
            ("(", ")"),
            ("[", "]"),
            ("{", "}"),
            ('"', '"'),
            ("'", "'"),
            ("`", "`"),
        ]:

            def _insert(event, opening=opening, closing=closing) -> None:
                pane = self.active_pane
                if pane is None:
                    return
                selection = pane.selection()
                if not selection.empty:
                    pane.begin_edit()
                    pane.replace_selection(
                        opening + pane.selected_text() + closing
                    )
                    return
                text = pane.buffer.text
                cursor = pane.buffer.cursor_position
                if text[cursor : cursor + 1] == closing:
                    pane.buffer.cursor_position = cursor + 1
                    return
                pane.set_text(
                    text[:cursor] + opening + closing + text[cursor:],
                    cursor + 1,
                )

            pair_filter = auto_pairs if opening in "([{" else auto_quotes
            keys.add(opening, filter=editor & pair_filter)(_insert)

        @keys.add("*", filter=editor)
        def _comment_open(event) -> None:
            pane = self.active_pane
            if pane is None or not self.config.auto_closing_comments:
                event.current_buffer.insert_text("*")
                return
            opening = pane.language.block_comment[0] if pane.language.block_comment else None
            closing = pane.language.block_comment[1] if pane.language.block_comment else None
            text = pane.buffer.text
            cursor = pane.buffer.cursor_position
            if opening and closing and text[cursor - len(opening) + 1 : cursor] == opening[:-1]:
                start = cursor - len(opening) + 1
                pane.set_text(text[:start] + opening + closing + text[cursor:], start + len(opening))
            else:
                event.current_buffer.insert_text("*")

        for closing, opening in [(")", "("), ("]", "["), ("}", "{")]:

            def _close_pair(event, closing=closing, opening=opening) -> None:
                pane = self.active_pane
                if pane is None:
                    return
                if not pane.selection().empty:
                    pane.replace_selection(closing)
                    return
                text = pane.buffer.text
                cursor = pane.buffer.cursor_position
                if text[cursor : cursor + 1] == closing:
                    pane.buffer.cursor_position = cursor + 1
                    return
                pane.replace_selection(closing)

            keys.add(closing, filter=editor & auto_pairs)(_close_pair)


SHORTCUTS_TEXT = """
Keyboard Shortcuts
==================

  Ctrl+S          Save
  Ctrl+N          New file
  Ctrl+O / Ctrl+P Open file (quick open)
  Ctrl+K Ctrl+O   Open folder
  Ctrl+W          Close editor
  Ctrl+Q          Quit
  Ctrl+PageDown   Next editor
  Ctrl+PageUp     Previous editor
  Ctrl+B          Toggle sidebar
  F1              Command palette
  Ctrl+G          Go to line
  Ctrl+F          Find
  Ctrl+R          Replace
  F3 / F4         Next / previous match
  F6 / F7 / F8    Toggle case / whole word / regex
  F5              Replace all
  Ctrl+Z          Undo
  Ctrl+Y          Redo
  Ctrl+A          Select all
  Ctrl+C / X / V  Copy / cut / paste
  Ctrl+Alt+E      Emmet: Expand Abbreviation
  Ctrl+D          Duplicate line
  Ctrl+K          Delete line
  Ctrl+Up/Down    Move line up/down
  Ctrl+/          Toggle line comment
  Tab / Shift+Tab Indent / outdent
  F10             Toggle word wrap
  F9              Open the File menu
  Ctrl+F9         Toggle code folding on the current block
  Ctrl+Space      Word completion

Explorer: arrow keys navigate, Enter opens, Right/Left expand/collapse.
Find bar: Tab switches to the replace field, Esc closes.

Tip: if Ctrl+S freezes the terminal, run `stty -ixon` first (XOFF flow
control). Mouse support can be toggled from the command palette.
"""

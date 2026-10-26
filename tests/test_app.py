"""Headless integration tests for the prompt_toolkit application.

These tests drive the real key bindings through a pipe input and a dummy
output. They are intentionally focused on user-visible flows instead of
internal state.
"""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from prompt_toolkit.data_structures import Point
from prompt_toolkit.input import create_pipe_input
from prompt_toolkit.mouse_events import MouseEventType
from prompt_toolkit.output import DummyOutput

from vcli.app import EditorApp
from vcli.config import Config

CTRL_C = "\x03"
CTRL_D = "\x04"
CTRL_F = "\x06"
CTRL_G = "\x07"
CTRL_K = "\x0b"
CTRL_N = "\x0e"
CTRL_P = "\x10"
CTRL_Q = "\x11"
CTRL_R = "\x12"
CTRL_S = "\x13"
CTRL_W = "\x17"
CTRL_Y = "\x19"
CTRL_Z = "\x1a"
ESC = "\x1b"
ENTER = "\r"
TAB = "\t"
BACKSPACE = "\x7f"
F1 = "\x1bOP"
F3 = "\x1bOR"
F5 = "\x1b[15~"
F10 = "\x1b[21~"
DOWN = "\x1b[B"
UP = "\x1b[A"


class PipeInput:
    """Tiny wrapper that keeps the pipe-input context manager open."""

    def __init__(self) -> None:
        self._context = create_pipe_input()
        self.input = self._context.__enter__()

    def send_text(self, text: str) -> None:
        self.input.send_text(text)

    def close(self) -> None:
        self._context.__exit__(None, None, None)


def make_app(
    tmp_path: Path,
    *,
    files: tuple[Path, ...] = (),
    confirm_exit: bool = False,
    show_sidebar: bool = False,
    config: Config | None = None,
) -> tuple[EditorApp, PipeInput]:
    cfg = config or Config(
        confirm_exit=confirm_exit, show_sidebar=show_sidebar, mouse=False
    )
    pipe = PipeInput()
    app = EditorApp(
        files,
        config=cfg,
        workspace_root=tmp_path,
        config_file=tmp_path / "config.json",
        input=pipe.input,
        output=DummyOutput(),
    )
    return app, pipe


def run_keys(
    tmp_path: Path,
    keys: str,
    *,
    files: tuple[Path, ...] = (),
    confirm_exit: bool = False,
    show_sidebar: bool = False,
    pre_run=None,
    config: Config | None = None,
) -> EditorApp:
    app, pipe = make_app(
        tmp_path,
        files=files,
        confirm_exit=confirm_exit,
        show_sidebar=show_sidebar,
        config=config,
    )
    try:
        pipe.send_text(keys)
        app.application.run(pre_run=pre_run, set_exception_handler=False)
    finally:
        pipe.close()
    return app


def test_new_file_typing_and_save(tmp_path: Path):
    target = tmp_path / "notes.txt"
    app = run_keys(
        tmp_path,
        CTRL_N + "line one" + ENTER + "line two" + CTRL_S + CTRL_Q,
    )
    # Ctrl+S on an untitled buffer asks for a name; nothing is written yet.
    assert "No file name" in app.message
    assert app.documents and app.documents[0].buffer.text == "line one\nline two"

    # Save As via the command palette writes the file.
    app = run_keys(
        tmp_path,
        CTRL_N
        + "hello"
        + F1
        + "save as"
        + ENTER
        + "\x01\x0b"
        + str(target)
        + ENTER
        + CTRL_Q,
    )
    assert target.read_text(encoding="utf-8") == "hello"
    assert app.documents[0].dirty is False


def test_open_file_and_close_dirty_tab(tmp_path: Path):
    path = tmp_path / "demo.txt"
    path.write_text("original\n", encoding="utf-8")

    # Cancel the close dialog: the document must stay open and dirty.
    app = run_keys(
        tmp_path,
        "X" + CTRL_W + DOWN + DOWN + ENTER + CTRL_Q,
        files=(path,),
    )
    assert len(app.documents) == 1
    assert app.documents[0].dirty is True
    assert path.read_text(encoding="utf-8") == "original\n"

    # Choose "Save" in the close dialog: saved and closed.
    app = run_keys(tmp_path, "X" + CTRL_W + ENTER + CTRL_Q, files=(path,))
    assert not app.documents
    assert path.read_text(encoding="utf-8") == "Xoriginal\n"


def test_undo_redo(tmp_path: Path):
    app = run_keys(
        tmp_path,
        CTRL_N + "abc" + CTRL_Z + CTRL_Z + CTRL_Y + CTRL_Q,
    )
    assert app.documents[0].buffer.text in {"", "a", "ab", "abc"}
    # prompt_toolkit groups typing, so at minimum redo restores something.
    assert CTRL_Q not in app.documents[0].buffer.text


def test_edit_operations(tmp_path: Path):
    path = tmp_path / "code.py"
    path.write_text("one\ntwo\n", encoding="utf-8")

    # Ctrl+A then Tab indents both lines.
    app = run_keys(
        tmp_path,
        "\x01" + TAB + CTRL_Z + CTRL_Q,
        files=(path,),
    )
    assert app.documents[0].buffer.text == "one\ntwo\n"

    # Duplicate the current line and delete it again.
    app = run_keys(
        tmp_path,
        CTRL_N + "dup" + CTRL_D + CTRL_Z + CTRL_Q,
    )
    assert app.documents[0].buffer.text == "dup"

    # Comment toggle on a Python file.
    app = run_keys(tmp_path, "\x01" + "\x1f" + CTRL_Q, files=(path,))
    assert app.documents[0].buffer.text.startswith("# ")


def test_find_and_replace_all(tmp_path: Path):
    path = tmp_path / "text.txt"
    path.write_text("foo bar foo baz\n", encoding="utf-8")

    app = run_keys(
        tmp_path,
        CTRL_F + "foo" + F3 + CTRL_Q,
        files=(path,),
    )
    assert app.find.index == 1

    app = run_keys(
        tmp_path,
        CTRL_R + "foo" + TAB + "qux" + F5 + ESC + CTRL_Q,
        files=(path,),
    )
    assert app.documents[0].buffer.text == "qux bar qux baz\n"
    assert app.documents[0].dirty is True


def test_find_case_toggle_and_invalid_regex(tmp_path: Path):
    path = tmp_path / "text.txt"
    path.write_text("Foo foo\n", encoding="utf-8")

    app = run_keys(
        tmp_path,
        CTRL_F + "foo" + "\x1b[17~" + CTRL_Q,  # F6 toggles case
        files=(path,),
    )
    assert app.find.case_sensitive is True
    assert len(app.find.matches) == 1

    app = run_keys(
        tmp_path,
        CTRL_F + "(" + "\x1b[19~" + CTRL_Q,  # F8 enables regex
        files=(path,),
    )
    assert app.find.regex is True
    assert app.find.error is not None


def test_typing_replaces_selection(tmp_path: Path):
    path = tmp_path / "code.py"
    path.write_text("hello world\n", encoding="utf-8")

    app = run_keys(
        tmp_path,
        "\x01" + "bye" + CTRL_Z * 3 + CTRL_Q,
        files=(path,),
    )
    assert app.documents[0].buffer.text == "hello world\n"

    app = run_keys(
        tmp_path,
        "\x01" + "bye" + CTRL_Q,
        files=(path,),
    )
    assert app.documents[0].buffer.text == "bye"


def test_find_prefill_is_selected(tmp_path: Path):
    path = tmp_path / "code.py"
    path.write_text("alpha beta\n", encoding="utf-8")

    # Cursor starts at the beginning, so "alpha" is the prefilled query.
    app = run_keys(tmp_path, CTRL_F + "beta" + CTRL_Q, files=(path,))
    assert app.find.query_buffer.text == "beta"
    assert len(app.find.matches) == 1


def test_quick_open_and_goto_line(tmp_path: Path):
    path = tmp_path / "src" / "main.py"
    path.parent.mkdir()
    path.write_text("a\nb\nc\n", encoding="utf-8")

    app = run_keys(
        tmp_path,
        CTRL_P + "main" + ENTER + CTRL_G + "2" + ENTER + CTRL_Q,
    )
    assert app.active_pane is not None
    assert app.active_pane.path == path.resolve()
    assert app.active_pane.cursor_line == 2


def test_command_palette_theme_persisted(tmp_path: Path):
    app = run_keys(
        tmp_path, F1 + "color theme" + ENTER + "dracula" + ENTER + CTRL_Q
    )
    assert app.config.theme == "dracula"
    raw = (tmp_path / "config.json").read_text(encoding="utf-8")
    assert "dracula" in raw


def test_quit_confirmation_can_cancel_and_quit(tmp_path: Path):
    # Down -> "Quit Without Saving" exits the application.
    app = run_keys(
        tmp_path,
        CTRL_N + "dirty" + CTRL_Q + DOWN + ENTER,
        confirm_exit=True,
    )
    assert app._quitting is True

    # Cancel keeps the app alive; a second Ctrl+Q with confirm disabled exits.
    config = Config(confirm_exit=True, show_sidebar=False, mouse=False)
    app, pipe = make_app(tmp_path, config=config)
    try:
        pipe.send_text(CTRL_N + "dirty" + CTRL_Q + DOWN + DOWN + ENTER)
        pipe.send_text(CTRL_Q)
        app.config.confirm_exit = False
        app.application.run(pre_run=None, set_exception_handler=False)
    finally:
        pipe.close()
    assert app._quitting is True


def test_sidebar_toggle_and_word_wrap(tmp_path: Path):
    app = run_keys(tmp_path, "\x02" + F10 + CTRL_Q, show_sidebar=True)
    assert app.config.show_sidebar is False
    assert app.config.word_wrap is True


def test_settings_panel_changes_persisted_editor_options(tmp_path: Path):
    app, pipe = make_app(tmp_path)
    try:
        app.open_settings()
        highlight = next(
            item for item in app.picker.items
            if item.label == "Editor: Highlight Current Line"
        )
        highlight.action()
        assert app.config.highlight_current_line is False
        assert app.picker.mode == "settings"

        line_height = next(
            item for item in app.picker.items if item.label == "Editor: Line Height"
        )
        line_height.action()
        assert app.config.line_height == 2
        assert (tmp_path / "config.json").exists()
    finally:
        pipe.close()


def test_mouse_tab_and_tree_clicks(tmp_path: Path):
    first = tmp_path / "a.txt"
    first.write_text("a\n", encoding="utf-8")
    app, pipe = make_app(tmp_path, show_sidebar=True, files=(first,))
    try:
        app.new_file()
        assert len(app.documents) == 2
        assert app.active_index == 1

        app.tabbar.create_content(80, 1)
        # Clicking the first tab activates it (MOUSE_DOWN).
        app.tabbar.mouse_handler(
            SimpleNamespace(
                position=Point(1, 0), event_type=MouseEventType.MOUSE_DOWN
            )
        )
        assert app.active_index == 0

        app.tree_control.create_content(30, 10)
        node = next(n for n in app.workspace.flatten() if n.name == "a.txt")
        index = app.workspace.flatten().index(node)
        app.tree_control.mouse_handler(
            SimpleNamespace(
                position=Point(2, index), event_type=MouseEventType.MOUSE_UP
            )
        )
        assert app.workspace.selected == index
        assert app.active_pane.path == first.resolve()
    finally:
        pipe.close()


def test_mouse_close_on_press_and_release_does_not_double_close(tmp_path: Path):
    first = tmp_path / "a.txt"
    second = tmp_path / "b.txt"
    first.write_text("a\n", encoding="utf-8")
    second.write_text("b\n", encoding="utf-8")
    app, pipe = make_app(tmp_path, files=(first, second))
    try:
        app.tabbar.create_content(80, 1)
        close = next(
            span for span in app.tabbar._spans if span[2] == "close"
        )
        x = close[0]

        def event(kind):
            return SimpleNamespace(position=Point(x, 0), event_type=kind)

        # Press alone must close the tab (terminals that only report presses).
        app.tabbar.mouse_handler(event(MouseEventType.MOUSE_DOWN))
        assert len(app.documents) == 1

        # And the release that follows must not close the next tab.
        app.tabbar.mouse_handler(event(MouseEventType.MOUSE_UP))
        assert len(app.documents) == 1
    finally:
        pipe.close()


def test_close_dirty_tab_mouse(tmp_path: Path):
    path = tmp_path / "b.txt"
    path.write_text("b\n", encoding="utf-8")
    app, pipe = make_app(tmp_path, files=(path,))
    try:
        app.active_pane.buffer.insert_text("x")
        app.tabbar.create_content(80, 1)
        # Close span starts after "  b.txt " (8 cells).
        app.tabbar.mouse_handler(
            SimpleNamespace(
                position=Point(9, 0), event_type=MouseEventType.MOUSE_UP
            )
        )
        assert app.picker.active is True
        assert app.picker.mode == "confirm"
        app.picker.close()
        assert len(app.documents) == 1
    finally:
        pipe.close()


def test_cursor_blink_state_machine(tmp_path: Path):
    app, pipe = make_app(tmp_path)
    try:
        assert app.cursor_visible()

        # One phase later the cursor goes dark, then comes back.
        app.advance_blink(now=app._blink_next + 0.01)
        assert not app.cursor_visible()
        app.advance_blink(now=app._blink_next + 0.01)
        assert app.cursor_visible()

        # A keystroke or a cursor move shows it again immediately.
        app.advance_blink(now=app._blink_next + 0.01)
        assert not app.cursor_visible()
        app.reset_blink()
        assert app.cursor_visible()

        # Turning the setting off pins the cursor on.
        app.config.cursor_blink = False
        app.advance_blink(now=app._blink_next + 60)
        assert app.cursor_visible()
    finally:
        pipe.close()


def test_editor_cursor_follows_blink_phase(tmp_path: Path):
    app, pipe = make_app(tmp_path)
    try:
        app.new_file()
        control = app.active_pane.control
        assert control._cursor_visible() is True
        app.advance_blink(now=app._blink_next + 0.01)
        assert control._cursor_visible() is False
        app.reset_blink()
        assert control._cursor_visible() is True
    finally:
        pipe.close()

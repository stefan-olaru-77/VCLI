"""Unit tests for the pure text transformations."""

from __future__ import annotations

from vcli import actions


def test_line_helpers():
    text = "one\ntwo\nthree"
    assert actions.line_start(text, 5) == 4
    assert actions.line_end(text, 5) == 7
    assert actions.line_bounds(text, 5) == (4, 7)
    assert actions.line_block(text, 0, 4) == (0, 3)
    assert actions.line_start("", 0) == 0
    assert actions.line_end("", 0) == 0


def test_normalize_selection():
    assert actions.normalize(9, 2) == actions.Selection(2, 9)
    assert actions.normalize(2, 2).empty
    assert list(actions.Selection(1, 4)) == [1, 4]


def test_indent_and_outdent_lines():
    text = "a\nb\n"
    new_text, start, end = actions.indent_lines(text, 0, 3, "    ")
    assert new_text == "    a\n    b\n"
    assert (start, end) == (4, 11)

    back, _, _ = actions.outdent_lines(new_text, 0, len(new_text), 4)
    assert back == text


def test_indent_at_cursor_uses_tab_stops():
    text = "ab"
    new_text, cursor = actions.indent_at_cursor(text, 2, 4)
    assert new_text == "ab  "
    assert cursor == 4

    tabs, cursor = actions.indent_at_cursor("x", 1, 4, use_spaces=False)
    assert tabs == "x\t"
    assert cursor == 2


def test_outdent_at_cursor_never_eats_code():
    assert actions.outdent_at_cursor("    x", 5, 4) == ("x", 1)
    assert actions.outdent_at_cursor("  ab", 4, 4) == ("ab", 2)
    assert actions.outdent_at_cursor("abc", 2, 4) == ("abc", 2)


def test_toggle_comment_roundtrip():
    text = "a = 1\nb = 2\n"
    commented, start, end = actions.toggle_comment(text, 0, len(text), "#")
    assert commented == "# a = 1\n# b = 2\n"
    assert (start, end) == (0, 15)

    restored, _, _ = actions.toggle_comment(commented, 0, len(commented), "#")
    assert restored == text


def test_toggle_comment_preserves_blank_lines_and_indent():
    text = "  value = 1\n\n  return value\n"
    commented, _, _ = actions.toggle_comment(text, 0, len(text), "//")
    assert commented == "  // value = 1\n\n  // return value\n"


def test_wrap_block_comment():
    new_text, start, end = actions.wrap_block_comment("x = 1\n", 0, 0, "/*", "*/")
    assert new_text == "/* x = 1 */\n"
    assert (start, end) == (0, 11)


def test_duplicate_lines():
    text = "one\ntwo\n"
    new_text, _, _, cursor = actions.duplicate_lines(text, 4, 4, 4)
    assert new_text == "one\ntwo\ntwo\n"
    assert new_text[cursor:] == "two\n"


def test_move_lines():
    text = "one\ntwo\nthree\n"
    result = actions.move_lines(text, 4, 4, 1)
    assert result is not None
    new_text, _, _, cursor = result
    assert new_text == "one\nthree\ntwo\n"
    assert new_text[cursor:].startswith("two")

    moved_up = actions.move_lines(new_text, 10, 10, -1)
    assert moved_up is not None
    assert moved_up[0] == "one\ntwo\nthree\n"

    assert actions.move_lines("only\n", 0, 0, -1) is None
    assert actions.move_lines("only\n", 0, 0, 1) is None
    assert actions.move_lines(text, 0, 0, 0) is None


def test_delete_lines():
    text = "one\ntwo\nthree"
    assert actions.delete_lines(text, 4, 4) == ("one\nthree", 4)
    assert actions.delete_lines(text, 0, 0) == ("two\nthree", 0)
    assert actions.delete_lines("only", 0, 0) == ("", 0)


def test_auto_indent_newline():
    text = "if True:"
    payload, offset = actions.auto_indent_newline(text, len(text), "    ")
    assert payload == "\n    "
    assert offset == len(payload)

    text = "    x = 1"
    payload, offset = actions.auto_indent_newline(text, len(text), "    ")
    assert payload == "\n    "

    wrapped = "foo()"
    payload, offset = actions.auto_indent_newline(wrapped, 4, "    ")
    assert payload == "\n    \n"
    assert offset == 5


def test_detect_indentation():
    assert actions.detect_indentation("") is None
    assert actions.detect_indentation("plain\n") is None
    assert actions.detect_indentation("if x:\n    y\n") == (True, 4)
    assert actions.detect_indentation("\tfoo\n\tbar\n") == (False, 4)


def test_whitespace_and_words():
    assert actions.trim_trailing_whitespace(" a  \n b\t\n") == " a\n b\n"
    assert actions.ensure_final_newline("x") == "x\n"
    assert actions.ensure_final_newline("x\n") == "x\n"
    assert actions.ensure_final_newline("") == ""

    text = "hello brave world"
    assert actions.word_at(text, 8) == (6, 11, "brave")
    assert actions.word_at("...", 1) is None
    assert actions.word_at("", 0) is None

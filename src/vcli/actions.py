"""Pure text transformations used by the editor.

Keeping these functions free of any prompt_toolkit dependency makes them easy
to unit test - the UI layer only turns the results into buffer updates.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

WORD_RE = re.compile(r"[A-Za-z0-9_]+")
_INDENT_RE = re.compile(r"[ \t]*")

OPEN_TO_CLOSE = {"(": ")", "[": "]", "{": "}"}
CLOSE_TO_OPEN = {v: k for k, v in OPEN_TO_CLOSE.items()}


@dataclass(frozen=True)
class Selection:
    """A normalized (start <= end) selection in character offsets."""

    start: int
    end: int

    @property
    def empty(self) -> bool:
        return self.start == self.end

    def __iter__(self):
        yield self.start
        yield self.end


def normalize(start: int, end: int) -> Selection:
    return Selection(min(start, end), max(start, end))


def line_start(text: str, index: int) -> int:
    return text.rfind("\n", 0, index) + 1


def line_end(text: str, index: int) -> int:
    end = text.find("\n", index)
    return len(text) if end == -1 else end


def line_bounds(text: str, index: int) -> tuple[int, int]:
    start = line_start(text, index)
    return start, line_end(text, index)


def line_block(text: str, start: int, end: int) -> tuple[int, int]:
    """Expand a selection to whole lines.

    A selection that ends exactly at the beginning of a line does not include
    that line (matching the behaviour of most code editors).
    """
    start, end = normalize(start, end)
    block_start = line_start(text, start)
    probe = end - 1 if end > start else end
    block_end = line_end(text, max(probe, start))
    return block_start, block_end


def _line_offsets(lines: list[str]) -> list[int]:
    offsets = [0]
    total = 0
    for line in lines:
        total += len(line) + 1
        offsets.append(total)
    return offsets


def line_index(text: str, index: int) -> int:
    return text.count("\n", 0, index)


def indent_lines(
    text: str, start: int, end: int, unit: str
) -> tuple[str, int, int]:
    """Indent every line touched by the selection. Returns text, start, end."""
    sel = normalize(start, end)
    if sel.empty:
        return text, start, end
    block_start, block_end = line_block(text, sel.start, sel.end)
    block = text[block_start:block_end]
    lines = block.split("\n")
    new_block = "\n".join(unit + line for line in lines)
    delta = len(new_block) - len(block)
    new_text = text[:block_start] + new_block + text[block_end:]
    return new_text, sel.start + len(unit), sel.end + delta


def outdent_lines(
    text: str, start: int, end: int, tab_size: int, use_spaces: bool = True
) -> tuple[str, int, int]:
    """Remove one indentation level from every selected line."""
    sel = normalize(start, end)
    if sel.empty:
        return text, start, end
    block_start, block_end = line_block(text, sel.start, sel.end)
    block = text[block_start:block_end]
    removed_total = 0
    removed_first = 0
    new_lines: list[str] = []
    for i, line in enumerate(block.split("\n")):
        if line.startswith("\t"):
            removed = 1
        elif use_spaces:
            removed = len(line) - len(line.lstrip(" "))
            removed = min(removed, tab_size)
        else:
            removed = 0
        if i == 0:
            removed_first = removed
        removed_total += removed
        new_lines.append(line[removed:])
    new_block = "\n".join(new_lines)
    new_text = text[:block_start] + new_block + text[block_end:]
    return new_text, max(block_start, sel.start - removed_first), max(
        block_start, sel.end - removed_total
    )


def indent_at_cursor(
    text: str, cursor: int, tab_size: int, use_spaces: bool = True
) -> tuple[str, int]:
    """Tab without a selection: move to the next tab stop."""
    if not use_spaces:
        return text[:cursor] + "\t" + text[cursor:], cursor + 1
    col = cursor - line_start(text, cursor)
    spaces = tab_size - (col % tab_size)
    return text[:cursor] + " " * spaces + text[cursor:], cursor + spaces


def outdent_at_cursor(
    text: str, cursor: int, tab_size: int
) -> tuple[str, int]:
    """Backtab without a selection: remove one indent level from the line."""
    start = line_start(text, cursor)
    line = text[start:]
    if not line:
        return text, cursor
    if line.startswith("\t"):
        removed = 1
    else:
        indentation = len(line) - len(line.lstrip(" "))
        removed = min(indentation, tab_size)
    if removed <= 0:
        return text, cursor
    new_text = text[:start] + text[start + removed :]
    return new_text, max(start, cursor - removed)


def toggle_comment(
    text: str, start: int, end: int, line_comment: str
) -> tuple[str, int, int]:
    """Comment/uncomment complete lines with ``line_comment``."""
    sel = normalize(start, end)
    block_start, block_end = line_block(text, sel.start, sel.end)
    block = text[block_start:block_end]
    lines = block.split("\n")
    meaningful = [line for line in lines if line.strip()]
    prefix = line_comment + " "
    if not meaningful:
        return text, start, end

    all_commented = all(line.lstrip().startswith(line_comment) for line in meaningful)
    if all_commented:
        new_lines: list[str] = []
        for line in lines:
            stripped = line.lstrip()
            if stripped.startswith(line_comment):
                indent = line[: len(line) - len(stripped)]
                rest = stripped[len(line_comment) :]
                rest = rest.removeprefix(" ")
                new_lines.append(indent + rest)
            else:
                new_lines.append(line)
    else:
        new_lines = []
        for line in lines:
            if not line.strip():
                new_lines.append(line)
                continue
            indent = _INDENT_RE.match(line).group(0)
            new_lines.append(indent + prefix + line[len(indent) :])
    new_block = "\n".join(new_lines)
    new_text = text[:block_start] + new_block + text[block_end:]
    # Keep the same lines selected; clamp the end so it never passes EOF.
    new_end = min(len(new_text), block_start + len(new_block))
    return new_text, block_start, new_end if sel.end > sel.start else block_start


def wrap_block_comment(
    text: str, start: int, end: int, opening: str, closing: str
) -> tuple[str, int, int]:
    """Surround the selection (or current line) with a block comment."""
    sel = normalize(start, end)
    if sel.empty:
        s, e = line_bounds(text, sel.start)
    else:
        s, e = sel.start, sel.end
    wrapped = f"{opening} {text[s:e]} {closing}"
    new_text = text[:s] + wrapped + text[e:]
    return new_text, s, s + len(wrapped)


def duplicate_lines(
    text: str, start: int, end: int, cursor: int
) -> tuple[str, int, int, int]:
    """Duplicate the selected lines (or the current line).

    Returns ``(text, sel_start, sel_end, cursor)`` with the *second* copy
    selected, mirroring VSCode's "Duplicate Line Down".
    """
    sel = normalize(start, end)
    block_start, block_end = line_block(text, sel.start, sel.end)
    block = text[block_start:block_end]
    insert_at = block_end
    payload = "\n" + block
    new_text = text[:insert_at] + payload + text[insert_at:]
    shift = len(payload)
    if sel.empty:
        return new_text, cursor, cursor, cursor + shift
    return new_text, sel.start + shift, sel.end + shift, cursor + shift


def move_lines(
    text: str, start: int, end: int, direction: int
) -> tuple[str, int, int, int] | None:
    """Move selected lines up (``-1``) or down (``+1``).

    Returns ``(text, sel_start, sel_end, cursor)``; the selection follows the
    moved block. ``None`` means the block is already at the document edge.
    """
    if direction == 0:
        return None
    sel = normalize(start, end)
    block_start, block_end = line_block(text, sel.start, sel.end)
    had_final_newline = text.endswith("\n")
    lines = text.split("\n")
    if had_final_newline:
        lines.pop()
    first = line_index(text, block_start)
    last = line_index(text, max(block_start, block_end - 1))

    if direction < 0:
        if first == 0:
            return None
        neighbour = lines[first - 1]
        new_lines = (
            lines[: first - 1] + lines[first : last + 1] + [neighbour] + lines[last + 1 :]
        )
        new_first = first - 1
    else:
        if last >= len(lines) - 1:
            return None
        neighbour = lines[last + 1]
        new_lines = (
            lines[:first] + [neighbour] + lines[first : last + 1] + lines[last + 2 :]
        )
        new_first = first + 1

    new_text = "\n".join(new_lines)
    if had_final_newline:
        new_text += "\n"
    offsets = _line_offsets(new_lines)
    new_block_start = offsets[new_first]
    new_block_end = offsets[new_first + (last - first + 1)] - 1
    new_block_end = max(new_block_end, new_block_start)
    if sel.empty:
        column = sel.start - block_start
        cursor = min(new_block_start + column, new_block_end)
        return new_text, cursor, cursor, cursor
    return new_text, new_block_start, new_block_end, new_block_end


def delete_lines(text: str, start: int, end: int) -> tuple[str, int]:
    """Delete the selected lines including their trailing newline."""
    sel = normalize(start, end)
    block_start, block_end = line_block(text, sel.start, sel.end)
    if block_end < len(text) and text[block_end] == "\n":
        block_end += 1
    elif block_start > 0:
        block_start -= 1
    new_text = text[:block_start] + text[block_end:]
    cursor = min(block_start, len(new_text))
    return new_text, cursor


def auto_indent_newline(
    text: str,
    cursor: int,
    unit: str,
    pair_aware: bool = True,
) -> tuple[str, int]:
    """Return the text to insert for Enter and the cursor offset inside it."""
    start = line_start(text, cursor)
    before = text[start:cursor]
    indent = _INDENT_RE.match(before).group(0)
    stripped = before.rstrip()
    increase = stripped.endswith((":", "{", "[", "(", ","))

    if pair_aware:
        prev_char = text[cursor - 1] if cursor > 0 else ""
        next_char = text[cursor] if cursor < len(text) else ""
        if prev_char in OPEN_TO_CLOSE and OPEN_TO_CLOSE[prev_char] == next_char:
            inner = indent + (unit if increase else "")
            payload = "\n" + inner + "\n" + indent
            return payload, len("\n" + inner)

    inner = indent + (unit if increase else "")
    payload = "\n" + inner
    return payload, len(payload)


def detect_indentation(
    text: str, default_size: int = 4, max_lines: int = 400
) -> tuple[bool, int] | None:
    """Guess ``(use_spaces, tab_size)`` from the file contents."""
    sizes: dict[int, int] = {}
    tab_lines = 0
    inspected = 0
    for line in text.split("\n")[:max_lines]:
        if not line.strip():
            continue
        inspected += 1
        if line.startswith("\t"):
            tab_lines += 1
            continue
        indent = len(line) - len(line.lstrip(" "))
        if indent:
            sizes[indent] = sizes.get(indent, 0) + 1
    if inspected == 0:
        return None
    if tab_lines > sum(sizes.values()):
        return False, default_size
    if not sizes:
        return None
    # Use the smallest common indentation (ignoring continuation alignment).
    best = min(sizes)
    for candidate in (2, 4, 8):
        if candidate in sizes:
            best = candidate
            break
    return True, best


def trim_trailing_whitespace(text: str) -> str:
    return "\n".join(line.rstrip() for line in text.split("\n"))


def ensure_final_newline(text: str) -> str:
    return text if text.endswith("\n") or not text else text + "\n"


def word_at(text: str, cursor: int) -> tuple[int, int, str] | None:
    """Return ``(start, end, word)`` around ``cursor``."""
    if not text:
        return None
    start = min(max(cursor, 0), len(text))
    end = start
    while start > 0 and WORD_RE.match(text[start - 1]):
        start -= 1
    while end < len(text) and WORD_RE.match(text[end]):
        end += 1
    if start == end:
        return None
    return start, end, text[start:end]


def indentation_of(text: str, index: int) -> str:
    start = line_start(text, index)
    return _INDENT_RE.match(text[start:index]).group(0)

"""Input processors that decorate the editor content."""

from __future__ import annotations

import re
from collections.abc import Callable
from typing import Protocol

from prompt_toolkit.document import Document
from prompt_toolkit.formatted_text import StyleAndTextTuples
from prompt_toolkit.layout.processors import (
    Processor,
    Transformation,
    TransformationInput,
)


class SpanProvider(Protocol):
    def spans_for_line(
        self, document: Document, lineno: int
    ) -> list[tuple[int, int, str]]: ...


class SearchHighlighter(Processor):
    """Highlight every find-bar match, with a stronger colour for the current one.

    The provider returns line-relative ``(start, end, style_class)`` spans and
    is responsible for caching (this processor runs for every visible line on
    every render).
    """

    def __init__(self, provider: SpanProvider) -> None:
        self.provider = provider

    def apply_transformation(
        self, transformation_input: TransformationInput
    ) -> Transformation:
        spans = self.provider.spans_for_line(
            transformation_input.document, transformation_input.lineno
        )
        if not spans:
            return Transformation(transformation_input.fragments)

        result: StyleAndTextTuples = []
        position = 0
        for fragment in transformation_input.fragments:
            style = fragment[0]
            text = fragment[1]
            extra = fragment[2:]
            frag_start = position
            frag_end = position + len(text)
            cuts = {frag_start, frag_end}
            for start, end, _ in spans:
                if frag_start < start < frag_end:
                    cuts.add(start)
                if frag_start < end < frag_end:
                    cuts.add(end)
            boundaries = sorted(cuts)
            for start, end in zip(boundaries, boundaries[1:]):
                if start >= end:
                    continue
                overlap = next(
                    (
                        cls
                        for span_start, span_end, cls in spans
                        if span_start <= start < span_end
                    ),
                    None,
                )
                segment = text[start - frag_start : end - frag_start]
                new_style = f"{style} {overlap}" if overlap else style
                result.append((new_style, segment, *extra))
            position = frag_end

        return Transformation(result)


class MultiSelectionHighlighter(Processor):
    """Highlight secondary selections created by multi-cursor editing."""

    def __init__(self, provider: Callable[[int], list[tuple[int, int]]]) -> None:
        self.provider = provider

    def apply_transformation(
        self, transformation_input: TransformationInput
    ) -> Transformation:
        spans = self.provider(transformation_input.lineno)
        if not spans:
            return Transformation(transformation_input.fragments)
        styles: dict[int, str] = {}
        for start, end in spans:
            styles.update(
                {position: "class:multi-selection" for position in range(start, end)}
            )
        return Transformation(_apply_position_styles(transformation_input.fragments, styles))


class BracketPairColorizer(Processor):
    """Apply rotating colors to nested brackets in the current document."""

    _OPEN = "([{"
    _CLOSE = ")] }".replace(" ", "")

    def __init__(self, enabled: Callable[[], bool]) -> None:
        self.enabled = enabled

    def apply_transformation(
        self, transformation_input: TransformationInput
    ) -> Transformation:
        if not self.enabled():
            return Transformation(transformation_input.fragments)
        document = transformation_input.document
        line_start = document.translate_row_col_to_index(transformation_input.lineno, 0)
        depth = 0
        for char in document.text[:line_start]:
            if char in self._OPEN:
                depth += 1
            elif char in self._CLOSE:
                depth = max(0, depth - 1)

        colors: dict[int, str] = {}
        for offset, char in enumerate(document.lines[transformation_input.lineno]):
            if char in self._CLOSE:
                depth = max(0, depth - 1)
            if char in self._OPEN or char in self._CLOSE:
                colors[offset] = f"class:bracket.color.{depth % 5}"
            if char in self._OPEN:
                depth += 1
        return Transformation(_apply_position_styles(transformation_input.fragments, colors))


class ColorDecorator(Processor):
    """Render hexadecimal color literals with their color as a background."""

    _HEX = re.compile(r"#[0-9a-fA-F]{3,8}\b")

    def __init__(self, enabled: Callable[[], bool]) -> None:
        self.enabled = enabled

    def apply_transformation(
        self, transformation_input: TransformationInput
    ) -> Transformation:
        if not self.enabled():
            return Transformation(transformation_input.fragments)
        line = transformation_input.document.lines[transformation_input.lineno]
        styles = {
            match.start(): f"bg:{match.group(0)} #000000"
            for match in self._HEX.finditer(line)
        }
        return Transformation(_apply_position_styles(transformation_input.fragments, styles))


class SemanticIdentifierColorizer(Processor):
    """Add JetBrains-like colors to generic identifier tokens.

    Pygments already marks declarations such as ``Name.Function`` and
    ``Name.Class``.  This processor fills in the identifiers that lexers leave
    as generic ``Name`` tokens using lightweight, language-neutral context
    rules.  It intentionally stays lexical and never changes the document.
    """

    _DECLARATION = re.compile(
        r"\b(?:def|function|fn|func|sub|fun)\s+([A-Za-z_$][\w$]*)"
    )
    _CLASS_DECLARATION = re.compile(
        r"\b(?:class|interface|trait|struct|enum)\s+([A-Za-z_$][\w$]*)"
    )
    _IDENTIFIER = re.compile(r"[A-Za-z_$][\w$]*")

    def __init__(self, language: Callable[[], object]) -> None:
        self.language = language

    def apply_transformation(
        self, transformation_input: TransformationInput
    ) -> Transformation:
        line = transformation_input.document.lines[transformation_input.lineno]
        if not line:
            return Transformation(transformation_input.fragments)

        function_positions = self._declaration_positions(line, self._DECLARATION)
        class_positions = self._declaration_positions(line, self._CLASS_DECLARATION)
        parameter_ranges = self._parameter_ranges(line)
        styles: dict[int, str] = {}
        position = 0
        for fragment in transformation_input.fragments:
            style, text = fragment[:2]
            if "pygments.name" not in style:
                position += len(text)
                continue
            known_kind = any(
                f"pygments.name.{kind}" in style
                for kind in ("function", "class", "attribute", "builtin", "constant")
            )
            if known_kind:
                position += len(text)
                continue
            for match in self._IDENTIFIER.finditer(text):
                absolute = position + match.start()
                name = match.group(0)
                kind = self._kind_for(
                    line,
                    absolute,
                    name,
                    function_positions,
                    class_positions,
                    parameter_ranges,
                )
                semantic_style = f"class:semantic.{kind}"
                for offset in range(match.start(), match.end()):
                    styles[position + offset] = semantic_style
            position += len(text)
        return Transformation(_apply_position_styles(transformation_input.fragments, styles))

    @classmethod
    def _declaration_positions(cls, line: str, pattern: re.Pattern) -> set[int]:
        return {match.start(1) for match in pattern.finditer(line)}

    @classmethod
    def _parameter_ranges(cls, line: str) -> list[tuple[int, int]]:
        ranges: list[tuple[int, int]] = []
        for match in re.finditer(r"\b(?:def|function|fn|func|sub|fun)\b", line):
            opening = line.find("(", match.end())
            if opening < 0:
                continue
            closing = line.find(")", opening + 1)
            if closing >= 0:
                ranges.append((opening + 1, closing))
        for match in re.finditer(r"\(([^()]*)\)\s*=>", line):
            ranges.append((match.start(1), match.end(1)))
        for match in re.finditer(
            r"\b[A-Za-z_$][\w$<>\[\],.?]*\s+([A-Za-z_$][\w$]*)\s*\(([^()]*)\)",
            line,
        ):
            ranges.append((match.start(2), match.end(2)))
        for match in re.finditer(r"\b([A-Za-z_$][\w$]*)\s*=>", line):
            ranges.append((match.start(1), match.end(1) + 1))
        return ranges

    @staticmethod
    def _kind_for(
        line: str,
        position: int,
        name: str,
        function_positions: set[int],
        class_positions: set[int],
        parameter_ranges: list[tuple[int, int]],
    ) -> str:
        if position in function_positions:
            return "function"
        if position in class_positions:
            return "class"
        if any(start <= position < end for start, end in parameter_ranges):
            return "parameter"
        before = line[:position].rstrip()
        after = line[position + len(name) :].lstrip()
        if before.endswith(".") or after.startswith(":"):
            return "property"
        if after.startswith("("):
            return "function"
        if name.isupper() and len(name) > 1:
            return "constant"
        return "variable"


def _apply_position_styles(fragments, positions: dict[int, str]):
    if not positions:
        return fragments
    result = []
    position = 0
    for fragment in fragments:
        style, text, *extra = fragment
        start = 0
        while start < len(text):
            absolute = position + start
            decorated = positions.get(absolute)
            end = start + 1
            while end < len(text) and positions.get(position + end) == decorated:
                end += 1
            result.append((f"{style} {decorated}" if decorated else style, text[start:end], *extra))
            start = end
        position += len(text)
    return result

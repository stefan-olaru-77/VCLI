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

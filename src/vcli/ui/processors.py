"""Input processors that decorate the editor content."""

from __future__ import annotations

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

"""Search helpers shared by the find bar and the quick openers."""

from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class Match:
    start: int
    end: int

    def __len__(self) -> int:
        return self.end - self.start


def compile_query(
    query: str,
    *,
    case_sensitive: bool = False,
    whole_word: bool = False,
    regex: bool = False,
) -> re.Pattern[str]:
    pattern = query if regex else re.escape(query)
    if whole_word:
        pattern = rf"\b(?:{pattern})\b"
    flags = 0 if case_sensitive else re.IGNORECASE
    return re.compile(pattern, flags)


def find_matches(
    text: str,
    query: str,
    *,
    case_sensitive: bool = False,
    whole_word: bool = False,
    regex: bool = False,
    limit: int = 20_000,
) -> tuple[list[Match], str | None]:
    """Find all matches. Returns ``(matches, error)``."""
    if not query:
        return [], None
    try:
        pattern = compile_query(
            query,
            case_sensitive=case_sensitive,
            whole_word=whole_word,
            regex=regex,
        )
    except re.error as exc:
        return [], str(exc)
    matches: list[Match] = []
    for found in pattern.finditer(text):
        if len(matches) >= limit:
            break
        if found.start() == found.end():
            # Never loop forever on zero-width regex matches.
            continue
        matches.append(Match(found.start(), found.end()))
    return matches, None


def replacement_for(
    text: str,
    match: Match,
    query: str,
    replacement: str,
    *,
    case_sensitive: bool = False,
    whole_word: bool = False,
    regex: bool = False,
) -> str:
    """Expand a replacement, honouring ``\\1`` style groups in regex mode."""
    if not regex:
        return replacement
    try:
        compiled = compile_query(
            query,
            case_sensitive=case_sensitive,
            whole_word=whole_word,
            regex=True,
        )
        found = compiled.match(text, match.start)
    except re.error:  # pragma: no cover
        return replacement
    return found.expand(replacement) if found else replacement


def replace_range(text: str, match: Match, replacement: str) -> str:
    return text[: match.start] + replacement + text[match.end :]

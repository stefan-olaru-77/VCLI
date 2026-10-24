"""Fuzzy subsequence matching for the command palette and quick open."""

from __future__ import annotations

_BOUNDARY = " _-./\\:;,([{"


def fuzzy_match(query: str, text: str, case_sensitive: bool = False) -> tuple[float, list[int]] | None:
    """Score ``text`` against ``query``.

    Returns ``(score, matched_positions)`` or ``None`` when ``query`` is not a
    subsequence of ``text``. Higher scores are better; consecutive, prefix and
    word-boundary matches are strongly preferred.
    """
    if not query:
        return 0.0, []
    haystack = text if case_sensitive else text.lower()
    needle = query if case_sensitive else query.lower()
    if len(needle) > len(haystack):
        return None

    positions: list[int] = []
    score = 0.0
    index = 0
    last = -2
    for char in needle:
        found = haystack.find(char, index)
        if found == -1:
            return None
        if found == last + 1:
            score += 14.0
        else:
            score -= min(8.0, (found - index) * 0.6)
        if found == 0 or haystack[found - 1] in _BOUNDARY:
            score += 24.0
        elif found > 0 and haystack[found - 1].islower() and char.isupper():
            score += 12.0
        positions.append(found)
        last = found
        index = found + 1

    if positions and positions[0] == 0:
        score += 40.0
    if haystack == needle:
        score += 1000.0
    elif haystack.startswith(needle):
        score += 120.0
    # Prefer shorter, more relevant labels when scores are otherwise close.
    score -= len(text) * 0.05
    return score, positions


def filter_items(query: str, items, key=lambda item: item.label):
    """Filter and rank ``items`` by fuzzy score. Stable for equal scores."""
    if not query.strip():
        return [(item, []) for item in items]
    scored = []
    for order, item in enumerate(items):
        result = fuzzy_match(query, key(item))
        if result is not None:
            score, positions = result
            scored.append((score, order, item, positions))
    scored.sort(key=lambda entry: (-entry[0], entry[1]))
    return [(item, positions) for _, _, item, positions in scored]

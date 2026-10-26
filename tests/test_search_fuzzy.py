"""Unit tests for search and fuzzy matching."""

from __future__ import annotations

from vcli.fuzzy import filter_items, fuzzy_match
from vcli.search import Match, find_matches, replacement_for


def test_find_matches_literal_and_flags():
    matches, error = find_matches("Foo foo FOO", "foo")
    assert error is None
    assert [(m.start, m.end) for m in matches] == [(0, 3), (4, 7), (8, 11)]

    matches, _ = find_matches("Foo foo", "foo", case_sensitive=True)
    assert [m.start for m in matches] == [4]

    matches, _ = find_matches("food foo", "foo", whole_word=True)
    assert [m.start for m in matches] == [5]


def test_find_matches_regex_and_errors():
    matches, error = find_matches("a1 b22", r"\d+", regex=True)
    assert error is None
    assert [(m.start, m.end) for m in matches] == [(1, 2), (4, 6)]

    matches, error = find_matches("abc", "(", regex=True)
    assert not matches
    assert error is not None


def test_find_matches_skips_zero_width():
    matches, error = find_matches("abc", r"^|$", regex=True)
    assert error is None
    assert not matches


def test_find_matches_limit():
    matches, _ = find_matches("aaaa", "a", limit=2)
    assert len(matches) == 2


def test_replacement_for():
    assert replacement_for("foo", Match(0, 3), "foo", "bar") == "bar"
    assert (
        replacement_for("a1", Match(1, 2), r"(\d)", r"<\1>", regex=True)
        == "<1>"
    )
    assert replacement_for("a1", Match(1, 2), r"(\d)", "x", regex=True) == "x"


def test_fuzzy_match_scoring():
    assert fuzzy_match("", "anything") == (0.0, [])
    assert fuzzy_match("xyz", "abc") is None
    assert fuzzy_match("abc", "abc") is not None

    exact = fuzzy_match("main", "main.py")
    prefix = fuzzy_match("main", "domain.py")
    assert exact[0] > prefix[0]
    assert exact[1] == [0, 1, 2, 3]

    # camelCase boundary bonus
    camel = fuzzy_match("fb", "fooBar")
    assert camel is not None
    assert camel[1] == [0, 3]


def test_filter_items_ranking_and_empty_query():
    items = ["src/main.py", "main.py", "docs/main.md"]
    ranked = filter_items("main", items, key=lambda item: item)
    assert ranked[0][0] == "main.py"
    assert all(isinstance(positions, list) for _, positions in ranked)

    everything = filter_items("  ", items, key=lambda item: item)
    assert [item for item, _ in everything] == items


def test_filter_items_no_result():
    assert filter_items("zzz", ["abc"], key=lambda item: item) == []

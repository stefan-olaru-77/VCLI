"""Tests for configuration loading, validation and persistence."""

from __future__ import annotations

import json
from pathlib import Path

from vcli.config import Config, config_path


def test_defaults():
    config = Config()
    assert config.theme == "vscode-dark"
    assert config.indent_unit() == "    "
    assert config.indent_label == "Spaces: 4"
    assert config.line_height == 1
    assert config.show_status_bar is True


def test_from_dict_ignores_unknown_and_wrong_types():
    config = Config.from_dict(
        {
            "theme": "dracula",
            "tab_size": "wide",
            "mouse": "yes",
            "line_numbers": False,
            "unknown": 1,
            "recent_files": ["/a", 3, "/b"],
        }
    )
    assert config.theme == "dracula"
    assert config.tab_size == 4
    assert config.mouse is True
    assert config.line_numbers is False
    assert config.recent_files == ["/a", "/b"]


def test_sanitize_clamps_values():
    config = Config(
        tab_size=100,
        sidebar_width=1,
        scroll_off=-3,
        line_height=10,
        max_recent_files=0,
    )
    config.sanitize()
    assert config.tab_size == 16
    assert config.sidebar_width == 16
    assert config.scroll_off == 0
    assert config.line_height == 3
    assert config.max_recent_files == 1


def test_save_and_load_roundtrip(tmp_path: Path):
    path = tmp_path / "config.json"
    config = Config(theme="nord", word_wrap=True, tab_size=2)
    config.remember_file(tmp_path / "a.txt")
    config.save(path)

    raw = json.loads(path.read_text(encoding="utf-8"))
    assert raw["theme"] == "nord"

    loaded = Config.load(path)
    assert loaded.theme == "nord"
    assert loaded.word_wrap is True
    assert loaded.tab_size == 2
    assert loaded.recent_files == [str((tmp_path / "a.txt").resolve())]


def test_load_missing_or_broken_file(tmp_path: Path):
    assert Config.load(tmp_path / "nope.json") == Config()
    broken = tmp_path / "broken.json"
    broken.write_text("{not json", encoding="utf-8")
    assert Config.load(broken) == Config()
    array = tmp_path / "array.json"
    array.write_text("[1, 2]", encoding="utf-8")
    assert Config.load(array) == Config()


def test_remember_file_moves_to_front_and_dedupes(tmp_path: Path):
    config = Config(max_recent_files=2)
    config.remember_file(tmp_path / "a")
    config.remember_file(tmp_path / "b")
    config.remember_file(tmp_path / "a")
    assert [Path(p).name for p in config.recent_files] == ["a", "b"]

    config.remember_file(tmp_path / "c")
    assert [Path(p).name for p in config.recent_files] == ["c", "a"]


def test_config_path_env(monkeypatch, tmp_path: Path):
    monkeypatch.setenv("VCLI_CONFIG", str(tmp_path / "custom.json"))
    assert config_path() == tmp_path / "custom.json"

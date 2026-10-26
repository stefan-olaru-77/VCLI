"""User configuration (``~/.config/vcli/config.json``)."""

from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass, field, fields
from pathlib import Path
from typing import Any

CONFIG_ENV = "VCLI_CONFIG"


def config_path() -> Path:
    """Return the configuration file location.

    ``$VCLI_CONFIG`` wins, then ``$XDG_CONFIG_HOME/vcli/config.json`` and
    finally ``~/.config/vcli/config.json``.
    """
    override = os.environ.get(CONFIG_ENV)
    if override:
        return Path(override).expanduser()
    base = os.environ.get("XDG_CONFIG_HOME")
    root = Path(base).expanduser() if base else Path.home() / ".config"
    return root / "vcli" / "config.json"


@dataclass
class Config:
    """Persistent editor settings.

    Every field is persisted as-is in JSON; unknown keys in an existing config
    file are ignored so that downgrading stays painless.
    """

    theme: str = "vscode-dark"
    tab_size: int = 4
    use_spaces: bool = True
    detect_indentation: bool = True
    detect_language: bool = True
    line_numbers: bool = True
    relative_line_numbers: bool = False
    highlight_current_line: bool = True
    line_height: int = 1
    word_wrap: bool = False
    show_sidebar: bool = True
    sidebar_width: int = 32
    mouse: bool = True
    copy_on_select: bool = True
    cursor_blink: bool = True
    scroll_off: int = 3
    auto_indent: bool = True
    auto_close_brackets: bool = True
    auto_closing_quotes: bool = True
    auto_closing_comments: bool = True
    bracket_pair_colorization: bool = True
    color_decorators: bool = True
    format_on_save: bool = False
    code_folding: bool = True
    trim_trailing_whitespace_on_save: bool = False
    confirm_exit: bool = True
    show_tab_bar: bool = True
    show_status_bar: bool = True
    show_hidden_files: bool = False
    recent_files: list[str] = field(default_factory=list)
    max_recent_files: int = 12

    # ------------------------------------------------------------------ load
    @classmethod
    def load(cls, path: Path | None = None) -> Config:
        path = path or config_path()
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return cls()
        if not isinstance(raw, dict):
            return cls()
        return cls.from_dict(raw)

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> Config:
        known = {f.name: f for f in fields(cls)}
        values: dict[str, Any] = {}
        for key, value in raw.items():
            spec = known.get(key)
            if spec is None:
                continue
            if key == "recent_files":
                if isinstance(value, list):
                    values[key] = [str(v) for v in value if isinstance(v, str)][
                        : cls.max_recent_files
                    ]
                continue
            default = spec.default
            if isinstance(default, bool):
                if isinstance(value, bool):
                    values[key] = value
            elif isinstance(default, int):
                if isinstance(value, int) and not isinstance(value, bool):
                    values[key] = value
            elif isinstance(default, str):
                if isinstance(value, str):
                    values[key] = value
        cfg = cls(**values)
        cfg.sanitize()
        return cfg

    def sanitize(self) -> None:
        self.tab_size = max(1, min(16, int(self.tab_size)))
        self.sidebar_width = max(16, min(80, int(self.sidebar_width)))
        self.scroll_off = max(0, min(20, int(self.scroll_off)))
        self.line_height = max(1, min(3, int(self.line_height)))
        self.max_recent_files = max(1, min(100, int(self.max_recent_files)))
        self.recent_files = self.recent_files[: self.max_recent_files]

    # ------------------------------------------------------------------ save
    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def save(self, path: Path | None = None) -> None:
        path = path or config_path()
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            tmp = path.with_suffix(path.suffix + ".tmp")
            tmp.write_text(
                json.dumps(self.to_dict(), indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
            tmp.replace(path)
        except OSError:
            # A read-only home should never take the editor down.
            pass

    # --------------------------------------------------------------- helpers
    def remember_file(self, path: Path | str) -> None:
        entry = str(Path(path).expanduser().resolve())
        self.recent_files = [entry] + [p for p in self.recent_files if p != entry]
        del self.recent_files[self.max_recent_files :]

    def indent_unit(self) -> str:
        return " " * self.tab_size if self.use_spaces else "\t"

    @property
    def indent_label(self) -> str:
        return f"Spaces: {self.tab_size}" if self.use_spaces else "Tab Size: " + str(
            self.tab_size
        )

"""Colour themes and prompt_toolkit style construction.

A theme is described once as a small palette (``ThemeSpec``); all the
individual UI style classes are derived from it so that every theme stays
consistent across the tab bar, explorer, status bar, find widget and picker.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from prompt_toolkit.styles import BaseStyle, Style


@dataclass(frozen=True)
class ThemeSpec:
    key: str
    label: str
    bg: str
    fg: str
    muted: str
    border: str
    panel_bg: str
    accent: str
    accent_fg: str
    status_bg: str
    status_fg: str
    gutter_bg: str
    line_number: str
    line_number_current: str
    current_line: str
    selection_bg: str
    cursor: str
    tab_active_bg: str
    tab_inactive_bg: str
    input_bg: str
    selected_bg: str
    match_bg: str
    match_current_bg: str
    error: str
    warning: str
    success: str
    syntax: dict[str, str] = field(default_factory=dict)


_DARK_SYNTAX = {
    "pygments.comment": "#6a9955 italic",
    "pygments.keyword": "#569cd6",
    "pygments.keyword.type": "#4ec9b0",
    "pygments.keyword.constant": "#569cd6",
    "pygments.operator": "#d4d4d4",
    "pygments.punctuation": "#d4d4d4",
    "pygments.name": "#d4d4d4",
    "pygments.name.builtin": "#4ec9b0",
    "pygments.name.function": "#dcdcaa",
    "pygments.name.class": "#4ec9b0",
    "pygments.name.decorator": "#dcdcaa",
    "pygments.name.attribute": "#9cdcfe",
    "pygments.name.variable": "#9cdcfe",
    "pygments.name.constant": "#4fc1ff",
    "pygments.name.tag": "#569cd6",
    "pygments.literal.string": "#ce9178",
    "pygments.literal.string.doc": "#6a9955",
    "pygments.literal.string.escape": "#d7ba7d",
    "pygments.literal.number": "#b5cea8",
    "pygments.literal": "#ce9178",
    "pygments.generic.heading": "bold underline",
    "pygments.generic.deleted": "#f44747",
    "pygments.generic.inserted": "#6a9955",
    "pygments.error": "#f44747",
}

_LIGHT_SYNTAX = {
    "pygments.comment": "#008000 italic",
    "pygments.keyword": "#0000ff",
    "pygments.keyword.type": "#267f99",
    "pygments.keyword.constant": "#0000ff",
    "pygments.operator": "#000000",
    "pygments.punctuation": "#000000",
    "pygments.name": "#001080",
    "pygments.name.builtin": "#267f99",
    "pygments.name.function": "#795e26",
    "pygments.name.class": "#267f99",
    "pygments.name.decorator": "#795e26",
    "pygments.name.attribute": "#e50000",
    "pygments.name.variable": "#001080",
    "pygments.name.constant": "#0070c1",
    "pygments.name.tag": "#800000",
    "pygments.literal.string": "#a31515",
    "pygments.literal.string.doc": "#008000",
    "pygments.literal.string.escape": "#ee0000",
    "pygments.literal.number": "#098658",
    "pygments.literal": "#a31515",
    "pygments.generic.heading": "bold underline",
    "pygments.generic.deleted": "#a31515",
    "pygments.generic.inserted": "#008000",
    "pygments.error": "#cd3131",
}


THEMES: dict[str, ThemeSpec] = {
    "vscode-dark": ThemeSpec(
        key="vscode-dark",
        label="Dark+ (default dark)",
        bg="#1e1e1e",
        fg="#d4d4d4",
        muted="#858585",
        border="#3c3c3c",
        panel_bg="#252526",
        accent="#0e639c",
        accent_fg="#ffffff",
        status_bg="#007acc",
        status_fg="#ffffff",
        gutter_bg="#1e1e1e",
        line_number="#858585",
        line_number_current="#c6c6c6",
        current_line="#262626",
        selection_bg="#264f78",
        cursor="#aeafad",
        tab_active_bg="#1e1e1e",
        tab_inactive_bg="#2d2d2d",
        input_bg="#3c3c3c",
        selected_bg="#04395e",
        match_bg="#3a3d41",
        match_current_bg="#613214",
        error="#f44747",
        warning="#cca700",
        success="#89d185",
        syntax=_DARK_SYNTAX,
    ),
    "vscode-light": ThemeSpec(
        key="vscode-light",
        label="Light+ (default light)",
        bg="#ffffff",
        fg="#333333",
        muted="#6e7681",
        border="#e5e5e5",
        panel_bg="#f3f3f3",
        accent="#007acc",
        accent_fg="#ffffff",
        status_bg="#007acc",
        status_fg="#ffffff",
        gutter_bg="#ffffff",
        line_number="#999999",
        line_number_current="#333333",
        current_line="#f5f5f5",
        selection_bg="#add6ff",
        cursor="#333333",
        tab_active_bg="#ffffff",
        tab_inactive_bg="#ececec",
        input_bg="#ffffff",
        selected_bg="#e4e6f1",
        match_bg="#ffe9a8",
        match_current_bg="#f8a500",
        error="#cd3131",
        warning="#bf8803",
        success="#16825d",
        syntax=_LIGHT_SYNTAX,
    ),
    "dracula": ThemeSpec(
        key="dracula",
        label="Dracula",
        bg="#282a36",
        fg="#f8f8f2",
        muted="#6272a4",
        border="#44475a",
        panel_bg="#21222c",
        accent="#bd93f9",
        accent_fg="#282a36",
        status_bg="#44475a",
        status_fg="#f8f8f2",
        gutter_bg="#282a36",
        line_number="#6272a4",
        line_number_current="#f8f8f2",
        current_line="#343746",
        selection_bg="#44475a",
        cursor="#f8f8f2",
        tab_active_bg="#282a36",
        tab_inactive_bg="#21222c",
        input_bg="#44475a",
        selected_bg="#44475a",
        match_bg="#55597a",
        match_current_bg="#ffb86c",
        error="#ff5555",
        warning="#f1fa8c",
        success="#50fa7b",
        syntax={
            "pygments.comment": "#6272a4 italic",
            "pygments.keyword": "#ff79c6",
            "pygments.keyword.type": "#8be9fd italic",
            "pygments.keyword.constant": "#bd93f9",
            "pygments.operator": "#ff79c6",
            "pygments.punctuation": "#f8f8f2",
            "pygments.name": "#f8f8f2",
            "pygments.name.builtin": "#8be9fd italic",
            "pygments.name.function": "#50fa7b",
            "pygments.name.class": "#8be9fd",
            "pygments.name.decorator": "#50fa7b",
            "pygments.name.attribute": "#50fa7b",
            "pygments.name.variable": "#f8f8f2",
            "pygments.name.constant": "#bd93f9",
            "pygments.name.tag": "#ff79c6",
            "pygments.literal.string": "#f1fa8c",
            "pygments.literal.string.doc": "#6272a4",
            "pygments.literal.string.escape": "#ff79c6",
            "pygments.literal.number": "#bd93f9",
            "pygments.literal": "#f1fa8c",
            "pygments.generic.deleted": "#ff5555",
            "pygments.generic.inserted": "#50fa7b",
            "pygments.error": "#ff5555",
        },
    ),
    "monokai": ThemeSpec(
        key="monokai",
        label="Monokai",
        bg="#272822",
        fg="#f8f8f2",
        muted="#75715e",
        border="#49483e",
        panel_bg="#1e1f1c",
        accent="#fd971f",
        accent_fg="#272822",
        status_bg="#414339",
        status_fg="#f8f8f2",
        gutter_bg="#272822",
        line_number="#90908a",
        line_number_current="#f8f8f2",
        current_line="#3e3d32",
        selection_bg="#49483e",
        cursor="#f8f8f0",
        tab_active_bg="#272822",
        tab_inactive_bg="#1e1f1c",
        input_bg="#3e3d32",
        selected_bg="#49483e",
        match_bg="#575642",
        match_current_bg="#fd971f",
        error="#f92672",
        warning="#e6db74",
        success="#a6e22e",
        syntax={
            "pygments.comment": "#75715e italic",
            "pygments.keyword": "#f92672",
            "pygments.keyword.type": "#66d9ef italic",
            "pygments.keyword.constant": "#ae81ff",
            "pygments.operator": "#f92672",
            "pygments.punctuation": "#f8f8f2",
            "pygments.name": "#f8f8f2",
            "pygments.name.builtin": "#66d9ef italic",
            "pygments.name.function": "#a6e22e",
            "pygments.name.class": "#a6e22e",
            "pygments.name.decorator": "#a6e22e",
            "pygments.name.attribute": "#a6e22e",
            "pygments.name.variable": "#f8f8f2",
            "pygments.name.constant": "#ae81ff",
            "pygments.name.tag": "#f92672",
            "pygments.literal.string": "#e6db74",
            "pygments.literal.string.doc": "#75715e",
            "pygments.literal.string.escape": "#ae81ff",
            "pygments.literal.number": "#ae81ff",
            "pygments.literal": "#e6db74",
            "pygments.generic.deleted": "#f92672",
            "pygments.generic.inserted": "#a6e22e",
            "pygments.error": "#f92672",
        },
    ),
    "nord": ThemeSpec(
        key="nord",
        label="Nord",
        bg="#2e3440",
        fg="#d8dee9",
        muted="#616e88",
        border="#3b4252",
        panel_bg="#2b303b",
        accent="#88c0d0",
        accent_fg="#2e3440",
        status_bg="#3b4252",
        status_fg="#e5e9f0",
        gutter_bg="#2e3440",
        line_number="#4c566a",
        line_number_current="#d8dee9",
        current_line="#3b4252",
        selection_bg="#434c5e",
        cursor="#d8dee9",
        tab_active_bg="#2e3440",
        tab_inactive_bg="#2b303b",
        input_bg="#3b4252",
        selected_bg="#434c5e",
        match_bg="#4c566a",
        match_current_bg="#ebcb8b",
        error="#bf616a",
        warning="#ebcb8b",
        success="#a3be8c",
        syntax={
            "pygments.comment": "#616e88 italic",
            "pygments.keyword": "#81a1c1",
            "pygments.keyword.type": "#8fbcbb italic",
            "pygments.keyword.constant": "#81a1c1",
            "pygments.operator": "#81a1c1",
            "pygments.punctuation": "#eceff4",
            "pygments.name": "#d8dee9",
            "pygments.name.builtin": "#8fbcbb",
            "pygments.name.function": "#88c0d0",
            "pygments.name.class": "#8fbcbb",
            "pygments.name.decorator": "#d08770",
            "pygments.name.attribute": "#88c0d0",
            "pygments.name.variable": "#d8dee9",
            "pygments.name.constant": "#81a1c1",
            "pygments.name.tag": "#81a1c1",
            "pygments.literal.string": "#a3be8c",
            "pygments.literal.string.doc": "#616e88",
            "pygments.literal.string.escape": "#ebcb8b",
            "pygments.literal.number": "#b48ead",
            "pygments.literal": "#a3be8c",
            "pygments.generic.deleted": "#bf616a",
            "pygments.generic.inserted": "#a3be8c",
            "pygments.error": "#bf616a",
        },
    ),
    "mc": ThemeSpec(
        key="mc",
        label="Midnight Commander",
        bg="#000080",
        fg="#ffffff",
        muted="#aaaaaa",
        border="#00aaaa",
        panel_bg="#000080",
        accent="#00ffff",
        accent_fg="#000080",
        status_bg="#00aaaa",
        status_fg="#000000",
        gutter_bg="#000080",
        line_number="#aaaaaa",
        line_number_current="#ffffff",
        current_line="#000080",
        selection_bg="#0000aa",
        cursor="#ffffff",
        tab_active_bg="#000080",
        tab_inactive_bg="#0000aa",
        input_bg="#0000aa",
        selected_bg="#0000aa",
        match_bg="#008080",
        match_current_bg="#00aaaa",
        error="#ff5555",
        warning="#ffff00",
        success="#00ff00",
        syntax={
            "pygments.comment": "#00ff00 italic",
            "pygments.keyword": "#00ffff",
            "pygments.name.function": "#ffff00",
            "pygments.name.class": "#ffff00",
            "pygments.literal.string": "#00ff00",
            "pygments.literal.number": "#00ffff",
            "pygments.error": "#ff5555",
        },
    ),
}

DEFAULT_THEME = "vscode-dark"


def theme_names() -> list[str]:
    return list(THEMES)


def get_theme(name: str) -> ThemeSpec:
    return THEMES.get(name, THEMES[DEFAULT_THEME])


def resolve_theme_key(name: str) -> str:
    return name if name in THEMES else DEFAULT_THEME


def style_dict(spec: ThemeSpec) -> dict[str, str]:
    """Expand a palette into the full set of UI style classes."""
    styles: dict[str, str] = {
        # Base / caret / selection
        "": f"{spec.fg} bg:{spec.bg}",
        "cursor": f"bg:{spec.cursor} {spec.bg}",
        "selected-text": f"bg:{spec.selection_bg} {spec.fg}",
        # Gutter / editor decorations
        "editor": f"bg:{spec.bg} {spec.fg}",
        "line-number": f"bg:{spec.gutter_bg} {spec.line_number}",
        "line-number.current": f"bg:{spec.gutter_bg} {spec.line_number_current} bold",
        "cursor-line": f"bg:{spec.current_line}",
        "matching-bracket.cursor": f"bg:{spec.match_current_bg} {spec.bg} bold",
        "matching-bracket.other": f"bg:{spec.match_bg} {spec.fg} bold",
        "search.match": f"bg:{spec.match_bg} {spec.fg}",
        "search.match.current": f"bg:{spec.match_current_bg} {spec.bg} bold",
        # Tab bar
        "tabbar": f"bg:{spec.panel_bg} {spec.fg}",
        "tabbar.tab": f"bg:{spec.tab_inactive_bg} {spec.fg}",
        "tabbar.tab.active": f"bg:{spec.tab_active_bg} {spec.fg} bold",
        "tabbar.modified": f"bg:{spec.tab_active_bg} {spec.warning}",
        "tabbar.close": f"bg:{spec.tab_inactive_bg} {spec.muted}",
        "tabbar.close.active": f"bg:{spec.tab_active_bg} {spec.muted}",
        "tabbar.separator": f"bg:{spec.panel_bg} {spec.border}",
        "tabbar.overflow": f"bg:{spec.panel_bg} {spec.muted}",
        "chrome.separator": f"bg:{spec.border} {spec.border}",
        "menubar": f"bg:{spec.panel_bg} {spec.fg}",
        "menubar.item": f"bg:{spec.panel_bg} {spec.fg}",
        # Explorer / sidebar
        "sidebar": f"bg:{spec.panel_bg} {spec.fg}",
        "sidebar.title": f"bg:{spec.panel_bg} {spec.muted} bold",
        "sidebar.title.root": f"bg:{spec.panel_bg} {spec.fg} bold",
        "sidebar.item": f"bg:{spec.panel_bg} {spec.fg}",
        "sidebar.item.selected": f"bg:{spec.selected_bg} {spec.fg}",
        "sidebar.item.active": f"bg:{spec.panel_bg} {spec.accent}",
        "sidebar.dir": f"bg:{spec.panel_bg} {spec.fg}",
        "sidebar.chevron": f"bg:{spec.panel_bg} {spec.muted}",
        "sidebar.hidden": f"bg:{spec.panel_bg} {spec.muted}",
        # Status bar
        "statusbar": f"bg:{spec.status_bg} {spec.status_fg}",
        "statusbar.item": f"bg:{spec.status_bg} {spec.status_fg}",
        "statusbar.muted": f"bg:{spec.status_bg} {spec.status_fg}",
        "statusbar.branch": f"bg:{spec.status_bg} {spec.status_fg} bold",
        "statusbar.modified": f"bg:{spec.status_bg} {spec.warning}",
        "statusbar.message": f"bg:{spec.status_bg} {spec.status_fg}",
        "statusbar.error": f"bg:{spec.error} {spec.status_fg} bold",
        # Find widget
        "findbar": f"bg:{spec.panel_bg} {spec.fg}",
        "findbar.label": f"bg:{spec.panel_bg} {spec.muted}",
        "findbar.input": f"bg:{spec.input_bg} {spec.fg}",
        "findbar.input.focused": f"bg:{spec.input_bg} {spec.fg}",
        "findbar.toggle": f"bg:{spec.panel_bg} {spec.muted}",
        "findbar.toggle.on": f"bg:{spec.accent} {spec.accent_fg} bold",
        "findbar.count": f"bg:{spec.panel_bg} {spec.muted}",
        "findbar.error": f"bg:{spec.panel_bg} {spec.error} bold",
        "findbar.hint": f"bg:{spec.panel_bg} {spec.muted}",
        # Picker / command palette
        "picker": f"bg:{spec.panel_bg} {spec.fg}",
        "picker.border": f"bg:{spec.panel_bg} {spec.border}",
        "picker.input": f"bg:{spec.input_bg} {spec.fg}",
        "picker.input.title": f"bg:{spec.input_bg} {spec.muted}",
        "picker.prompt": f"bg:{spec.input_bg} {spec.accent} bold",
        "picker.tabs": f"bg:{spec.panel_bg} {spec.muted}",
        "picker.tabs.item": f"bg:{spec.panel_bg} {spec.muted}",
        "picker.tabs.selected": f"bg:{spec.accent} {spec.accent_fg} bold",
        "picker.item": f"bg:{spec.panel_bg} {spec.fg}",
        "picker.item.selected": f"bg:{spec.selected_bg} {spec.fg} bold",
        "picker.item.description": f"bg:{spec.panel_bg} {spec.muted}",
        "picker.item.selected.description": f"bg:{spec.selected_bg} {spec.muted}",
        "picker.item.key": f"bg:{spec.panel_bg} {spec.accent}",
        "picker.item.selected.key": f"bg:{spec.selected_bg} {spec.accent}",
        "picker.match": f"bg:{spec.panel_bg} {spec.accent} bold",
        "picker.match.selected": f"bg:{spec.selected_bg} {spec.accent} bold",
        "picker.empty": f"bg:{spec.panel_bg} {spec.muted}",
        "picker.footer": f"bg:{spec.panel_bg} {spec.muted}",
        "picker.shadow": "bg:#000000",
        "picker.menu.item": f"bg:{spec.bg} {spec.fg}",
        "picker.menu.item.selected": f"bg:{spec.accent} {spec.accent_fg} bold",
        "picker.menu.item.description": f"bg:{spec.bg} {spec.muted}",
        "picker.menu.item.selected.description": f"bg:{spec.accent} {spec.accent_fg}",
        "picker.menu.item.key": f"bg:{spec.bg} {spec.accent}",
        "picker.menu.item.selected.key": f"bg:{spec.accent} {spec.accent_fg}",
        # Misc
        "separator": f"bg:{spec.bg} {spec.border}",
        "window-border": f"bg:{spec.panel_bg} {spec.border}",
        "warning": f"bg:{spec.panel_bg} {spec.warning}",
        "error": f"bg:{spec.panel_bg} {spec.error} bold",
        "success": f"bg:{spec.panel_bg} {spec.success}",
        "welcome": f"bg:{spec.bg} {spec.fg}",
        "welcome.muted": f"bg:{spec.bg} {spec.muted}",
        "welcome.key": f"bg:{spec.bg} {spec.accent} bold",
        "welcome.title": f"bg:{spec.bg} {spec.accent} bold",
        # Completions (Ctrl+Space)
        "completion-menu.completion": f"bg:{spec.panel_bg} {spec.fg}",
        "completion-menu.completion.current": f"bg:{spec.selected_bg} {spec.fg} bold",
        "completion-menu.meta.completion": f"bg:{spec.panel_bg} {spec.muted}",
        "completion-menu.meta.completion.current": f"bg:{spec.selected_bg} {spec.muted}",
        "scrollbar.background": f"bg:{spec.panel_bg}",
        "scrollbar.button": f"bg:{spec.border}",
        "menu-border": f"bg:{spec.border}",
    }
    styles.update(spec.syntax)
    return styles


def build_style(name: str) -> BaseStyle:
    return Style.from_dict(style_dict(get_theme(name)))

# vcli

A VSCode-like editor that runs in the Linux terminal.
Built with [prompt_toolkit](https://github.com/prompt-toolkit/python-prompt-toolkit)
and [Pygments](https://pygments.org/). No GUI, no Electron: just your terminal.

```
┌ EXPLORER ──────┬──────────────────────────────────────────────────┐
│ ▾ src/         │ ● app.py  │ main.py │                         │
│   app.py       ├──────────────────────────────────────────────────┤
│   main.py      │  1 │ """Entry point."""                           │
│ README.md      │  2 │ import sys                                   │
│                │  3 │                                              │
├────────────────┴──────────────────────────────────────────────────┤
│  main  ●  Saved              Ln 2, Col 8   Spaces: 4   Python     │
└───────────────────────────────────────────────────────────────────┘
```

## Features

- **Editor**: syntax highlighting, absolute or relative line numbers,
  current-line highlight, configurable line height, word wrap, auto-indent,
  indentation/language detection, auto-closing brackets, quotes and comments,
  bracket pair colorization, color decorators, code folding and completion.
- **VSCode-style chrome**: File/Edit menus, editor-aligned tabs, separators,
  MC-inspired borders, centered dialogs and drop shadows.
- **Tabs**: one tab per file, dirty marker, blinking block cursor, mouse and
  keyboard switching.
- **Explorer**: lazy file tree, full-row selection, expand/collapse, hidden
  files, quick open, active-file reveal, and filtered system directories.
- **Find & replace**: live highlighting of all matches, current match,
  case/whole-word/regex toggles, replace one or replace all.
- **Command palette**: fuzzy search over every command, including themes and
  settings.
- **Themes**: `vscode-dark`, `vscode-light`, `dracula`, `monokai`, `nord`,
  and `mc` (Midnight Commander).
- **Files**: encoding-aware reading (UTF-8, BOM, latin-1 fallback),
  CRLF/LF preservation, atomic saves, large-file and binary-file guards.
- **Status bar**: git branch, cursor position, indentation, encoding, EOL,
  language.
- **Settings**: F1 opens the command palette; choose `Preferences: Open
  Settings` for searchable `Editor`, `Files`, `Workbench`, and `Theme` tabs.
  Changes persist to JSON.

## Requirements

- Linux (or any POSIX terminal; macOS should work too)
- Python 3.10+
- A terminal with 256-colour support (true colour recommended)

## Install

```bash
cd vscode-cli
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
vcli
```

Open a folder and a file:

```bash
vcli -w ~/projects/my-app src/main.py
```

Run from a checkout without installing:

```bash
python run.py -w ~/projects/my-app
```

### CLI options

```
vcli [paths...] [-w DIR] [--theme NAME] [--tab-size N]
     [--no-sidebar] [--no-mouse] [--relative-numbers]
     [--config FILE] [--no-config] [--version]
```

If the first path is a directory it becomes the workspace. If only files are
given, the workspace is the first file's folder.

## Keyboard shortcuts

| Keys | Action |
| --- | --- |
| `Ctrl+N` | New file |
| `Ctrl+O` / `Ctrl+P` | Open file (quick open) |
| `Ctrl+S` | Save |
| `Ctrl+W` | Close editor |
| `Ctrl+Q` | Quit |
| `Ctrl+PageDown` / `Ctrl+PageUp` | Next / previous editor |
| `Ctrl+B` | Toggle sidebar |
| `F1` | Command palette |
| `F9` | Open File menu |
| `Ctrl+F9` | Toggle code folding |
| `Ctrl+G` | Go to line |
| `Ctrl+F` | Find |
| `Ctrl+R` | Find and replace |
| `Enter` (find bar) | Next match (or replace current in replace field) |
| `F3` / `F4` | Next / previous match |
| `F5` | Replace all |
| `F6` / `F7` / `F8` | Toggle case / whole word / regex |
| `Tab` / `Shift+Tab` | Switch find fields / indent / outdent |
| `Ctrl+Z` / `Ctrl+Y` | Undo / redo |
| `Ctrl+A` | Select all |
| `Ctrl+C` / `Ctrl+X` / `Ctrl+V` | Copy / cut / paste |
| `Ctrl+D` | Duplicate line |
| `Ctrl+K` | Delete line |
| `Ctrl+Up` / `Ctrl+Down` | Move line up / down |
| `Ctrl+/` (terminal may send `Ctrl+_`) | Toggle line comment |
| `F10` | Toggle word wrap |
| `Ctrl+Space` | Word completion |
| `Esc` | Close overlay / clear selection |

In the explorer: arrows or `j`/`k` navigate, `Enter`/`Space` opens or toggles,
`Right`/`Left` (or `l`/`h`) expand/collapse, `r` refreshes, `Tab` returns to
the editor.

Click a tab to activate it, or its `✕` to close it (the click is handled on
press, so a slightly wobbly release still closes the tab). `Ctrl+W` closes
the current editor from the keyboard.

In the File/Edit menus, use the mouse or `Up`/`Down` and `Enter`; `Esc` closes
the menu. In the command palette: type to fuzzy-filter, `Up`/`Down` (or
`Ctrl+P`/`Ctrl+N`) to move, `Enter` to run, `Tab` to complete the query, and
`Esc` to cancel. In Settings, click a tab or use `Left`/`Right` and
`Tab`/`Shift+Tab` to switch sections.
Quick open (`Ctrl+P`) also offers a **Create file** entry for unknown paths.

## Find bar

- Matches are highlighted live while you type.
- The query is prefilled with the selected text or the word under the cursor
  and is selected, so typing replaces it.
- `Aa`, `ab`, `.*` toggle case sensitivity, whole word and regular expressions.
- Regex replacements support groups: search `(\w+)@(\w+)` and replace
  `\2 at \1`.
- `F5` replaces every match in one undoable step.

## Configuration

Settings live in `$VCLI_CONFIG`, else `$XDG_CONFIG_HOME/vcli/config.json`,
else `~/.config/vcli/config.json`:

```json
{
  "theme": "dracula",
  "tab_size": 4,
  "use_spaces": true,
  "detect_indentation": true,
  "detect_language": true,
  "line_numbers": true,
  "relative_line_numbers": false,
  "highlight_current_line": true,
  "line_height": 1,
  "word_wrap": false,
  "show_sidebar": true,
  "show_tab_bar": true,
  "show_status_bar": true,
  "show_hidden_files": false,
  "mouse": true,
  "auto_indent": true,
  "auto_close_brackets": true,
  "auto_closing_quotes": true,
  "auto_closing_comments": true,
  "bracket_pair_colorization": true,
  "color_decorators": true,
  "format_on_save": false,
  "code_folding": true,
  "trim_trailing_whitespace_on_save": false,
  "confirm_exit": true
}
```

Unknown or invalid keys are ignored, so hand-edited configs stay safe.
The theme and view toggles changed from the palette are written back on exit.
Use `F1` → `Preferences: Open Settings` to search and change these options
inside the application. `line_height` accepts values from 1 to 3.

## Terminal tips

- **Ctrl+S freezes the terminal?** Your terminal has XON/XOFF flow control
  enabled. Run `stty -ixon` (add it to your shell profile) or use
  `stty -ixon; vcli`.
- Mouse support needs a terminal that reports mouse events; toggle it with
  `View: Toggle Mouse Support` in the palette.
- In Konsole, enable mouse reporting for the terminal profile/application if
  clicks are not reaching vcli. Every mouse-driven control also has keyboard
  navigation.
- If colours look wrong, try a true-colour terminal (`COLORTERM=truecolor`)
  and set `TERM=xterm-256color`.
- Paste is handled by the terminal; on some terminals use
  `Ctrl+Shift+V` instead of `Ctrl+V`.

## Development

```bash
pip install -e ".[dev]"
python -m pytest
```

The test-suite covers the pure text operations, search/fuzzy matching,
file I/O, the workspace tree, configuration and headless integration flows
that drive the real key bindings (`tests/test_app.py`).

Project layout:

```
src/vcli/
  app.py          layout, commands, key bindings, document lifecycle
  actions.py      pure text transformations (no prompt_toolkit imports)
  fileio.py       encoding/EOL-safe reads, atomic writes
  workspace.py    lazy file tree + quick-open scan
  search.py       literal/regex search and replacement expansion
  fuzzy.py        fuzzy subsequence scoring
  languages.py    suffix -> language, lexer and comment syntax
  theme.py        theme palettes -> prompt_toolkit styles
  config.py       persisted settings
  ui/             editor pane, gutter, find bar, picker, tabs, tree, status
  processors.py   bracket coloring and color-decorator processors
```

## Roadmap

- Split view and multi-cursor editing
- Git gutter (added/modified/deleted markers) and diff view
- Integrated terminal panel
- File operations in the explorer (rename, delete, new file/folder)
- Persistent undo history and session restore
- LSP client for completion and diagnostics

## License

MIT

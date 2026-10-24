"""Command line entry point."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from . import APP_NAME, __version__
from .config import Config, config_path
from .theme import DEFAULT_THEME, resolve_theme_key, theme_names


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog=APP_NAME,
        description="A VSCode-like editor for the Linux terminal.",
        epilog=(
            "Examples:\n"
            "  vcli                     open the current folder\n"
            "  vcli src/app.py          open a file (workspace = its folder)\n"
            "  vcli -w ~/project        open a folder as the workspace\n"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("paths", nargs="*", help="files or a folder to open")
    parser.add_argument("-w", "--workspace", metavar="DIR", help="workspace folder")
    parser.add_argument(
        "--theme",
        choices=theme_names(),
        default=None,
        help=f"colour theme (default: {DEFAULT_THEME})",
    )
    parser.add_argument("--tab-size", type=int, default=None, help="indentation width")
    parser.add_argument("--no-sidebar", action="store_true", help="start without the explorer")
    parser.add_argument("--no-mouse", action="store_true", help="disable mouse support")
    parser.add_argument(
        "--relative-numbers", action="store_true", help="start with relative line numbers"
    )
    parser.add_argument(
        "--config",
        metavar="FILE",
        default=None,
        help=f"config file (default: {config_path()})",
    )
    parser.add_argument(
        "--no-config", action="store_true", help="do not read or write the config file"
    )
    parser.add_argument(
        "--version", action="version", version=f"{APP_NAME} {__version__}"
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if not sys.stdout.isatty() or not sys.stdin.isatty():
        parser.error("vcli needs an interactive terminal (stdin/stdout are not a TTY)")

    config_file = Path(args.config).expanduser() if args.config else None
    config = Config() if args.no_config else Config.load(config_file)

    if args.theme:
        config.theme = resolve_theme_key(args.theme)
    else:
        config.theme = resolve_theme_key(config.theme)
    if args.tab_size:
        config.tab_size = max(1, min(16, args.tab_size))
    if args.no_sidebar:
        config.show_sidebar = False
    if args.no_mouse:
        config.mouse = False
    if args.relative_numbers:
        config.relative_line_numbers = True

    paths = [Path(p).expanduser() for p in args.paths]
    files: list[Path] = []
    workspace_root: Path | None = Path(args.workspace).expanduser() if args.workspace else None

    for path in paths:
        if path.is_dir() and workspace_root is None:
            workspace_root = path
        else:
            files.append(path)

    if workspace_root is None:
        if files:
            workspace_root = (files[0].absolute().parent)
        else:
            workspace_root = Path.cwd()

    if not workspace_root.exists():
        parser.error(f"workspace folder does not exist: {workspace_root}")

    # Imported late so that --help/--version stay fast and dependency-free.
    from .app import EditorApp

    app = EditorApp(
        files,
        config=config,
        workspace_root=workspace_root,
        config_file=config_file,
    )
    try:
        app.run()
    except KeyboardInterrupt:
        pass
    finally:
        if not args.no_config:
            config.save(config_file)
    return 0

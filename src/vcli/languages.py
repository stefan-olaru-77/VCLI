"""Language detection, lexers and comment syntax."""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from prompt_toolkit.lexers import Lexer


@dataclass(frozen=True)
class Language:
    name: str
    lexer: str | None
    line_comment: str | None = None
    block_comment: tuple[str, str] | None = None

    @property
    def has_comments(self) -> bool:
        return bool(self.line_comment or self.block_comment)


PLAIN_TEXT = Language("Plain Text", None)


# suffix -> language. Keep this table explicit: it is the single source of
# truth for highlighting *and* for "toggle comment".
_BY_SUFFIX: dict[str, Language] = {
    ".py": Language("Python", "python", "#"),
    ".pyi": Language("Python", "python", "#"),
    ".pyw": Language("Python", "python", "#"),
    ".js": Language("JavaScript", "javascript", "//", ("/*", "*/")),
    ".mjs": Language("JavaScript", "javascript", "//", ("/*", "*/")),
    ".cjs": Language("JavaScript", "javascript", "//", ("/*", "*/")),
    ".jsx": Language("JavaScript React", "jsx", "//", ("/*", "*/")),
    ".ts": Language("TypeScript", "typescript", "//", ("/*", "*/")),
    ".mts": Language("TypeScript", "typescript", "//", ("/*", "*/")),
    ".cts": Language("TypeScript", "typescript", "//", ("/*", "*/")),
    ".tsx": Language("TypeScript React", "tsx", "//", ("/*", "*/")),
    ".json": Language("JSON", "json"),
    ".jsonc": Language("JSON with Comments", "json", "//", ("/*", "*/")),
    ".json5": Language("JSON5", "json", "//", ("/*", "*/")),
    ".md": Language("Markdown", "markdown", None, ("<!--", "-->")),
    ".markdown": Language("Markdown", "markdown", None, ("<!--", "-->")),
    ".rst": Language("reStructuredText", "rst"),
    ".html": Language("HTML", "html", None, ("<!--", "-->")),
    ".htm": Language("HTML", "html", None, ("<!--", "-->")),
    ".xml": Language("XML", "xml", None, ("<!--", "-->")),
    ".svg": Language("XML", "xml", None, ("<!--", "-->")),
    ".css": Language("CSS", "css", None, ("/*", "*/")),
    ".scss": Language("SCSS", "scss", "//", ("/*", "*/")),
    ".sass": Language("Sass", "sass", "//", ("/*", "*/")),
    ".less": Language("Less", "less", "//", ("/*", "*/")),
    ".yaml": Language("YAML", "yaml", "#"),
    ".yml": Language("YAML", "yaml", "#"),
    ".toml": Language("TOML", "toml", "#"),
    ".ini": Language("INI", "ini", ";"),
    ".cfg": Language("INI", "ini", ";"),
    ".conf": Language("INI", "ini", "#"),
    ".sh": Language("Shell Script", "bash", "#"),
    ".bash": Language("Shell Script", "bash", "#"),
    ".zsh": Language("Shell Script", "bash", "#"),
    ".fish": Language("Fish", "fish", "#"),
    ".rs": Language("Rust", "rust", "//", ("/*", "*/")),
    ".go": Language("Go", "go", "//", ("/*", "*/")),
    ".c": Language("C", "c", "//", ("/*", "*/")),
    ".h": Language("C", "c", "//", ("/*", "*/")),
    ".cc": Language("C++", "cpp", "//", ("/*", "*/")),
    ".cpp": Language("C++", "cpp", "//", ("/*", "*/")),
    ".cxx": Language("C++", "cpp", "//", ("/*", "*/")),
    ".hpp": Language("C++", "cpp", "//", ("/*", "*/")),
    ".hxx": Language("C++", "cpp", "//", ("/*", "*/")),
    ".java": Language("Java", "java", "//", ("/*", "*/")),
    ".kt": Language("Kotlin", "kotlin", "//", ("/*", "*/")),
    ".kts": Language("Kotlin", "kotlin", "//", ("/*", "*/")),
    ".swift": Language("Swift", "swift", "//", ("/*", "*/")),
    ".php": Language("PHP", "php", "//", ("/*", "*/")),
    ".rb": Language("Ruby", "ruby", "#", ("=begin", "=end")),
    ".lua": Language("Lua", "lua", "--", ("--[[", "]]")),
    ".pl": Language("Perl", "perl", "#"),
    ".r": Language("R", "r", "#"),
    ".sql": Language("SQL", "sql", "--", ("/*", "*/")),
    ".dockerfile": Language("Dockerfile", "docker", "#"),
    ".makefile": Language("Makefile", "make", "#"),
    ".mk": Language("Makefile", "make", "#"),
    ".cmake": Language("CMake", "cmake", "#"),
    ".vim": Language("Vimscript", "vim", '"'),
    ".el": Language("Emacs Lisp", "elisp", ";"),
    ".lisp": Language("Common Lisp", "common-lisp", ";"),
    ".clj": Language("Clojure", "clojure", ";"),
    ".ex": Language("Elixir", "elixir", "#"),
    ".exs": Language("Elixir", "elixir", "#"),
    ".erl": Language("Erlang", "erlang", "%"),
    ".hs": Language("Haskell", "haskell", "--"),
    ".ml": Language("OCaml", "ocaml", None, ("(*", "*)")),
    ".zig": Language("Zig", "zig", "//"),
    ".nim": Language("Nim", "nim", "#"),
    ".dart": Language("Dart", "dart", "//", ("/*", "*/")),
    ".tex": Language("LaTeX", "tex", "%"),
    ".diff": Language("Diff", "diff"),
    ".patch": Language("Diff", "diff"),
    ".log": Language("Log", None),
    ".txt": PLAIN_TEXT,
}

# Exact file names (case-insensitive) that don't rely on an extension.
_BY_NAME: dict[str, Language] = {
    "dockerfile": Language("Dockerfile", "docker", "#"),
    "containerfile": Language("Dockerfile", "docker", "#"),
    "makefile": Language("Makefile", "make", "#"),
    "gnumakefile": Language("Makefile", "make", "#"),
    "cmakelists.txt": Language("CMake", "cmake", "#"),
    "justfile": Language("Makefile", "make", "#"),
    ".gitignore": Language("Ignore List", None, "#"),
    ".gitattributes": Language("Ignore List", None, "#"),
    ".dockerignore": Language("Ignore List", None, "#"),
    ".env": Language("Dotenv", "properties", "#"),
    ".editorconfig": Language("INI", "ini", ";"),
    ".bashrc": Language("Shell Script", "bash", "#"),
    ".zshrc": Language("Shell Script", "bash", "#"),
    ".profile": Language("Shell Script", "bash", "#"),
    "requirements.txt": Language("Plain Text", None, "#"),
    "cargo.toml": Language("TOML", "toml", "#"),
    "pyproject.toml": Language("TOML", "toml", "#"),
    "package.json": Language("JSON", "json"),
    "tsconfig.json": Language("JSON with Comments", "json", "//", ("/*", "*/")),
}


def language_for_path(path: str | Path | None) -> Language:
    if path is None:
        return PLAIN_TEXT
    p = Path(path)
    lowered = p.name.lower()
    if lowered in _BY_NAME:
        return _BY_NAME[lowered]
    return _BY_SUFFIX.get(p.suffix.lower(), PLAIN_TEXT)


@lru_cache(maxsize=64)
def pygments_lexer_class(language: Language) -> type | None:
    """Return the Pygments lexer *class* for ``language`` or ``None``.

    Highlighting is strictly best-effort: a missing Pygments install, an
    unknown alias or a broken lexer must never break editing. The class (and
    not an instance) is returned so that every editor pane gets its own
    stateful ``PygmentsLexer`` wrapper.
    """
    if language.lexer is None:
        return None
    try:
        from pygments.lexers import get_lexer_by_name

        return type(get_lexer_by_name(language.lexer))
    except Exception:  # pragma: no cover - depends on optional lexers
        return None


def lexer_for(language: Language, sync_from_start: bool = False) -> Lexer | None:
    """Build a fresh prompt_toolkit lexer for ``language``."""
    cls = pygments_lexer_class(language)
    if cls is None:
        return None
    try:
        from prompt_toolkit.lexers import PygmentsLexer

        return PygmentsLexer(cls, sync_from_start=sync_from_start)
    except Exception:  # pragma: no cover
        return None

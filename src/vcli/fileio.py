"""Reading and writing text files without losing encodings or line endings."""

from __future__ import annotations

import locale
import os
from dataclasses import dataclass, field
from pathlib import Path

MAX_FILE_BYTES = 16 * 1024 * 1024
BINARY_SNIFF_BYTES = 8192


class BinaryFileError(Exception):
    """Raised when a file looks like binary data."""


class FileTooLargeError(Exception):
    """Raised for files above :data:`MAX_FILE_BYTES`."""


@dataclass
class LoadedFile:
    path: Path
    text: str
    encoding: str = "utf-8"
    newline: str = "\n"
    mtime: float = 0.0
    size: int = 0
    warnings: list[str] = field(default_factory=list)


def _preferred_encoding() -> str:
    try:
        return locale.getpreferredencoding(False) or "utf-8"
    except Exception:  # pragma: no cover
        return "utf-8"


def decode_bytes(data: bytes) -> tuple[str, str, list[str]]:
    """Decode ``data`` and return ``(text, encoding, warnings)``.

    ``utf-8-sig`` is only reported when the file actually starts with a BOM,
    so that saving an ordinary UTF-8 file never adds one.
    """
    warnings: list[str] = []
    if data.startswith(b"\xef\xbb\xbf"):
        try:
            return data.decode("utf-8-sig"), "utf-8-sig", warnings
        except UnicodeDecodeError:
            pass
    try:
        return data.decode("utf-8"), "utf-8", warnings
    except UnicodeDecodeError:
        pass
    fallback = _preferred_encoding()
    if fallback.lower().replace("-", "") not in {"utf8", "utf8sig"}:
        try:
            text = data.decode(fallback)
            warnings.append(f"Opened with fallback encoding {fallback}.")
            return text, fallback, warnings
        except (UnicodeDecodeError, LookupError):
            pass
    text = data.decode("latin-1")
    warnings.append("File is not valid UTF-8; opened as latin-1.")
    return text, "latin-1", warnings


def detect_newline(text: str) -> tuple[str, str, list[str]]:
    """Normalize newlines to ``\\n`` and report the dominant ending."""
    warnings: list[str] = []
    crlf = text.count("\r\n")
    cr = text.count("\r") - crlf
    lf = text.count("\n") - crlf
    newline = "\r\n" if crlf > 0 else ("\r" if cr > 0 else "\n")
    if (crlf and lf) or cr:
        warnings.append("Mixed line endings normalized while editing.")
    normalized = text.replace("\r\n", "\n").replace("\r", "\n")
    return normalized, newline, warnings


def read_file(path: str | Path) -> LoadedFile:
    """Load a UTF-8-ish text file, normalizing newlines to ``\\n``."""
    p = Path(path)
    stat = p.stat()
    if stat.st_size > MAX_FILE_BYTES:
        raise FileTooLargeError(
            f"{p.name} is {stat.st_size / 1048576:.1f} MB "
            f"(limit {MAX_FILE_BYTES // 1048576} MB)"
        )
    data = p.read_bytes()
    if b"\x00" in data[:BINARY_SNIFF_BYTES]:
        raise BinaryFileError(f"{p.name} looks like a binary file")
    text, encoding, warnings = decode_bytes(data)
    text, newline, eol_warnings = detect_newline(text)
    return LoadedFile(
        path=p,
        text=text,
        encoding=encoding,
        newline=newline,
        mtime=stat.st_mtime,
        size=stat.st_size,
        warnings=warnings + eol_warnings,
    )


def write_file(
    path: str | Path,
    text: str,
    encoding: str = "utf-8",
    newline: str = "\n",
    make_dirs: bool = False,
) -> None:
    """Write ``text`` converting ``\\n`` to ``newline``."""
    p = Path(path)
    if make_dirs:
        p.parent.mkdir(parents=True, exist_ok=True)
    payload = text if newline == "\n" else text.replace("\n", newline)
    try:
        data = payload.encode(encoding)
    except (LookupError, UnicodeEncodeError):
        data = payload.encode("utf-8")
        encoding = "utf-8"
    # Write through a temporary file so an interrupted save cannot truncate
    # the original document.
    tmp = p.with_name(f".{p.name}.vcli-{os.getpid()}.tmp")
    try:
        tmp.write_bytes(data)
        if p.exists():
            try:
                os.chmod(tmp, p.stat().st_mode)
            except OSError:
                pass
        tmp.replace(p)
    finally:
        try:
            tmp.unlink()
        except OSError:
            pass


def is_probably_binary(path: str | Path) -> bool:
    try:
        with open(path, "rb") as fh:
            return b"\x00" in fh.read(BINARY_SNIFF_BYTES)
    except OSError:
        return False

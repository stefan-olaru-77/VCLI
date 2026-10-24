"""Tests for encoding/EOL-safe reading and atomic writing."""

from __future__ import annotations

from pathlib import Path

import pytest

from vcli.fileio import (
    BinaryFileError,
    decode_bytes,
    detect_newline,
    is_probably_binary,
    read_file,
    write_file,
)


def test_decode_utf8_and_bom():
    text, encoding, warnings = decode_bytes("héllo".encode())
    assert (text, encoding, warnings) == ("héllo", "utf-8", [])

    text, encoding, _ = decode_bytes(b"\xef\xbb\xbfhello")
    assert text == "hello"
    assert encoding == "utf-8-sig"


def test_decode_invalid_utf8_falls_back():
    text, encoding, warnings = decode_bytes(b"caf\xe9")
    assert text == "café"
    assert encoding in {"latin-1", "utf-8"}
    assert warnings


def test_detect_newline():
    assert detect_newline("a\r\nb\r\n")[1] == "\r\n"
    assert detect_newline("a\rb\r")[1] == "\r"
    assert detect_newline("a\nb\n")[1] == "\n"
    normalized, _, warnings = detect_newline("a\r\nb\nc\r")
    assert normalized == "a\nb\nc\n"
    assert warnings


def test_read_write_roundtrip_preserves_crlf(tmp_path: Path):
    path = tmp_path / "crlf.txt"
    path.write_bytes(b"one\r\ntwo\r\n")
    loaded = read_file(path)
    assert loaded.text == "one\ntwo\n"
    assert loaded.newline == "\r\n"
    assert loaded.encoding == "utf-8"

    write_file(path, loaded.text + "three\n", newline=loaded.newline)
    assert path.read_bytes() == b"one\r\ntwo\r\nthree\r\n"


def test_write_file_creates_directories(tmp_path: Path):
    target = tmp_path / "a" / "b" / "file.txt"
    write_file(target, "hello\n", make_dirs=True)
    assert target.read_text(encoding="utf-8") == "hello\n"


def test_write_file_keeps_mode(tmp_path: Path):
    target = tmp_path / "script.sh"
    target.write_text("old\n")
    target.chmod(0o755)
    write_file(target, "new\n")
    assert target.stat().st_mode & 0o777 == 0o755


def test_binary_detection(tmp_path: Path):
    binary = tmp_path / "bin"
    binary.write_bytes(b"abc\x00def")
    with pytest.raises(BinaryFileError):
        read_file(binary)
    assert is_probably_binary(binary) is True
    assert is_probably_binary(tmp_path / "missing") is False


def test_file_too_large(tmp_path: Path, monkeypatch):
    path = tmp_path / "big.txt"
    path.write_text("x")
    monkeypatch.setattr("vcli.fileio.MAX_FILE_BYTES", 0)
    from vcli.fileio import FileTooLargeError

    with pytest.raises(FileTooLargeError):
        read_file(path)

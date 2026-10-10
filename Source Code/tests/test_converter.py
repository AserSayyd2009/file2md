"""Tests for app.converter."""

from __future__ import annotations

from pathlib import Path

import pytest

from app.converter import ConversionError, Converter


@pytest.fixture
def converter() -> Converter:
    return Converter()


class TestConversion:
    def test_converts_txt_file(self, converter: Converter, tmp_path: Path) -> None:
        src = tmp_path / "hello.txt"
        src.write_text("# Hello\n\nworld\n", encoding="utf-8")
        result = converter.convert_file(src)
        assert "Hello" in result.markdown
        assert result.markdown.endswith("\n")

    def test_converts_json_file(self, converter: Converter, tmp_path: Path) -> None:
        src = tmp_path / "data.json"
        src.write_text('{"name": "File2MD", "n": 1}', encoding="utf-8")
        result = converter.convert_file(src)
        assert "File2MD" in result.markdown

    def test_converts_csv_file(self, converter: Converter, tmp_path: Path) -> None:
        src = tmp_path / "table.csv"
        src.write_text("name,age\nAlice,30\nBob,25\n", encoding="utf-8")
        result = converter.convert_file(src)
        assert "Alice" in result.markdown
        assert "Bob" in result.markdown

    def test_preserves_unicode(self, converter: Converter, tmp_path: Path) -> None:
        src = tmp_path / "unicode.txt"
        src.write_text("مرحبا 世界 привет café\n", encoding="utf-8")
        result = converter.convert_file(src)
        assert "مرحبا" in result.markdown
        assert "世界" in result.markdown
        assert "привет" in result.markdown
        assert "café" in result.markdown


class TestErrorHandling:
    def test_missing_file_raises_friendly_error(self, converter: Converter, tmp_path: Path) -> None:
        with pytest.raises(ConversionError) as exc_info:
            converter.convert_file(tmp_path / "nonexistent.pdf")
        assert "does not exist" in str(exc_info.value)

    def test_empty_file_raises_friendly_error(self, converter: Converter, tmp_path: Path) -> None:
        src = tmp_path / "empty.txt"
        src.write_text("", encoding="utf-8")
        with pytest.raises(ConversionError) as exc_info:
            converter.convert_file(src)
        assert "empty" in str(exc_info.value).lower()

    def test_directory_raises_friendly_error(self, converter: Converter, tmp_path: Path) -> None:
        with pytest.raises(ConversionError) as exc_info:
            converter.convert_file(tmp_path)
        assert "not a file" in str(exc_info.value).lower()

    def test_unsupported_format_raises(self, converter: Converter, tmp_path: Path) -> None:
        # A binary file with a .xyz extension MarkItDown does not recognize.
        # MarkItDown may fall back to PlainTextConverter via content detection,
        # so we use a tiny binary file that should not be parsed as text.
        src = tmp_path / "data.xyz"
        src.write_bytes(b"\x00\x01\x02\x03binary\xff\xfe")
        # Either it fails (unsupported) or it succeeds with empty/garbage.
        # If it succeeds, the output is not our concern here; the contract
        # is that the converter never crashes the process.
        try:
            result = converter.convert_file(src)
            assert isinstance(result.markdown, str)
        except ConversionError:
            pass  # acceptable outcome

    def test_corrupted_pdf_does_not_crash(self, converter: Converter, tmp_path: Path) -> None:
        # A file that looks like a PDF but is not parseable. MarkItDown's
        # PlainTextConverter may still extract the text "not a real pdf" —
        # that is acceptable. The contract we test here is: the converter
        # never raises an unhandled exception (it either succeeds with a
        # string or raises a friendly ConversionError).
        src = tmp_path / "broken.pdf"
        src.write_bytes(b"%PDF-1.4\nnot a real pdf\n%%EOF")
        try:
            result = converter.convert_file(src)
            assert isinstance(result.markdown, str)
        except ConversionError:
            pass  # acceptable outcome

    def test_error_message_does_not_leak_traceback(self, converter: Converter, tmp_path: Path) -> None:
        with pytest.raises(ConversionError) as exc_info:
            converter.convert_file(tmp_path / "nope.pdf")
        msg = str(exc_info.value)
        assert "Traceback" not in msg

"""Tests for app.utils."""

from __future__ import annotations

from pathlib import Path

import pytest

from app.utils import (
    change_extension,
    cleanup_markdown,
    generate_unique_output_path,
    humanize_size,
    sanitize_filename,
    truncate_middle,
    write_text_file,
)


class TestSanitizeFilename:
    def test_strips_invalid_windows_chars(self) -> None:
        assert sanitize_filename("a<b>c:d?e*f|g") == "a_b_c_d_e_f_g"

    def test_replaces_control_chars(self) -> None:
        assert sanitize_filename("hello\x00world") == "hello_world"

    def test_strips_leading_trailing_dots_and_spaces(self) -> None:
        assert sanitize_filename("..hidden..") == "hidden"
        assert sanitize_filename("  spaced  ") == "spaced"

    def test_returns_untitled_for_empty(self) -> None:
        assert sanitize_filename("") == "untitled"
        assert sanitize_filename("...") == "untitled"

    def test_preserves_unicode(self) -> None:
        assert sanitize_filename("بحث") == "بحث"
        assert sanitize_filename("研究论文") == "研究论文"

    def test_truncates_oversized(self) -> None:
        long_name = "x" * 500
        result = sanitize_filename(long_name)
        assert len(result) <= 200


class TestChangeExtension:
    def test_changes_extension(self, tmp_path: Path) -> None:
        assert change_extension(Path("a/b.pdf"), ".md") == Path("a/b.md")
        assert change_extension(Path("a/b.pdf"), "md") == Path("a/b.md")
        assert change_extension(Path("noext"), ".md") == Path("noext.md")


class TestGenerateUniqueOutputPath:
    def test_no_conflict_returns_target(self, tmp_path: Path) -> None:
        target = tmp_path / "report.md"
        assert generate_unique_output_path(target) == target

    def test_create_unique_appends_counter(self, tmp_path: Path) -> None:
        (tmp_path / "report.md").write_text("x", encoding="utf-8")
        result = generate_unique_output_path(tmp_path / "report.md")
        assert result == tmp_path / "report (1).md"

    def test_create_unique_increments_counter(self, tmp_path: Path) -> None:
        (tmp_path / "report.md").write_text("x", encoding="utf-8")
        (tmp_path / "report (1).md").write_text("x", encoding="utf-8")
        result = generate_unique_output_path(tmp_path / "report.md")
        assert result == tmp_path / "report (2).md"

    def test_overwrite_returns_target(self, tmp_path: Path) -> None:
        target = tmp_path / "report.md"
        target.write_text("old", encoding="utf-8")
        assert generate_unique_output_path(target, overwrite=True) == target

    def test_skip_returns_none_when_no_unique(self, tmp_path: Path) -> None:
        target = tmp_path / "report.md"
        target.write_text("old", encoding="utf-8")
        assert generate_unique_output_path(target, create_unique=False) is None


class TestCleanupMarkdown:
    def test_normalizes_line_endings(self) -> None:
        assert cleanup_markdown("a\r\nb\rc") == "a\nb\nc\n"

    def test_strips_trailing_whitespace(self) -> None:
        assert cleanup_markdown("hello   \nworld\t\n") == "hello\nworld\n"

    def test_collapses_excessive_blank_lines(self) -> None:
        text = "para1\n\n\n\n\npara2"
        assert cleanup_markdown(text) == "para1\n\npara2\n"

    def test_preserves_tables(self) -> None:
        md = "| A | B |\n|---|---|\n| 1 | 2 |\n"
        assert cleanup_markdown(md) == "| A | B |\n|---|---|\n| 1 | 2 |\n"

    def test_preserves_code_blocks(self) -> None:
        md = "```\nline1\n\nline2\n```\n"
        assert cleanup_markdown(md) == "```\nline1\n\nline2\n```\n"

    def test_ends_with_single_newline(self) -> None:
        assert cleanup_markdown("hello\n\n\n") == "hello\n"
        assert cleanup_markdown("hello").endswith("\n")

    def test_empty_input(self) -> None:
        assert cleanup_markdown("") == ""


class TestWriteTextFile:
    def test_writes_utf8_without_bom(self, tmp_path: Path) -> None:
        target = tmp_path / "out.md"
        write_text_file(target, "# مرحبا 世界\n")
        raw = target.read_bytes()
        assert not raw.startswith(b"\xef\xbb\xbf")  # no BOM
        assert target.read_text(encoding="utf-8") == "# مرحبا 世界\n"

    def test_creates_parent_dirs(self, tmp_path: Path) -> None:
        target = tmp_path / "nested" / "deeper" / "out.md"
        write_text_file(target, "content")
        assert target.exists()


class TestHumanizeSize:
    def test_bytes(self) -> None:
        assert humanize_size(512) == "512 B"

    def test_kilobytes(self) -> None:
        assert humanize_size(2048) == "2.0 KB"

    def test_megabytes(self) -> None:
        assert humanize_size(5 * 1024 * 1024) == "5.0 MB"

    def test_negative(self) -> None:
        assert humanize_size(-5) == "0 B"


class TestTruncateMiddle:
    def test_short_unchanged(self) -> None:
        assert truncate_middle("short", 60) == "short"

    def test_long_truncated(self) -> None:
        text = "a" * 100
        result = truncate_middle(text, 20)
        assert len(result) <= 20
        assert result.startswith("a")
        assert result.endswith("a")

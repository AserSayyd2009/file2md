"""Tests for app.file_manager."""

from __future__ import annotations

from pathlib import Path

import pytest

from app.file_manager import (
    compute_output_path,
    discover_files,
    discover_supported_extensions,
    filter_supported,
    is_supported_file,
)


class TestSupportedExtensions:
    def test_returns_nonempty_set(self) -> None:
        exts = discover_supported_extensions()
        assert isinstance(exts, frozenset)
        assert len(exts) > 5

    def test_includes_common_formats(self) -> None:
        exts = discover_supported_extensions()
        for expected in (".pdf", ".docx", ".pptx", ".xlsx", ".csv", ".html", ".txt", ".json"):
            assert expected in exts, f"{expected} should be supported"

    def test_cached(self) -> None:
        a = discover_supported_extensions()
        b = discover_supported_extensions()
        assert a is b


class TestIsSupportedFile:
    def test_supported_extension(self, tmp_path: Path) -> None:
        p = tmp_path / "x.pdf"
        p.write_text("dummy", encoding="utf-8")
        assert is_supported_file(p) is True

    def test_unsupported_extension(self, tmp_path: Path) -> None:
        p = tmp_path / "x.xyz"
        p.write_text("dummy", encoding="utf-8")
        assert is_supported_file(p) is False

    def test_md_files_not_supported(self, tmp_path: Path) -> None:
        # The output format itself must not be re-queued.
        p = tmp_path / "x.md"
        p.write_text("# hi", encoding="utf-8")
        assert is_supported_file(p) is False

    def test_case_insensitive(self, tmp_path: Path) -> None:
        p = tmp_path / "X.PDF"
        p.write_text("dummy", encoding="utf-8")
        assert is_supported_file(p) is True


class TestFilterSupported:
    def test_filters_unsupported(self, tmp_path: Path) -> None:
        a = tmp_path / "a.pdf"
        b = tmp_path / "b.unknown"
        c = tmp_path / "c.docx"
        for p in (a, b, c):
            p.write_text("dummy", encoding="utf-8")
        result = filter_supported([a, b, c])
        assert a in result
        assert c in result
        assert b not in result

    def test_deduplicates(self, tmp_path: Path) -> None:
        a = tmp_path / "a.pdf"
        a.write_text("dummy", encoding="utf-8")
        result = filter_supported([a, a, a])
        assert len(result) == 1


class TestDiscoverFiles:
    def test_discovers_flat(self, tmp_path: Path) -> None:
        (tmp_path / "a.pdf").write_text("x", encoding="utf-8")
        (tmp_path / "b.txt").write_text("x", encoding="utf-8")
        (tmp_path / "c.unsupported").write_text("x", encoding="utf-8")
        result = discover_files(tmp_path, recursive=False)
        names = sorted(p.name for p in result)
        assert names == ["a.pdf", "b.txt"]

    def test_recursive_walks_subdirs(self, tmp_path: Path) -> None:
        sub = tmp_path / "sub"
        sub.mkdir()
        (tmp_path / "top.pdf").write_text("x", encoding="utf-8")
        (sub / "deep.docx").write_text("x", encoding="utf-8")
        result = discover_files(tmp_path, recursive=True)
        names = sorted(p.name for p in result)
        assert names == ["deep.docx", "top.pdf"]

    def test_non_recursive_stays_flat(self, tmp_path: Path) -> None:
        sub = tmp_path / "sub"
        sub.mkdir()
        (tmp_path / "top.pdf").write_text("x", encoding="utf-8")
        (sub / "deep.pdf").write_text("x", encoding="utf-8")
        result = discover_files(tmp_path, recursive=False)
        assert [p.name for p in result] == ["top.pdf"]

    def test_skips_generated_md(self, tmp_path: Path) -> None:
        # Re-scanning an output directory should not re-queue generated .md
        (tmp_path / "out.md").write_text("# hi", encoding="utf-8")
        (tmp_path / "real.pdf").write_text("x", encoding="utf-8")
        result = discover_files(tmp_path, recursive=False)
        assert [p.name for p in result] == ["real.pdf"]


class TestComputeOutputPath:
    def test_basic_renames_extension(self, tmp_path: Path) -> None:
        src = tmp_path / "report.pdf"
        src.write_text("x", encoding="utf-8")
        out_dir = tmp_path / "out"
        result = compute_output_path(src, out_dir)
        assert result == out_dir / "report.md"

    def test_preserve_structure_mirrors_subdirs(self, tmp_path: Path) -> None:
        root = tmp_path / "root"
        sub = root / "Reports"
        sub.mkdir(parents=True)
        src = sub / "r1.pdf"
        src.write_text("x", encoding="utf-8")
        out_dir = tmp_path / "out"
        result = compute_output_path(src, out_dir, preserve_structure=True, input_root=root)
        assert result == out_dir / "Reports" / "r1.md"

    def test_unique_filename_on_conflict(self, tmp_path: Path) -> None:
        src = tmp_path / "report.pdf"
        src.write_text("x", encoding="utf-8")
        out_dir = tmp_path / "out"
        out_dir.mkdir()
        (out_dir / "report.md").write_text("old", encoding="utf-8")
        result = compute_output_path(src, out_dir, create_unique=True)
        assert result == out_dir / "report (1).md"

    def test_overwrite_returns_existing_path(self, tmp_path: Path) -> None:
        src = tmp_path / "report.pdf"
        src.write_text("x", encoding="utf-8")
        out_dir = tmp_path / "out"
        out_dir.mkdir()
        existing = out_dir / "report.md"
        existing.write_text("old", encoding="utf-8")
        result = compute_output_path(src, out_dir, overwrite=True)
        assert result == existing

    def test_returns_none_when_skip_policy(self, tmp_path: Path) -> None:
        src = tmp_path / "report.pdf"
        src.write_text("x", encoding="utf-8")
        out_dir = tmp_path / "out"
        out_dir.mkdir()
        (out_dir / "report.md").write_text("old", encoding="utf-8")
        result = compute_output_path(
            src, out_dir, overwrite=False, create_unique=False
        )
        assert result is None

    def test_sanitizes_unsafe_input_name(self, tmp_path: Path) -> None:
        # Filenames with colons etc. must not produce invalid output paths.
        src = tmp_path / "weird:name.pdf"
        src.write_text("x", encoding="utf-8")
        out_dir = tmp_path / "out"
        result = compute_output_path(src, out_dir)
        assert ":" not in result.name
        assert result.suffix == ".md"

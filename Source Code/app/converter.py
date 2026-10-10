"""
Conversion engine: a thin, robust wrapper around Microsoft MarkItDown.

Responsibilities:
  - Lazily construct a single :class:`MarkItDown` instance.
  - Convert one file to a Markdown string.
  - Translate MarkItDown's exception types into readable, user-facing
    :class:`ConversionError` messages.
  - Never log document content.
"""

from __future__ import annotations

import io
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from .logger import get_logger
from .utils import cleanup_markdown


log = get_logger("converter")


class ConversionError(Exception):
    """Raised when a document cannot be converted. Message is user-safe."""

    def __init__(self, message: str, *, reason_kind: str = "error") -> None:
        super().__init__(message)
        self.reason_kind = reason_kind


@dataclass
class ConversionResult:
    """Outcome of converting a single file."""

    input_path: Path
    markdown: str
    warnings: list[str]


class Converter:
    """Wraps :class:`markitdown.MarkItDown` for safe one-file conversion."""

    def __init__(self) -> None:
        self._md = None

    # ------------------------------------------------------------------ #
    # Lazy initialization
    # ------------------------------------------------------------------ #
    def _engine(self):
        if self._md is None:
            try:
                from markitdown import MarkItDown  # local import keeps startup fast
            except ImportError as exc:
                raise ConversionError(
                    "Microsoft MarkItDown is not installed. "
                    "Run: pip install markitdown",
                    reason_kind="missing_dependency",
                ) from exc
            self._md = MarkItDown()
        return self._md

    # ------------------------------------------------------------------ #
    # Public API
    # ------------------------------------------------------------------ #
    def convert_file(self, path: Path) -> ConversionResult:
        """Convert ``path`` to Markdown.

        Raises :class:`ConversionError` with a human-readable message on
        any failure. Never returns partial/garbage output.
        """
        path = Path(path)
        if not path.exists():
            raise ConversionError(
                f"The file does not exist: {path}", reason_kind="missing_file"
            )
        if not path.is_file():
            raise ConversionError(
                f"The path is not a file: {path}", reason_kind="not_a_file"
            )
        if path.stat().st_size == 0:
            raise ConversionError(
                f"The file is empty: {path.name}", reason_kind="empty_file"
            )

        log.info("Converting: %s", path)
        warnings: list[str] = []

        try:
            engine = self._engine()
        except ConversionError:
            raise
        except Exception as exc:
            log.exception("Failed to initialize MarkItDown engine")
            raise ConversionError(
                f"Could not start the conversion engine: {exc}"
            ) from exc

        try:
            result = engine.convert(str(path))
        except Exception as exc:
            raise self._translate_exception(exc, path) from exc

        markdown = getattr(result, "text_content", None)
        if markdown is None:
            markdown = ""
        if not isinstance(markdown, str):
            try:
                markdown = str(markdown)
            except Exception:
                markdown = ""

        if not markdown.strip():
            raise ConversionError(
                f"No readable text could be extracted from: {path.name}",
                reason_kind="empty_content",
            )

        markdown = cleanup_markdown(markdown)

        log.info("Converted: %s (%d chars)", path, len(markdown))
        return ConversionResult(
            input_path=path, markdown=markdown, warnings=warnings
        )

    # ------------------------------------------------------------------ #
    # Internal helpers
    # ------------------------------------------------------------------ #
    def _translate_exception(self, exc: Exception, path: Path) -> ConversionError:
        """Map MarkItDown / Python exceptions to user-friendly messages."""
        # Try to detect MarkItDown's specific exception types without importing
        # them eagerly (they may not exist in older versions).
        exc_module = type(exc).__module__ or ""
        exc_name = type(exc).__name__

        if exc_name == "MissingDependencyException":
            msg = str(exc)
            # MarkItDown includes the feature/extension; surface a friendly hint.
            return ConversionError(
                f"{path.name} requires an optional dependency that is not installed.\n\n{msg}",
                reason_kind="missing_dependency",
            )
        if exc_name == "UnsupportedFormatException":
            return ConversionError(
                f"{path.name} is not a supported format.",
                reason_kind="unsupported",
            )
        if exc_name == "FileConversionException":
            return ConversionError(
                f"{path.name} could not be converted. The file may be corrupted or password-protected.",
                reason_kind="conversion_failed",
            )

        # Password-protected PDFs usually surface as pdfplumber errors
        if "password" in str(exc).lower() or "encrypted" in str(exc).lower():
            return ConversionError(
                f"{path.name} appears to be password-protected. Remove the password and try again.",
                reason_kind="password_protected",
            )

        # Permission / locked file errors
        if isinstance(exc, PermissionError):
            return ConversionError(
                f"Permission denied when reading: {path.name}. The file may be open in another program.",
                reason_kind="permission",
            )
        if isinstance(exc, OSError):
            return ConversionError(
                f"Could not read the file: {path.name}. Reason: {exc}",
                reason_kind="io_error",
            )

        # Fall back to the exception's own message but never expose a full
        # Python traceback in the user-facing UI.
        log.warning("Unhandled conversion exception for %s: %s", path, exc)
        return ConversionError(
            f"Failed to convert {path.name}.\n\nReason: {exc}",
            reason_kind="error",
        )


# Module-level singleton used by the CLI. The GUI keeps its own instance
# because it constructs the engine lazily on the worker thread.
_default_converter: Optional[Converter] = None


def get_default_converter() -> Converter:
    global _default_converter
    if _default_converter is None:
        _default_converter = Converter()
    return _default_converter

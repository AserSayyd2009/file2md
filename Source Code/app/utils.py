"""
Utility functions: filename safety, Markdown cleanup, encoding helpers.

These helpers are deliberately conservative — they never rewrite Markdown
structure, only normalize whitespace and encoding.
"""

from __future__ import annotations

import re
from pathlib import Path


# Characters that Windows forbids in filenames, plus control characters.
_WINDOWS_INVALID_CHARS = '<>:"/\\|?*\0'
_INVALID_CHAR_PATTERN = re.compile(
    f"[{re.escape(_WINDOWS_INVALID_CHARS)}\\x00-\\x1f]"
)

# Multiple consecutive blank lines collapsed to at most two.
_MULTIPLE_BLANK_LINES = re.compile(r"\n{3,}")
# Trailing whitespace on each line. MULTILINE so $ matches end-of-line, not
# just end-of-string.
_TRAILING_WS = re.compile(r"[ \t]+$", re.MULTILINE)
# Stray carriage returns (normalize to \n).
_CR = re.compile(r"\r\n?")

# A safe replacement character for invalid filename chars.
_SAFE_REPLACEMENT = "_"


def sanitize_filename(name: str) -> str:
    """Return a filename safe for Windows / macOS / Linux.

    Replaces invalid characters with ``_`` and trims leading/trailing
    spaces and dots (which Windows does not allow).
    """
    cleaned = _INVALID_CHAR_PATTERN.sub(_SAFE_REPLACEMENT, name)
    # Windows does not allow leading/trailing spaces or dots in filenames.
    cleaned = cleaned.strip(" .")
    if not cleaned:
        cleaned = "untitled"
    # Windows limits path components to 255 chars; keep a margin for the
    # extension and uniqueness suffix.
    if len(cleaned) > 200:
        cleaned = cleaned[:200]
    return cleaned


def change_extension(path: Path, new_extension: str) -> Path:
    """Return ``path`` with its suffix replaced by ``new_extension``.

    ``new_extension`` may or may not start with a dot.
    """
    ext = new_extension if new_extension.startswith(".") else f".{new_extension}"
    return path.with_suffix(ext)


def generate_unique_output_path(
    target_path: Path,
    *,
    overwrite: bool = False,
    create_unique: bool = True,
) -> Path | None:
    """Resolve a target output path according to the overwrite policy.

    Returns:
        - The same ``target_path`` if no conflict exists or ``overwrite`` is True.
        - A uniquely numbered path (e.g. ``report (1).md``) if ``create_unique``
          is True and the target already exists.
        - ``None`` if the file already exists, ``overwrite`` is False, and
          ``create_unique`` is False (i.e. the caller should skip the file).
    """
    if not target_path.exists() or overwrite:
        return target_path
    if not create_unique:
        return None

    stem = target_path.stem
    suffix = target_path.suffix
    parent = target_path.parent
    counter = 1
    while True:
        candidate = parent / f"{stem} ({counter}){suffix}"
        if not candidate.exists():
            return candidate
        counter += 1
        # Guard against runaway loops (extremely unlikely in practice).
        if counter > 9999:
            return None


def normalize_line_endings(text: str) -> str:
    """Normalize ``\\r\\n`` and lone ``\\r`` to ``\\n``."""
    return _CR.sub("\n", text)


def cleanup_markdown(text: str) -> str:
    """Apply safe post-processing to MarkItDown output.

    Operations performed (all structurally safe — they do NOT touch tables,
    code blocks, lists, links, or headings):

    1. Normalize line endings to ``\\n``.
    2. Strip trailing whitespace from each line.
    3. Collapse 3+ consecutive blank lines to exactly 2.
    4. Ensure the document ends with exactly one trailing newline.

    The original MarkItDown output remains the primary source — this only
    tidies whitespace.
    """
    if not text:
        return ""
    out = normalize_line_endings(text)
    out = _TRAILING_WS.sub("", out)
    out = _MULTIPLE_BLANK_LINES.sub("\n\n", out)
    out = out.rstrip("\n") + "\n"
    return out


def write_text_file(path: Path, text: str) -> None:
    """Write ``text`` to ``path`` as UTF-8 without BOM."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="\n")


def humanize_size(num_bytes: int) -> str:
    """Return a human-readable file size string."""
    if num_bytes < 0:
        return "0 B"
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if abs(num_bytes) < 1024.0:
            if unit == "B":
                return f"{num_bytes} {unit}"
            return f"{num_bytes:.1f} {unit}"
        num_bytes = round(num_bytes / 1024)
    return f"{num_bytes} PB"


def truncate_middle(text: str, max_len: int = 60) -> str:
    """Truncate ``text`` in the middle if it exceeds ``max_len``."""
    if len(text) <= max_len:
        return text
    keep = max_len - 1
    left = keep // 2
    right = keep - left
    return f"{text[:left]}…{text[-right:]}"

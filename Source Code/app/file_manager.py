"""
File discovery and format support detection.

The supported extension set is discovered dynamically from the installed
MarkItDown version (so we never claim to support a format that the
underlying library does not handle). A fallback list is used if the
dynamic discovery fails for any reason.
"""

from __future__ import annotations

import importlib
import pkgutil
from pathlib import Path
from typing import Iterable

from .utils import (
    change_extension,
    generate_unique_output_path,
    sanitize_filename,
)


# Fallback list used only if dynamic discovery fails.
# This matches MarkItDown 0.1.x; the runtime list is the source of truth.
_FALLBACK_SUPPORTED_EXTENSIONS: frozenset[str] = frozenset(
    {
        ".csv", ".docx", ".epub", ".htm", ".html", ".ipynb",
        ".jpeg", ".jpg", ".json", ".jsonl", ".m4a", ".markdown",
        ".md", ".mp3", ".mp4", ".msg", ".pdf", ".png",
        ".pptx", ".text", ".txt", ".xls", ".xlsx", ".zip",
    }
)

_discovered_cache: frozenset[str] | None = None


def discover_supported_extensions() -> frozenset[str]:
    """Return the set of file extensions supported by the installed MarkItDown.

    Walks ``markitdown.converters`` and collects every ``ACCEPTED_*_EXTENSIONS``
    attribute. If discovery fails for any reason, returns the fallback list.
    """
    global _discovered_cache
    if _discovered_cache is not None:
        return _discovered_cache

    exts: set[str] = set()
    try:
        import markitdown.converters as pkg

        for module_info in pkgutil.iter_modules(pkg.__path__):
            if not module_info.name.startswith("_"):
                continue
            try:
                module = importlib.import_module(
                    f"markitdown.converters.{module_info.name}"
                )
            except Exception:
                continue
            for attr_name in dir(module):
                if (
                    attr_name.startswith("ACCEPTED_")
                    and attr_name.endswith("_EXTENSIONS")
                ):
                    value = getattr(module, attr_name)
                    if isinstance(value, (list, tuple, set, frozenset)):
                        exts.update(str(e).lower() for e in value)
    except Exception:
        pass

    _discovered_cache = (
        frozenset(exts) if exts else _FALLBACK_SUPPORTED_EXTENSIONS
    )
    return _discovered_cache


def is_supported_file(path: Path) -> bool:
    """Return True if ``path``'s extension is supported by MarkItDown.

    Also returns False for the ``.md`` output format itself, to avoid
    re-converting generated Markdown files when scanning a folder.
    """
    ext = path.suffix.lower()
    supported = discover_supported_extensions()
    if ext == ".md":
        return False
    return ext in supported


def filter_supported(paths: Iterable[Path]) -> list[Path]:
    """Filter an iterable of paths to only supported, existing files."""
    seen: set[Path] = set()
    result: list[Path] = []
    for p in paths:
        try:
            resolved = p.resolve()
        except OSError:
            resolved = p
        if resolved in seen:
            continue
        if not p.is_file():
            continue
        if not is_supported_file(p):
            continue
        seen.add(resolved)
        result.append(p)
    return result


def discover_files(
    root: Path,
    *,
    recursive: bool = True,
) -> list[Path]:
    """Discover supported files under ``root``.

    When ``recursive`` is True, walks the entire tree; otherwise only lists
    files directly inside ``root``. Skips ``.md`` files (output format)
    so re-scanning an output directory never re-queues its own products.
    """
    if not root.exists() or not root.is_dir():
        return []
    found: list[Path] = []
    if recursive:
        for dirpath, _dirnames, filenames in root.walk():
            for name in filenames:
                p = dirpath / name
                if is_supported_file(p):
                    found.append(p)
    else:
        for entry in root.iterdir():
            if entry.is_file() and is_supported_file(entry):
                found.append(entry)
    return filter_supported(found)


def compute_output_path(
    input_path: Path,
    output_dir: Path,
    *,
    preserve_structure: bool = False,
    input_root: Path | None = None,
    overwrite: bool = False,
    create_unique: bool = True,
) -> Path | None:
    """Compute the output ``.md`` path for ``input_path``.

    Args:
        input_path: The source document.
        output_dir: The base output directory.
        preserve_structure: If True, mirror the subfolder layout under
            ``input_root`` inside ``output_dir``.
        input_root: The folder the user selected as the conversion root.
            Required when ``preserve_structure`` is True.
        overwrite: If True, allow overwriting an existing output file.
        create_unique: If True, generate ``name (1).md`` etc. on conflict.

    Returns:
        The resolved output ``Path``, or ``None`` if the file should be
        skipped because an output already exists and neither overwrite nor
        create_unique is set.
    """
    safe_stem = sanitize_filename(input_path.stem)

    if preserve_structure and input_root is not None:
        try:
            rel = input_path.relative_to(input_root)
            rel_parent = rel.parent
            target_dir = output_dir / rel_parent
        except ValueError:
            target_dir = output_dir
    else:
        target_dir = output_dir

    target_dir.mkdir(parents=True, exist_ok=True)
    base_path = change_extension(target_dir / safe_stem, ".md")
    return generate_unique_output_path(
        base_path,
        overwrite=overwrite,
        create_unique=create_unique,
    )

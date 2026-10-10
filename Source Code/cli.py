"""
File2MD — command-line interface.

Reuses the same conversion engine as the GUI; no logic is duplicated.

Examples::

    file2md report.pdf
    file2md report.pdf -o output/
    file2md documents/ -r -o markdown/
    file2md *.docx --overwrite
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from app.config import APP_NAME, APP_VERSION, Settings
from app.converter import ConversionError, Converter
from app.file_manager import (
    compute_output_path,
    discover_files,
    discover_supported_extensions,
    filter_supported,
    is_supported_file,
)
from app.logger import get_logger, setup_logging
from app.utils import write_text_file


log = get_logger("cli")


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog=APP_NAME.lower(),
        description=(
            f"{APP_NAME} — convert supported documents to Markdown using "
            "Microsoft MarkItDown. Runs entirely locally."
        ),
    )
    parser.add_argument(
        "inputs",
        nargs="+",
        help="Files or folders to convert.",
    )
    parser.add_argument(
        "-o", "--output",
        type=str, default=None,
        help="Output directory (default: <input_dir>/Markdown for files, "
             "or the selected folder's 'Markdown' subdirectory).",
    )
    parser.add_argument(
        "-r", "--recursive",
        action="store_true",
        help="When an input is a folder, discover files recursively.",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Overwrite existing Markdown files in the output directory.",
    )
    parser.add_argument(
        "--no-unique",
        action="store_true",
        help="Do not generate unique filenames (report (1).md) when a "
             "Markdown file already exists. Files that conflict will be skipped.",
    )
    parser.add_argument(
        "--preserve-structure",
        action="store_true",
        help="When converting a folder recursively, mirror the input "
             "folder structure inside the output directory.",
    )
    parser.add_argument(
        "--gui",
        action="store_true",
        help="Force GUI mode (overrides any other CLI behavior). "
             "Only honored when invoked through the main entry point.",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {APP_VERSION}",
    )
    return parser


def _resolve_input_paths(inputs: list[str], recursive: bool) -> list[tuple[Path, Path | None]]:
    """Return (file_path, input_root) tuples for every supported file found.

    ``input_root`` is the folder the user passed in (used for structure
    preservation) or None for direct file inputs.
    """
    results: list[tuple[Path, Path | None]] = []
    for raw in inputs:
        p = Path(raw)
        if not p.exists():
            print(f"  ! Not found: {raw}", file=sys.stderr)
            continue
        if p.is_file():
            if is_supported_file(p):
                results.append((p, None))
            else:
                ext = p.suffix.lower() or "(no extension)"
                supported = discover_supported_extensions()
                if ext in supported:
                    # Should not normally happen — supported but skipped?
                    results.append((p, None))
                else:
                    print(f"  ! Unsupported format ({ext}): {p}", file=sys.stderr)
        elif p.is_dir():
            for f in discover_files(p, recursive=recursive):
                results.append((f, p))
        else:
            print(f"  ! Not a file or folder: {raw}", file=sys.stderr)
    return results


def _resolve_output_dir(
    inputs: list[str], output_arg: str | None, files: list[Path]
) -> Path:
    if output_arg:
        out = Path(output_arg)
    else:
        # Default to a "Markdown" subfolder next to the first input.
        first = files[0] if files else Path(inputs[0])
        if first.is_file():
            out = first.parent / "Markdown"
        else:
            out = first / "Markdown"
    out.mkdir(parents=True, exist_ok=True)
    return out


def run(args: argparse.Namespace) -> int:
    settings = Settings(
        overwrite_existing=args.overwrite,
        create_unique_filenames=not args.no_unique,
        preserve_structure=args.preserve_structure,
        include_subfolders=args.recursive,
    )

    discovered = _resolve_input_paths(args.inputs, recursive=args.recursive)
    if not discovered:
        print("No supported files were found.", file=sys.stderr)
        return 1

    files = [item[0] for item in discovered]
    output_dir = _resolve_output_dir(args.inputs, args.output, files)

    print(f"{APP_NAME} {APP_VERSION}")
    print(f"  Output directory: {output_dir}")
    print(f"  Files to convert: {len(files)}")
    print(f"  Recursive: {args.recursive}")
    print(f"  Preserve structure: {settings.preserve_structure}")
    print(f"  Overwrite: {settings.overwrite_existing}")
    print(f"  Unique filenames: {settings.create_unique_filenames}")
    print()

    converter = Converter()
    converted = failed = skipped = 0
    failures: list[tuple[str, str]] = []

    for i, (path, input_root) in enumerate(discovered, 1):
        prefix = f"[{i}/{len(discovered)}] {path.name}"
        print(prefix, end=" ... ", flush=True)
        try:
            result = converter.convert_file(path)
        except ConversionError as exc:
            failed += 1
            failures.append((path.name, str(exc)))
            print(f"FAILED")
            print(f"        Reason: {exc}", file=sys.stderr)
            log.warning("CLI conversion failed: %s — %s", path, exc)
            continue

        out_path = compute_output_path(
            path,
            output_dir,
            preserve_structure=settings.preserve_structure,
            input_root=input_root,
            overwrite=settings.overwrite_existing,
            create_unique=settings.create_unique_filenames,
        )
        if out_path is None:
            skipped += 1
            print("SKIPPED (output already exists)")
            continue

        try:
            write_text_file(out_path, result.markdown)
        except OSError as exc:
            failed += 1
            failures.append((path.name, str(exc)))
            print(f"FAILED (write error: {exc})")
            continue

        converted += 1
        rel = out_path.relative_to(output_dir) if out_path.is_relative_to(output_dir) else out_path
        print(f"OK  ->  {rel}")

    print()
    print(
        f"Done. Converted: {converted}  Failed: {failed}  Skipped: {skipped}"
    )
    if failures:
        print()
        print("Failed files:")
        for name, reason in failures:
            print(f"  • {name}: {reason}")
    return 0 if failed == 0 else 1


def main() -> int:
    setup_logging()
    parser = _build_parser()
    args = parser.parse_args()
    log.info("%s %s starting (CLI mode)", APP_NAME, APP_VERSION)
    log.info("Arguments: %s", vars(args))
    try:
        return run(args)
    except KeyboardInterrupt:
        print("\nInterrupted by user.", file=sys.stderr)
        return 130


if __name__ == "__main__":
    sys.exit(main())

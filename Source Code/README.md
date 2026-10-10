# File2MD

**A lightweight, local-first Windows desktop application that converts documents to clean Markdown (`.md`) files.**

Powered by [Microsoft MarkItDown](https://github.com/microsoft/markitdown).

File2MD is a small native utility — not a web app, not a cloud service.
Every byte of every document stays on your computer. There is no telemetry,
no analytics, no background service, and no internet access required.

---

## Features

- **Modern flat Tkinter UI** — compact, single-window, drag-and-drop enabled.
- **Batch conversion** — queue dozens or hundreds of files; they are processed
  one at a time so memory stays low.
- **Single worker thread** — the UI never freezes during conversion.
- **Folder discovery** — pick a folder and recursively find every supported
  file in one click. (Optional `Include subfolders` toggle.)
- **Folder-structure preservation** — mirror the input folder layout inside
  the output directory when converting recursively.
- **Smart filename conflicts** — auto-rename `report.md` → `report (1).md` so
  existing files are never silently overwritten (configurable: overwrite /
  skip / auto-rename).
- **Drag and drop** — drop files or folders directly onto the window
  (uses `tkinterdnd2`; falls back to buttons if unavailable).
- **Per-file status** — Ready / Converting / Converted / Failed / Skipped /
  Cancelled, color-coded.
- **Cancellation that is safe** — stop adding new jobs; the currently running
  conversion finishes naturally. The thread is never killed.
- **UTF-8 always** — Arabic, Chinese, Japanese, Cyrillic, mixed-language
  documents all convert correctly. Output files are written without BOM.
- **Friendly errors** — failures never crash the app or stop the queue.
  Tracebacks are logged internally; the UI shows a one-line reason.
- **View Log** button — opens the rotating log file (`file2md.log`) in your
  default editor for troubleshooting.
- **CLI mode** — convert from the command line with the same engine
  (`file2md report.pdf -o output/`).
- **Persistent settings** — output directory, subfolder toggle, structure
  preservation, and overwrite policy are remembered across sessions.
- **Privacy** — fully offline; no cloud, no API calls, no tracking.

---

## Supported formats

File2MD supports **every format that the installed MarkItDown version
supports**. The list is discovered at runtime — there is no hard-coded list
that can drift out of sync with MarkItDown.

The formats supported by MarkItDown 0.1.x are:

| Category | Extensions |
|----------|------------|
| **Documents** | `.pdf`, `.docx`, `.pptx`, `.xlsx`, `.xls`, `.epub`, `.msg` (Outlook) |
| **Web / Markup** | `.html`, `.htm` |
| **Data** | `.csv`, `.json`, `.jsonl` |
| **Text** | `.txt`, `.text`, `.markdown`, `.md`* |
| **Code notebooks** | `.ipynb` |
| **Images** | `.jpg`, `.jpeg`, `.png` |
| **Audio / Video** | `.mp3`, `.m4a`, `.wav`, `.mp4` |
| **Archives** | `.zip` |

\* `.md` files are listed for completeness — but File2MD will **not** re-queue
generated `.md` files when scanning a folder, so re-running conversion on an
output directory is always safe.

### Optional dependencies

MarkItDown installs the format-specific parsers (pdfplumber, mammoth,
python-pptx, openpyxl, …) automatically when you install
`markitdown[all]`. If a particular format fails with a
*“requires an optional dependency”* message, install the matching extras:

```bash
pip install "markitdown[all]"     # everything (recommended)
pip install "markitdown[pdf]"     # PDF only
pip install "markitdown[docx]"    # DOCX only
pip install "markitdown[pptx]"    # PPTX only
pip install "markitdown[xlsx]"    # XLSX only
```

### Known limitations

- **Scanned PDFs** — PDFs that contain only images (no selectable text)
  will report *"No readable text could be extracted."* OCR is **not**
  included by design — it would add hundreds of megabytes of dependencies.
  If you need OCR, pre-process the PDF with an OCR tool (e.g. `ocrmypdf`)
  and then convert the resulting text-based PDF.
- **Password-protected files** — encrypted PDFs / Office documents are
  detected and reported. Remove the password first, then convert.
- **Legacy binary Office formats** (`.doc`, `.ppt`) — not supported by
  MarkItDown. Convert them to `.docx` / `.pptx` first.
- **XML** — not in the explicit supported-extensions list. MarkItDown's
  PlainTextConverter may still extract raw XML as text, but no semantic
  conversion is performed.
- **Very large files** — conversion happens one file at a time, but very
  large PDFs (1000+ pages) can still take a minute or two. The UI remains
  responsive throughout.

---

## Installation

### Prerequisites

- **Python 3.11 or newer** (3.12 recommended)
- **Windows 10 / 11** (also runs on macOS / Linux for development)
- ~250 MB free disk space for the virtualenv (mostly markitdown + pdfplumber)

### Setup

```bash
git clone <your-repo-url> file2md
cd file2md

python -m venv .venv
.venv\Scripts\activate         # Windows
# source .venv/bin/activate    # macOS / Linux

pip install -r requirements.txt
```

If you plan to run tests or build the executable, also install dev deps:

```bash
pip install -r requirements-dev.txt
```

---

## Running

### GUI mode

```bash
python main.py
```

That's it. The window opens, you drag files in (or click *Select Files* /
*Select Folder*), pick an output folder, and click *Convert*.

### CLI mode

```bash
# Convert a single file (output goes to <input_dir>/Markdown/ by default)
python cli.py report.pdf

# Specify a custom output directory
python cli.py report.pdf -o output/

# Convert a whole folder, recursively, mirroring the structure
python cli.py documents/ -r --preserve-structure -o markdown/

# Multiple inputs at once
python cli.py a.pdf b.docx c.xlsx -o out/

# Overwrite existing .md files
python cli.py report.pdf --overwrite

# Skip files whose output already exists (do not generate (1), (2), …)
python cli.py report.pdf --no-unique
```

CLI options:

| Option | Description |
|--------|-------------|
| `inputs` (positional, 1+) | Files or folders to convert. |
| `-o`, `--output DIR` | Output directory. Default: `<input_dir>/Markdown`. |
| `-r`, `--recursive` | When an input is a folder, walk it recursively. |
| `--overwrite` | Overwrite existing `.md` files. |
| `--no-unique` | Do not generate `report (1).md` on conflict; skip instead. |
| `--preserve-structure` | Mirror input folder structure inside the output directory. |
| `--version` | Print the version and exit. |

The CLI uses the **same conversion engine** as the GUI — there is no
duplicated logic.

---

## Building the Windows executable

File2MD ships as a **folder distribution** (onedir), not a single `.exe`.
This is deliberate:

- **Faster startup** — no per-launch extraction to a temp directory.
- **More reliable** — MarkItDown's converter discovery works against the
  real on-disk package layout.
- **Easier to debug** — missing dependency? Drop the `.pyd` into the
  dist folder without rebuilding.

### Build steps

```bash
.venv\Scripts\activate
build.bat
```

`build.bat` will:

1. Create the virtualenv if missing.
2. Install `requirements-dev.txt` (includes PyInstaller).
3. Run the test suite (aborts if any test fails).
4. Clean `build/` and `dist/`.
5. Run `pyinstaller File2MD.spec --clean --noconfirm`.

### Output

```
dist/
└── File2MD/
    ├── File2MD.exe        ← double-click to launch (no console window)
    ├── _internal/
    │   └── ...            (Python runtime + all dependencies)
    └── ...
```

You can zip the entire `dist/File2MD/` folder and distribute it. End users
do **not** need Python installed.

### Manual build (without build.bat)

```bash
pyinstaller File2MD.spec --clean --noconfirm
```

### Why not `--onefile`?

`--onefile` produces a single `File2MD.exe`, but:

- It must extract its contents to `%TEMP%` on every launch, adding 1–3
  seconds of startup time. MarkItDown's converter discovery is already
  slow; this compounds.
- markitdown's plugin system occasionally fails to find converters inside
  a onefile bootstrap. The onedir layout sidesteps this entirely.

If you absolutely need a single-file build, change `COLLECT(...)` to
`EXE(...)` in `File2MD.spec` and set `exclude_binaries=False`. Test
thoroughly before shipping.

---

## Architecture

```
file2md/
│
├── main.py              ← GUI entry point
├── cli.py               ← CLI entry point (reuses the same engine)
├── File2MD.spec         ← PyInstaller spec (onedir)
├── build.bat            ← Windows build script
├── requirements.txt     ← runtime dependencies
├── requirements-dev.txt ← dev / build dependencies
├── LICENSE
├── README.md
│
├── app/
│   ├── __init__.py
│   ├── config.py        ← Settings (dataclass) + ConfigManager (JSON)
│   ├── logger.py        ← Rotating log file in user app-data dir
│   ├── utils.py         ← Filename safety, Markdown cleanup, encoding
│   ├── file_manager.py  ← Format discovery, recursive walk, output paths
│   ├── converter.py     ← MarkItDown wrapper + friendly error translation
│   ├── queue_manager.py ← Threaded worker, cancellation, status callbacks
│   └── gui.py           ← Tkinter window, drag-drop, dialogs
│
└── tests/
    ├── __init__.py
    ├── test_utils.py
    ├── test_file_manager.py
    └── test_converter.py
```

### Module responsibilities

- **`config.py`** — A `Settings` dataclass with sensible defaults, plus a
  `ConfigManager` that loads / saves JSON in the user's app-data directory.
  No database, no registry.

- **`logger.py`** — Configures a rotating file handler
  (`%APPDATA%\File2MD\logs\file2md.log` on Windows) plus stderr output.
  Idempotent; never logs document content.

- **`utils.py`** — Pure functions: filename sanitization (Windows-safe),
  unique path generation, line-ending normalization, Markdown whitespace
  cleanup (does **not** touch tables / code blocks / lists / links).

- **`file_manager.py`** — Discovers supported extensions **dynamically**
  by introspecting the installed MarkItDown version's converter modules.
  Walks folders recursively (or flat), filters out `.md` outputs, and
  computes output paths with structure preservation.

- **`converter.py`** — Thin wrapper around `MarkItDown.convert()`. Lazily
  constructs the engine on first use. Translates every MarkItDown exception
  type into a user-facing `ConversionError` with a clear one-line reason.

- **`queue_manager.py`** — Owns a single daemon worker thread that
  consumes a `queue.Queue` of `Job` objects. Cancellation is cooperative:
  a flag stops new jobs from being dequeued; the running conversion is
  allowed to finish. Status callbacks flow back to the GUI through the
  caller-provided callables (which the GUI marshals via `widget.after`).

- **`gui.py`** — The Tkinter window. Builds a flat modern theme
  (`#2563eb` accent, Segoe UI), registers drag-and-drop via `tkinterdnd2`
  (with graceful fallback), and wires the queue manager's callbacks into
  `widget.after(0, ...)` so every UI mutation happens on the Tk main
  thread. Includes `SettingsDialog` and `AboutDialog`.

### Threading model

```
┌─────────────────┐                ┌────────────────────┐
│  Tk main thread │  ← after(0) ←  │  Worker thread     │
│  (UI updates)   │                │  (MarkItDown call) │
└─────────────────┘                └────────────────────┘
        │                                   │
        │  enqueue(job)                     │  convert_file(path)
        │ ─────────────────────────────────►│ ────────────────────►
        │                                   │  write_text_file(out)
        │                                   │ ◄────────────────────
        │  ◄── on_progress / on_job_updated / on_batch_complete ────
```

- Only **one** worker thread exists for the lifetime of the app.
- One file is converted at a time → low, predictable memory usage.
- UI updates always go through `widget.after(0, ...)` → Tk's mainloop is
  the only thread that ever touches widgets.
- Cancellation sets a flag → worker drains the queue, marking remaining
  jobs as `Cancelled`. No `Thread.terminate()` (which doesn't exist
  anyway and would corrupt half-written files).

---

## Testing

```bash
.venv\Scripts\activate
pytest tests -v
```

Tests cover:

- Filename sanitization (Unicode, invalid chars, empty, oversized)
- Output-path generation (no-conflict, auto-rename, overwrite, skip)
- Markdown cleanup (line endings, trailing whitespace, blank lines,
  preservation of tables and code blocks)
- UTF-8 output without BOM
- Format detection (supported / unsupported / case-insensitive / `.md`
  excluded)
- Recursive vs flat folder discovery
- Folder-structure preservation
- Conversion of `.txt`, `.json`, `.csv`, real `.pdf`, real `.docx`
- Unicode preservation through the full pipeline
- Error handling: missing file, empty file, directory-as-input,
  unsupported format, corrupted PDF, no-traceback-in-message

---

## Troubleshooting

### “PDF extraction failed” / “No readable text could be extracted”

The PDF is likely scanned (image-only) or has unusual encoding. Open the
PDF in a viewer — if you cannot select text, neither can MarkItDown.
Run the PDF through `ocrmypdf` first:

```bash
ocrmypdf input.pdf input_ocr.pdf
python cli.py input_ocr.pdf -o out/
```

### “Permission denied when reading”

The file is open in another program (Word, Excel, a PDF viewer). Close
it and try again. If the file is on a network share with restrictive
permissions, copy it locally first.

### “requires an optional dependency that is not installed”

You installed bare `markitdown` instead of `markitdown[all]`. Reinstall:

```bash
pip install "markitdown[all]"
```

### The output directory does not exist

File2MD creates it automatically. If creation fails (e.g. the parent is
read-only), File2MD falls back to `~/Documents/Markdown`. Change the
output directory in *Settings* to a writable location.

### The application log

Logs are written to:

- **Windows:** `%APPDATA%\File2MD\logs\file2md.log`
- **macOS:** `~/Library/Application Support/File2MD/logs/file2md.log`
- **Linux:** `~/.config/file2md/logs/file2md.log`

The log file rotates at 512 KB and keeps 3 backups. The log never
contains your document contents — only file paths, sizes, and exception
messages.

Open the log from the GUI via **Help → View Log File**.

### Drag and drop does not work

`tkinterdnd2` requires native OS support. On Windows it works
out-of-the-box. If you somehow end up without it, File2MD still works —
just use the *Select Files* / *Select Folder* buttons.

### The build is too big

MarkItDown pulls in a lot of optional dependencies. If you only need a
subset of formats, edit `requirements.txt` to install
`markitdown[pdf,docx]` instead of `markitdown[all]`, and remove the
matching `hiddenimports` in `File2MD.spec`.

---

## Privacy

File2MD processes your files **entirely on your computer**. Your
documents are not uploaded to a server. There is no telemetry, no
analytics, no crash reporting, and no automatic update checker.

The only outbound network access happens if you click the
*MarkItDown project* link in the About dialog (opens your default
browser to GitHub).

---

## Credits

- **[Microsoft MarkItDown](https://github.com/microsoft/markitdown)** —
  the conversion engine.
- **[tkinterdnd2](https://github.com/pmgagnon/tkinterdnd2)** — Tkinter
  drag-and-drop bindings.

File2MD itself is licensed under the MIT License — see [LICENSE](LICENSE).

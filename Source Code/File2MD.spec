# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller spec for File2MD (onedir build).

Why onedir (not onefile)?
  - Faster startup: no need to unpack a single .exe to a temp dir on every
    launch. MarkItDown loads many converters dynamically at startup; that
    is already slow enough without adding 1–2 seconds of unpacking.
  - More reliable: markitdown's plugin / converter discovery depends on a
    real on-disk package layout. onefile builds occasionally hide package
    data files behind the bootstrap extraction, which can break converters.
  - Easier to debug: if a converter is missing a dependency, the user can
    drop the missing .pyd / .dll into the dist folder without rebuilding.

Build command:

    pyinstaller File2MD.spec --clean --noconfirm

Output:

    dist/File2MD/File2MD.exe   (launchable, no console window)
"""

from PyInstaller.utils.hooks import collect_data_files, collect_submodules

block_cipher = None

# Magika (used internally by MarkItDown for content-type detection) ships
# an ONNX model file. PyInstaller's automatic hooks do not catch this, so
# we collect every data file inside the magika package explicitly.
magika_datas = collect_data_files("magika")

# MarkItDown's converters are imported dynamically; collect their submodules
# so PyInstaller sees them at analysis time.
markitdown_hidden = collect_submodules("markitdown.converters")

a = Analysis(
    ["main.py"],
    pathex=[],
    binaries=[],
    datas=magika_datas,
    hiddenimports=[
        "markitdown",
        "markitdown.converters",
    ] + markitdown_hidden + [
        # Optional dependencies that some converters use.
        "pdfplumber",
        "mammoth",
        "openpyxl",
        "xlrd",
        "pptx",
        "bs4",
        "lxml",
        "PIL",
        "pandas",
        "magika",
        # Drag-and-drop
        "tkinterdnd2",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        # Exclude heavyweight optional features we do not use.
        "matplotlib",
        "notebook",
        "jupyter",
        "IPython",
        "pytest",
        "azure",
        "azure-ai-documentintelligence",
        "azure-ai-contentunderstanding",
        "azure-identity",
        "msal",
        "msal_extensions",
        "speech_recognition",
        "pydub",
        "youtube_transcript_api",
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="File2MD",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,  # No console window — this is a GUI app.
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,  # Set this to "assets/file2md.ico" if you add an icon later.
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="File2MD",
)

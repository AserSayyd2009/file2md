
# File2MD

**A lightweight Windows desktop application for converting documents and data files into Markdown using Microsoft's MarkItDown.**

File2MD provides a simple, modern desktop interface built with CustomTkinter, allowing users to convert individual files or entire folders into Markdown.

## 🚀 Download and Use

**Want to use File2MD without installing Python or setting up a development environment?**

### [⬇️ Download File2MD for Windows](../../releases/latest)

1. Open the [latest release](../../releases/latest).
2. Download `File2MD.zip` from the release assets.
3. Extract the ZIP file to a folder on your computer.
4. Open the extracted folder.
5. Double-click `File2MD.exe` to launch the application.

**That's it!** No separate Python installation or manual dependency installation should be necessary.

> **Important:** Extract the entire ZIP archive before running the application. Keep its accompanying files together, and do not move `File2MD.exe` out of the extracted folder.

If you encounter a Windows security warning, verify that you downloaded the archive from this project's official Releases page before deciding whether to run it.

## ✨ Features

- 📄 Convert supported documents and data files to Markdown
- 📁 Convert multiple files or entire folders
- 🔄 Recursive folder scanning
- 🗂️ Optional preservation of the original folder structure
- 🌐 Unicode and Arabic filename support
- 📊 Conversion queue and file status tracking
- 📈 Conversion progress indicator
- ⛔ Cancellation support
- 🛡️ Protection against accidental file overwrites
- 🌙 Dark, Light, and System appearance modes
- 💻 Modern CustomTkinter interface
- 🔒 Designed for local document processing
- 📦 Standalone Windows application packaged with PyInstaller

## 📚 Supported Formats

File2MD uses Microsoft's [MarkItDown](https://github.com/microsoft/markitdown) as its conversion engine.

Depending on the installed dependencies, supported formats may include:

- PDF
- DOCX
- PPTX
- XLSX
- XLS
- HTML
- TXT
- CSV
- JSON
- XML
- Other formats supported by MarkItDown

Actual format support depends on the MarkItDown version and the dependencies included in the application.

## 🖥️ System Requirements

### Packaged Windows Application

- Windows
- The complete extracted File2MD package

Python does not need to be installed separately when using a correctly packaged release.

### Running from Source

- Python 3.10.x
- pip
- Dependencies listed in `requirements.txt`

## 🛠️ Running from Source

Developers who want to inspect, modify, or contribute to File2MD can clone the repository:

```bash
git clone https://github.com/YOUR_USERNAME/YOUR_REPO.git
cd YOUR_REPO
```

Create and activate a Python 3.10 virtual environment:

```bash
py -3.10 -m venv .venv
.venv\Scripts\activate
```

Install the dependencies:

```bash
python -m pip install --upgrade pip
pip install -r requirements.txt
```

Run the application:

```bash
python main.py
```

## 📦 Building the Windows Application

File2MD uses PyInstaller to package the application for Windows.

If a build script is included, run:

```bash
build.bat
```

Alternatively, follow the build instructions and configuration provided in the repository.

The packaged application must include the dependencies and data files required by the selected MarkItDown installation.

**For most users, downloading the prebuilt ZIP from Releases is the recommended option.**

## 🔒 Privacy

File2MD is designed for local processing. It does not intentionally upload documents or their contents to a remote server.

Normal document conversion does not require a cloud account or API key.

## ⚠️ Limitations

Conversion quality depends on the original document and MarkItDown.

- Scanned or image-only PDFs may require OCR.
- Complex layouts may not be reproduced perfectly in Markdown.
- Some formats may require additional dependencies.
- Images, diagrams, and advanced formatting may not always be preserved exactly.

File2MD focuses on preserving useful document content and structure rather than reproducing the original document pixel-for-pixel.

## 🛠️ Technology Stack

- **Python 3.10** — Application runtime
- **CustomTkinter** — Desktop GUI
- **Microsoft MarkItDown** — Document conversion
- **PyInstaller** — Windows executable packaging
-

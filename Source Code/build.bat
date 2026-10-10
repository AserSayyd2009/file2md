@echo off
REM =====================================================================
REM File2MD Windows build script.
REM
REM Builds a redistributable folder dist\File2MD\ using PyInstaller (onedir).
REM Run from a Windows command prompt inside the project directory:
REM
REM     build.bat
REM
REM Prerequisites:
REM   - Python 3.11+ on PATH
REM   - This script will create a virtualenv at .venv if it does not exist
REM     and install requirements-dev.txt (which includes pyinstaller).
REM =====================================================================

setlocal

REM --- Locate Python ---
where python >nul 2>nul
if errorlevel 1 (
    echo [error] Python not found on PATH. Install Python 3.11+ from https://python.org
    exit /b 1
)

REM --- Create virtualenv if missing ---
if not exist ".venv\Scripts\python.exe" (
    echo [info] Creating virtual environment at .venv ...
    python -m venv .venv
    if errorlevel 1 (
        echo [error] Failed to create virtual environment.
        exit /b 1
    )
)

REM --- Install / update dependencies ---
echo [info] Installing dependencies ...
".venv\Scripts\python.exe" -m pip install --upgrade pip
".venv\Scripts\python.exe" -m pip install -r requirements-dev.txt
if errorlevel 1 (
    echo [error] Dependency installation failed.
    exit /b 1
)

REM --- Run the test suite first ---
echo [info] Running tests ...
".venv\Scripts\python.exe" -m pytest tests -q
if errorlevel 1 (
    echo [error] Tests failed. Aborting build.
    exit /b 1
)

REM --- Clean previous build outputs ---
echo [info] Cleaning previous build outputs ...
if exist "build" rmdir /s /q "build"
if exist "dist" rmdir /s /q "dist"

REM --- Build with PyInstaller ---
echo [info] Building File2MD.exe (onedir) ...
".venv\Scripts\python.exe" -m PyInstaller File2MD.spec --clean --noconfirm
if errorlevel 1 (
    echo [error] PyInstaller build failed.
    exit /b 1
)

echo.
echo [success] Build complete.
echo.
echo Output:
echo   dist\File2MD\File2MD.exe
echo.
echo You can zip the dist\File2MD folder and distribute it.
echo Users do NOT need Python installed to run File2MD.exe.

endlocal

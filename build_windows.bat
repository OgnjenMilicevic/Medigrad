@echo off
REM build_windows.bat — one-shot build of Datagrad.exe on Windows.
REM Run from the project folder in a regular Command Prompt (no admin needed).
REM Requires: Python 3.11 or 3.12 (64-bit) on PATH.

setlocal

echo ============================================
echo  Datagrad - Windows build
echo ============================================

REM 1. Create an isolated virtual environment
if not exist ".venv\" (
    echo [1/4] Creating virtual environment...
    python -m venv .venv
) else (
    echo [1/4] Reusing existing .venv
)

call .venv\Scripts\activate.bat

REM 2. Install dependencies + PyInstaller
echo [2/4] Installing dependencies...
python -m pip install --upgrade pip
pip install -r requirements.txt
pip install pyinstaller

REM 3. Build the one-folder app with the spec
echo [3/4] Running PyInstaller...
pyinstaller Datagrad.spec --noconfirm
if errorlevel 1 (
    echo PyInstaller build FAILED.
    exit /b 1
)

echo [4/4] Build complete.
echo.
echo   Portable app:   dist\Datagrad\Datagrad.exe
echo.
echo   To make an installer, compile Datagrad.iss with Inno Setup:
echo       ISCC.exe Datagrad.iss
echo   which produces  Output\Datagrad-Setup.exe
echo.

endlocal

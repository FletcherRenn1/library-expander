@echo off
setlocal
echo ======================================
echo   Library Expander  ^|  Build
echo ======================================
echo.

echo [1/2] Installing build tools...
pip install pyinstaller img2pdf Pillow gallery-dl
if errorlevel 1 ( echo ERROR: pip install failed & pause & exit /b 1 )

set _PY=
python3.13 -m PyInstaller --version >nul 2>&1 && set _PY=python3.13
if not defined _PY  python3   -m PyInstaller --version >nul 2>&1 && set _PY=python3
if not defined _PY  python    -m PyInstaller --version >nul 2>&1 && set _PY=python
if not defined _PY  py -3     -m PyInstaller --version >nul 2>&1 && set _PY=py -3
if not defined _PY (
    echo ERROR: Could not find Python with PyInstaller installed.
    echo Run: python3.13 -m pip install pyinstaller
    pause & exit /b 1
)
echo Using Python: %_PY%

echo.
echo [2/2] Building Library Expander.exe...
%_PY% -m PyInstaller ^
  --onefile ^
  --noconsole ^
  --name "Library Expander" ^
  --collect-all gallery_dl ^
  --hidden-import=PIL ^
  --hidden-import=PIL.Image ^
  --hidden-import=PIL.JpegImagePlugin ^
  --hidden-import=PIL.PngImagePlugin ^
  --hidden-import=PIL.WebPImagePlugin ^
  --hidden-import=img2pdf ^
  app.py
if errorlevel 1 ( echo ERROR: build failed & pause & exit /b 1 )

echo.
echo ======================================
echo   Done!
echo   Standalone exe: dist\Library Expander.exe
echo   Welcome to the Library my friend :3
echo ======================================
pause

@echo off
REM Build a standalone Windows .exe (no Python needed to run the result).
REM Requires: pip install pyinstaller
python -m PyInstaller --onefile --windowed --name CameraTeleprompter teleprompter.py
echo.
echo Done. The executable is in the dist\ folder: dist\CameraTeleprompter.exe

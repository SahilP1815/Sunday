@echo off
echo ================================================
echo   Sunday Desktop AI Assistant - Installer
echo ================================================
echo.

:: Check Python is installed
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python is not installed or not in PATH.
    echo Download Python 3.10+ from https://python.org
    pause
    exit /b 1
)

echo [1/3] Upgrading pip...
python -m pip install --upgrade pip --quiet

echo [2/3] Installing dependencies...
pip install -r requirements.txt

echo [3/3] Done!
echo.
echo ================================================
echo   Installation complete. Run:  python sunday.py
echo ================================================
pause

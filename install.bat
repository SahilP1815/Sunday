@echo off
echo ====================================================
echo   Sunday AI Assistant - Comprehensive Setup
echo ====================================================
echo.

:: Check Python
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python is not installed or not in PATH.
    echo Please install Python 3.10+ and make sure it is in your PATH.
    pause
    exit /b 1
)

:: Check Node.js
node --version >nul 2>&1
if errorlevel 1 (
    echo [WARNING] Node.js is not installed or not in PATH.
    echo Node.js is optional but recommended for running the Sunday Web Backend and HTML UI.
    echo You can download it from https://nodejs.org
    echo.
)

echo [1/3] Upgrading pip...
python -m pip install --upgrade pip --quiet

echo [2/3] Installing Python dependencies...
pip install -r sunday-desktop\requirements.txt

:: If node is installed, install backend dependencies
node --version >nul 2>&1
if not errorlevel 1 (
    echo [3/3] Installing Node.js backend dependencies...
    cd sunday-backend
    call npm install
    cd ..
) else (
    echo [3/3] Skipping Node.js dependencies (Node.js not installed).
)

echo.
echo ====================================================
echo   Setup Complete!
echo   To launch Sunday, run: run.bat
echo ====================================================
pause

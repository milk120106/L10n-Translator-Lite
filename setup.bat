@echo off
cd /d "%~dp0"

where uv >nul 2>nul
if errorlevel 1 (
    echo uv was not found in PATH. Please install uv first: https://docs.astral.sh/uv/
    pause
    exit /b 1
)

echo [1/2] Creating virtual environment with uv
uv venv
if errorlevel 1 (
    echo Failed to create the virtual environment. Please check the errors above.
    pause
    exit /b 1
)

echo [2/2] Installing dependencies from requirements.txt
uv pip install -r requirements.txt
if errorlevel 1 (
    echo Dependency installation failed. Please check the errors above.
    pause
    exit /b 1
)

echo.
echo Setup finished. Run start.bat to launch L10n Translator Lite.
pause
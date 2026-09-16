@echo off
setlocal
cd /d "%~dp0"

echo === Astra Studio clean reinstall ===
if exist ".venv" (
    echo Removing existing .venv...
    rmdir /s /q ".venv"
    if exist ".venv" (
        echo Failed to remove .venv. Close Astra Studio and try again.
        pause
        exit /b 1
    )
)

call install_app.bat
if errorlevel 1 exit /b 1
exit /b 0

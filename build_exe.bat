@echo off
chcp 65001 >nul
setlocal
cd /d "%~dp0"

set "PY_EXE="
set "PY_ARGS="

if exist ".venv\Scripts\python.exe" (
    set "PY_EXE=%~dp0.venv\Scripts\python.exe"
) else (
    where py >nul 2>nul
    if not errorlevel 1 (
        py -3 -c "import sys" >nul 2>nul
        if not errorlevel 1 (
            set "PY_EXE=py"
            set "PY_ARGS=-3"
        )
    )
    if not defined PY_EXE (
        where python >nul 2>nul
        if not errorlevel 1 (
            python -c "import sys" >nul 2>nul
            if not errorlevel 1 set "PY_EXE=python"
        )
    )
)

if not defined PY_EXE (
    echo No working Python interpreter was found. Run install_app.bat first.
    pause
    exit /b 1
)

"%PY_EXE%" %PY_ARGS% -m pip install -r requirements.txt
if errorlevel 1 (
    echo Failed to install build dependencies.
    pause
    exit /b 1
)

"%PY_EXE%" %PY_ARGS% -m PyInstaller --noconfirm --clean astra_studio.spec
if errorlevel 1 (
    echo PyInstaller build failed.
    pause
    exit /b 1
)

if not exist "dist\Astra Studio\Astra Studio.exe" (
    echo PyInstaller completed without the expected portable executable.
    pause
    exit /b 1
)

if "%ASTRA_CREATE_SHORTCUT%"=="1" (
    powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\create_desktop_shortcut.ps1"
    if errorlevel 1 echo EXE was built, but the shortcut could not be created.
) else (
    echo Desktop shortcut was not requested. Set ASTRA_CREATE_SHORTCUT=1 to create it.
)

echo.
echo Done: %~dp0dist\Astra Studio\Astra Studio.exe
if not "%ASTRA_NO_PAUSE%"=="1" pause
exit /b 0

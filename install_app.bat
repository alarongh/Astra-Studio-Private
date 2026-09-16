@echo off
chcp 65001 >nul
setlocal
cd /d "%~dp0"

echo === Astra Studio: application setup ===
echo.
echo Checking Python...
set "PY_EXE="
set "PY_ARGS="

where py >nul 2>nul
if not errorlevel 1 (
    py -3 -c "import sys; print(sys.executable)" >nul 2>nul
    if not errorlevel 1 (
        set "PY_EXE=py"
        set "PY_ARGS=-3"
    )
)

if not defined PY_EXE (
    where python >nul 2>nul
    if not errorlevel 1 (
        python -c "import sys; print(sys.executable)" >nul 2>nul
        if not errorlevel 1 set "PY_EXE=python"
    )
)

if not defined PY_EXE (
    for %%V in (314 313 312 311) do (
        if not defined PY_EXE if exist "%LOCALAPPDATA%\Programs\Python\Python%%V\python.exe" (
            "%LOCALAPPDATA%\Programs\Python\Python%%V\python.exe" -c "import sys" >nul 2>nul
            if not errorlevel 1 set "PY_EXE=%LOCALAPPDATA%\Programs\Python\Python%%V\python.exe"
        )
    )
)

if not defined PY_EXE (
    echo No working Python interpreter was found. Trying WinGet installation...
    powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\install_python.ps1"
    if errorlevel 1 (
        echo Python installation failed.
        pause
        exit /b 1
    )

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

    if not defined PY_EXE (
        for %%V in (314 313 312 311) do (
            if not defined PY_EXE if exist "%LOCALAPPDATA%\Programs\Python\Python%%V\python.exe" (
                "%LOCALAPPDATA%\Programs\Python\Python%%V\python.exe" -c "import sys" >nul 2>nul
                if not errorlevel 1 set "PY_EXE=%LOCALAPPDATA%\Programs\Python\Python%%V\python.exe"
            )
        )
    )

    if not defined PY_EXE (
        echo Python was installed, but this Windows process cannot see it yet.
        echo Run install_app.bat again. If that still fails, restart Windows once.
        pause
        exit /b 1
    )
)

echo Using Python: %PY_EXE% %PY_ARGS%
echo Creating virtual environment...
"%PY_EXE%" %PY_ARGS% -m venv .venv
if errorlevel 1 (
    echo Failed to create .venv.
    pause
    exit /b 1
)

if not exist ".venv\Scripts\python.exe" (
    echo .venv was not created correctly.
    pause
    exit /b 1
)

echo Installing dependencies...
".venv\Scripts\python.exe" -m pip install --upgrade pip
if errorlevel 1 (
    echo Failed to upgrade pip.
    pause
    exit /b 1
)

".venv\Scripts\python.exe" -m pip install -r requirements.txt
if errorlevel 1 (
    echo Failed to install Astra Studio dependencies.
    pause
    exit /b 1
)

if exist "requirements-test.txt" (
    echo Installing bundled acceptance-test dependencies...
    ".venv\Scripts\python.exe" -m pip install -r requirements-test.txt
    if errorlevel 1 (
        echo Failed to install acceptance-test dependencies.
        pause
        exit /b 1
    )
)

echo Creating desktop shortcut...
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\create_desktop_shortcut.ps1"
if errorlevel 1 (
    echo Astra Studio was installed, but the desktop shortcut could not be created.
)

echo.
echo Done. The Astra Studio shortcut should now be available on the desktop.
pause
exit /b 0

@echo off
chcp 65001 >nul
setlocal
cd /d "%~dp0"

if exist ".venv\Scripts\python.exe" (
    ".venv\Scripts\python.exe" main.py
    if errorlevel 1 exit /b 1
    exit /b 0
)

where py >nul 2>nul
if not errorlevel 1 (
    py -3 -c "import sys" >nul 2>nul
    if not errorlevel 1 (
        py -3 main.py
        if errorlevel 1 exit /b 1
        exit /b 0
    )
)

where python >nul 2>nul
if not errorlevel 1 (
    python -c "import sys" >nul 2>nul
    if not errorlevel 1 (
        python main.py
        if errorlevel 1 exit /b 1
        exit /b 0
    )
)

for %%V in (314 313 312 311) do (
    if exist "%LOCALAPPDATA%\Programs\Python\Python%%V\python.exe" (
        "%LOCALAPPDATA%\Programs\Python\Python%%V\python.exe" -c "import sys" >nul 2>nul
        if not errorlevel 1 (
            "%LOCALAPPDATA%\Programs\Python\Python%%V\python.exe" main.py
            if errorlevel 1 exit /b 1
            exit /b 0
        )
    )
)

echo No working Python interpreter was found. Run install_app.bat first or install Python manually.
exit /b 1

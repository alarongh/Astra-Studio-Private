@echo off
chcp 65001 >nul
setlocal
cd /d "%~dp0"

if exist ".venv\Scripts\pythonw.exe" (
    start "" ".venv\Scripts\pythonw.exe" "%~dp0main.py"
    exit /b 0
)

where py >nul 2>nul
if not errorlevel 1 (
    py -3 -c "import sys" >nul 2>nul
    if not errorlevel 1 (
        where pyw >nul 2>nul
        if not errorlevel 1 (
            start "" pyw -3 "%~dp0main.py"
        ) else (
            start "" /B py -3 "%~dp0main.py"
        )
        exit /b 0
    )
)

where python >nul 2>nul
if not errorlevel 1 (
    python -c "import sys" >nul 2>nul
    if not errorlevel 1 (
        where pythonw >nul 2>nul
        if not errorlevel 1 (
            start "" pythonw "%~dp0main.py"
        ) else (
            start "" /B python "%~dp0main.py"
        )
        exit /b 0
    )
)

for %%V in (314 313 312 311) do (
    if exist "%LOCALAPPDATA%\Programs\Python\Python%%V\pythonw.exe" (
        start "" "%LOCALAPPDATA%\Programs\Python\Python%%V\pythonw.exe" "%~dp0main.py"
        exit /b 0
    )
)

echo No working Python interpreter was found. Run install_app.bat first or install Python manually.
exit /b 1

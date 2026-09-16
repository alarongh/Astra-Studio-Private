@echo off
setlocal
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
    echo Astra Studio virtual environment was not found.
    echo Run install_app.bat first.
    pause
    exit /b 1
)

echo === Astra Studio Windows acceptance tests ===
echo.
echo === compileall ===
".venv\Scripts\python.exe" -m compileall -q main.py core tests
if errorlevel 1 goto failed
if not errorlevel 0 goto failed

echo.
echo === static smoke ===
".venv\Scripts\python.exe" tests\smoke_static.py
if errorlevel 1 goto failed
if not errorlevel 0 goto failed

echo.
echo === pytest ===
".venv\Scripts\python.exe" -m pytest -q -rs
if errorlevel 1 goto failed
if not errorlevel 0 goto failed

echo.
echo Automated acceptance tests completed successfully.
echo.
if not "%ASTRA_NO_PAUSE%"=="1" pause
exit /b 0

:failed
echo.
echo Automated acceptance tests reported failures.
echo.
if not "%ASTRA_NO_PAUSE%"=="1" pause
exit /b 1

@echo off
title دار التعلیم والقرآن — Islamic Education App
color 0a

echo ========================================================
echo   دار التعلیم والقرآن — ISLAMIC EDUCATION ACADEMY
echo   Complete Islamic Education App & Admin Management System
echo ========================================================
echo.

cd /d "%~dp0"

set "PY_CMD="

if exist "%~dp0venv\Scripts\python.exe" (
    set "PY_CMD=%~dp0venv\Scripts\python.exe"
    goto :PYTHON_FOUND
)

if exist "%~dp0.venv\Scripts\python.exe" (
    set "PY_CMD=%~dp0.venv\Scripts\python.exe"
    goto :PYTHON_FOUND
)

if exist "%LOCALAPPDATA%\Python\pythoncore-3.14-64\python.exe" (
    set "PY_CMD=%LOCALAPPDATA%\Python\pythoncore-3.14-64\python.exe"
    goto :PYTHON_FOUND
)

if exist "%LOCALAPPDATA%\Python\bin\python.exe" (
    set "PY_CMD=%LOCALAPPDATA%\Python\bin\python.exe"
    goto :PYTHON_FOUND
)

python --version >nul 2>&1
if %errorlevel% equ 0 (
    set "PY_CMD=python"
    goto :PYTHON_FOUND
)

py --version >nul 2>&1
if %errorlevel% equ 0 (
    set "PY_CMD=py"
    goto :PYTHON_FOUND
)

:PYTHON_NOT_FOUND
echo [ERROR] Python was not found on this system!
echo Please make sure Python is installed.
pause
exit /b 1

:PYTHON_FOUND
echo [1/3] Using Python: %PY_CMD%

echo [2/3] Checking dependencies...
"%PY_CMD%" -c "import uvicorn, fastapi, pymysql, sqlalchemy, bcrypt" >nul 2>&1
if %errorlevel% neq 0 (
    echo Installing missing dependencies from requirements.txt...
    "%PY_CMD%" -m pip install -r requirements.txt
) else (
    echo Dependencies are already satisfied!
)

echo [3/3] Starting Islamic Education App on http://localhost:8000 ...
start "" http://localhost:8000
"%PY_CMD%" -m uvicorn main:app --host 0.0.0.0 --port 8000 --reload

pause

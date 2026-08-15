@echo off
setlocal
cd /d "%~dp0"

REM ---------------------------------------------------------------------------
REM MediaFlow dev launcher for Windows (RD-011, RD-031..RD-034)
REM Mirrors run.sh from the macOS source: create .venv if missing, install
REM requirements, then start uvicorn bound to 127.0.0.1.
REM ---------------------------------------------------------------------------

if not exist ".venv\Scripts\python.exe" (
    where py >nul 2>nul
    if not errorlevel 1 (
        py -m venv .venv
    ) else (
        where python >nul 2>nul
        if errorlevel 1 (
            echo [run.bat] Neither 'py' nor 'python' is on PATH. Install Python 3.9+.
            exit /b 1
        )
        python -m venv .venv
    )
    if not exist ".venv\Scripts\python.exe" (
        echo [run.bat] Failed to create virtual environment in .venv
        exit /b 1
    )
    .venv\Scripts\python.exe -m pip install --upgrade pip
    .venv\Scripts\python.exe -m pip install -r requirements.txt || (
        echo [run.bat] Failed to install dependencies from requirements.txt
        exit /b 1
    )
)

.venv\Scripts\python.exe -m uvicorn app:app --host 127.0.0.1 --port 8765 --reload
endlocal

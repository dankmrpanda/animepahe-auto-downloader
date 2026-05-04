@echo off
setlocal EnableExtensions
cd /d "%~dp0"

echo Starting AnimePahe Web Downloader...

REM Attempt to activate Conda base using the provided activate.bat (works for Windows installs)
if exist "C:\ProgramData\miniconda3\Scripts\activate.bat" (
    echo Activating conda from C:\ProgramData\miniconda3
    call "C:\ProgramData\miniconda3\Scripts\activate.bat" "C:\ProgramData\miniconda3"
) else (
    REM Fallback to PATH-based conda (if available)
    echo Conda activation script not found at C:\ProgramData\miniconda3\Scripts\activate.bat; relying on PATH
)

REM Activate the animepahe environment
call conda activate animepahe

echo Running localhost startup checks and installing missing dependencies...
python scripts\localhost_checks.py --mode start --install-missing
if errorlevel 1 (
    echo Startup checks failed. Resolve the errors above and try again.
    goto done
)

cd web

set RESTART_DELAY=3
set LISTEN_PID=

for /f "tokens=5" %%p in ('netstat -ano ^| findstr /R /C:"127.0.0.1:8000 .*LISTENING"') do (
    set LISTEN_PID=%%p
)

if defined LISTEN_PID (
    echo Port 8000 is already in use ^(PID %LISTEN_PID%^).
    echo An API server is likely already running at http://127.0.0.1:8000
    echo Stop the existing server before starting a new one.
    goto done
)

:runserver
echo Starting API server in production mode (no reload)...
python -m uvicorn main:app --host 127.0.0.1 --port 8000
set EXIT_CODE=%ERRORLEVEL%

if %EXIT_CODE% EQU 0 (
    echo API server stopped cleanly.
    goto done
)

echo API server crashed with exit code %EXIT_CODE%. Restarting in %RESTART_DELAY%s...
timeout /t %RESTART_DELAY% /nobreak > nul
goto runserver

:done
pause
endlocal

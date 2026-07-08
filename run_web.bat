@echo off
setlocal EnableExtensions
cd /d "%~dp0"

echo Starting AnimePahe Web Downloader...

REM Refresh host/session-related environment variables on every launch.
REM cookies.txt is expected next to this batch file and is ignored by git.
set "KWIK_COOKIE_FILE=%~dp0cookies.txt"
set "ANIMEPAHE_COOKIE_FILE=%~dp0cookies.txt"
set "ANIMEPAHE_CLEARANCE_MODE=browser"
set "ANIMEPAHE_BROWSER=seleniumbase"
set "ANIMEPAHE_BROWSER_HEADLESS=false"
set "ANIMEPAHE_CLEARANCE_STORE=%~dp0clearance.json"
set "ANIMEPAHE_CURL_IMPERSONATE=chrome"
REM Optional: pin a domain (otherwise auto-detected).
REM set "ANIMEPAHE_BASE_URL=https://animepahe.pw"
REM Only set a UA if you also export matching cookies.txt (advanced).
if exist "%~dp0user-agent.txt" (
    set /p BROWSER_USER_AGENT=<"%~dp0user-agent.txt"
    echo Using browser user-agent from user-agent.txt
    set "KWIK_USER_AGENT=%BROWSER_USER_AGENT%"
    set "ANIMEPAHE_USER_AGENT=%BROWSER_USER_AGENT%"
)

if exist "%KWIK_COOKIE_FILE%" (
    echo Using cookie fallback file: %KWIK_COOKIE_FILE%
) else (
    echo Optional cookie fallback not found: %KWIK_COOKIE_FILE%
)
echo Cloudflare clearance mode: %ANIMEPAHE_CLEARANCE_MODE%

where uv > nul 2> nul
if errorlevel 1 (
    echo UV is required but was not found on PATH.
    echo Install UV from https://docs.astral.sh/uv/getting-started/installation/
    echo Then reopen this terminal and run run_web.bat again.
    goto done
)

echo Synchronizing Python dependencies with UV...
uv sync
if errorlevel 1 (
    echo UV dependency sync failed. Resolve the errors above and try again.
    goto done
)

echo Running localhost startup checks...
uv run python scripts\localhost_checks.py --mode start
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
uv run python -m uvicorn main:app --host 127.0.0.1 --port 8000
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

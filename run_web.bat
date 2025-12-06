@echo off
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

cd web
python -m uvicorn main:app --reload
pause
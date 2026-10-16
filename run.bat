@echo off
setlocal
cd /d "%~dp0"
if not exist .venv\Scripts\python.exe (
  py -3 -m venv .venv
  if errorlevel 1 goto fail
)
.venv\Scripts\python.exe -m pip install --upgrade pip
if errorlevel 1 goto fail
.venv\Scripts\python.exe -m pip install -r requirements.txt
if errorlevel 1 goto fail
where ffmpeg >nul 2>nul
if errorlevel 1 echo FFmpeg is required: winget install --id Gyan.FFmpeg -e then reopen this terminal.
.venv\Scripts\python.exe -m pip install deno
if errorlevel 1 goto fail
.venv\Scripts\python.exe app.py
if errorlevel 1 goto fail
exit /b 0
:fail
echo Setup or launch failed. Install Python 3.10+ and check the messages above.
pause
exit /b 1

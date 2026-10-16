@echo off
setlocal
cd /d "%~dp0"
if not defined VD_APP_NAME set "VD_APP_NAME=OrvantaVideoDownloader"
set "VD_ARTIFACT=dist\%VD_APP_NAME%.exe"
if not exist .venv\Scripts\python.exe py -3 -m venv .venv
if errorlevel 1 goto fail
.venv\Scripts\python.exe -m pip install -r requirements-release.lock
if errorlevel 1 goto fail
if not exist tools mkdir tools
REM --- aria2c (GPLv2: ship its license if you redistribute). Downloaded once into tools\ if not already on PATH.
set "ARIA="
for /f "delims=" %%I in ('where aria2c.exe 2^>nul') do if not defined ARIA set "ARIA=%%I"
if not defined ARIA if not exist tools\aria2c.exe powershell -NoProfile -Command "$ErrorActionPreference='Stop'; Invoke-WebRequest 'https://github.com/aria2/aria2/releases/download/release-1.37.0/aria2-1.37.0-win-64bit-build1.zip' -OutFile tools\aria2.zip; Expand-Archive tools\aria2.zip tools\a2 -Force; Copy-Item (Get-ChildItem tools\a2 -Recurse -Filter aria2c.exe | Select-Object -First 1).FullName tools\aria2c.exe; Remove-Item tools\aria2.zip,tools\a2 -Recurse -Force"
if not defined ARIA if exist tools\aria2c.exe set "ARIA=%CD%\tools\aria2c.exe"
set "ARIAARG="
if defined ARIA set "ARIAARG=--add-binary ""%ARIA%;."""
REM --- Compact QuickJS default; set VD_JS_RUNTIME=deno for the larger compatibility build.
if not exist tools\qjs.exe powershell -NoProfile -Command "$ErrorActionPreference='Stop'; Invoke-WebRequest 'https://github.com/quickjs-ng/quickjs/releases/download/v0.17.0/qjs-windows-x86_64.exe' -OutFile tools\qjs.exe"
if not exist tools\qjs.exe goto fail
REM Pin the tested runtime as well as Python dependencies; reject changed inputs.
powershell -NoProfile -Command "if ((Get-FileHash -LiteralPath tools\qjs.exe -Algorithm SHA256).Hash -ne '2AEABF0092C3262D6B2609824418F7DD7ED1F1DF939F73B2B15645230CAC0D77') { Write-Error 'QuickJS checksum does not match the tested v0.17.0 runtime'; exit 1 }"
if errorlevel 1 goto fail
set "JSBIN=tools\qjs.exe"
if /I "%VD_JS_RUNTIME%"=="deno" (
 .venv\Scripts\python.exe -m pip install deno
 if errorlevel 1 goto fail
 set "JSBIN=.venv\Scripts\deno.exe"
)
REM --- ffmpeg and ffprobe are both required for reliable audio conversion / metadata
set "FFMPEG="
set "FFPROBE="
for /f "delims=" %%I in ('where ffmpeg.exe 2^>nul') do if not defined FFMPEG set "FFMPEG=%%I"
for /f "delims=" %%I in ('where ffprobe.exe 2^>nul') do if not defined FFPROBE set "FFPROBE=%%I"
if exist tools\media\ffmpeg.exe set "FFMPEG=%CD%\tools\media\ffmpeg.exe"
if exist tools\media\ffprobe.exe set "FFPROBE=%CD%\tools\media\ffprobe.exe"
if not defined FFMPEG goto missing
if not defined FFPROBE goto missing
REM Keep the reviewed spec, icon, runtime fixes and dependency pruning.
set "VD_FFMPEG=%FFMPEG%"
set "VD_FFPROBE=%FFPROBE%"
set "VD_JSBIN=%JSBIN%"
set "VD_ARIA=%ARIA%"
.venv\Scripts\python.exe -m PyInstaller --noconfirm --clean VideoDownloaderDesktop.spec
if errorlevel 1 goto fail
.venv\Scripts\python.exe tools\verify_build.py "%VD_ARTIFACT%"
if errorlevel 1 goto fail
REM Opt in only with an existing trusted certificate; sign exact verified build before hashing.
if defined VD_SIGN_THUMBPRINT (
 powershell -NoProfile -File tools\sign_release.ps1 -Artifact "%VD_ARTIFACT%"
 if errorlevel 1 goto fail
)
.venv\Scripts\python.exe tools\release_manifest.py "%VD_ARTIFACT%"
if errorlevel 1 goto fail
echo Built %VD_ARTIFACT%
echo Manifest %VD_ARTIFACT%.manifest.json
exit /b 0
:missing
echo Install FFmpeg and ffprobe and add them to PATH before building.
:fail
pause
exit /b 1


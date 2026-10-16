[CmdletBinding()]
param([string]$CompilerPath='')
$ErrorActionPreference='Stop'
$releaseWorkspace=[IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
Set-Location -LiteralPath $releaseWorkspace
$python=Join-Path $releaseWorkspace '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $python)) {throw 'Prepare dependencies with build.bat first.'}
foreach ($required in @('tools\media\ffmpeg.exe','tools\media\ffprobe.exe','tools\qjs.exe')) {
    if (-not (Test-Path -LiteralPath $required)) {throw "Missing $required; prepare dependencies with build.bat first."}
}
$vendor=Join-Path $releaseWorkspace 'tools\vendor'
if (-not $CompilerPath) {
    $CompilerPath=Join-Path $vendor 'nsis-3.13\makensis.exe'
    if (-not (Test-Path -LiteralPath $CompilerPath)) {
        New-Item -ItemType Directory -Force -Path $vendor | Out-Null
        $archive=Join-Path $vendor 'nsis-3.13.zip'
        Invoke-WebRequest 'https://github.com/tauri-apps/binary-releases/releases/download/nsis-3.13/nsis-3.13.zip' -OutFile $archive
        if ((Get-FileHash -LiteralPath $archive -Algorithm SHA256).Hash -ne 'BA63DFFC4410EE89193E1CB5A41989991BD77C61068DA17E3156D136B7B0B3D8') {throw 'NSIS compiler checksum mismatch'}
        Expand-Archive -LiteralPath $archive -DestinationPath $vendor -Force
    }
}
New-Item -ItemType Directory -Force test-output,dist | Out-Null
$env:VD_PACKAGE_MODE='both';$env:VD_APP_NAME='OrvantaVideoDownloader'
try {
    & $python -m PyInstaller --noconfirm --distpath test-output/release VideoDownloaderDesktop.spec
    if ($LASTEXITCODE) {throw 'PyInstaller failed'}
} finally {Remove-Item Env:VD_PACKAGE_MODE;Remove-Item Env:VD_APP_NAME}
$payload=Join-Path $releaseWorkspace 'test-output\release\OrvantaVideoDownloader'
$portable=Join-Path $releaseWorkspace 'test-output\release\OrvantaVideoDownloader-Portable.exe'
foreach ($artifact in @($portable,(Join-Path $payload 'OrvantaVideoDownloader.exe'))) {
    & $python tools/verify_build.py $artifact
    if ($LASTEXITCODE) {throw "GUI startup failed: $artifact"}
    & $python tools/verify_embedded_sources.py $artifact
    if ($LASTEXITCODE) {throw "Embedded source mismatch: $artifact"}
}
$manifest=Join-Path $releaseWorkspace 'test-output\installer-uninstall.nsh'
& $python tools/create_uninstall_manifest.py $payload $manifest
if ($LASTEXITCODE) {throw 'Uninstall manifest failed'}
$setup=Join-Path $releaseWorkspace 'dist\OrvantaVideoDownloader-Setup.exe'
& $CompilerPath '/V2' "/DPAYLOAD=$payload" "/DPORTABLE=$portable" "/DOUTPUT=$setup" "/DUNINSTALL_INCLUDE=$manifest" (Join-Path $releaseWorkspace 'tools\installer.nsi')
if ($LASTEXITCODE) {throw 'Installer compilation failed'}
Copy-Item -LiteralPath $portable -Destination (Join-Path $releaseWorkspace 'dist\OrvantaVideoDownloader-Portable.exe') -Force
& $python tools/create_source_archive.py
if ($LASTEXITCODE) {throw 'Source ZIP failed'}
Write-Output 'Created unified Setup EXE (portable by default or installed) and source ZIP in dist.'

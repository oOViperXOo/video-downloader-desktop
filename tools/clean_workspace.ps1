[CmdletBinding(SupportsShouldProcess=$true)]
param()
$ErrorActionPreference='Stop'
$workspaceRoot=[IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..')).TrimEnd('\')
$workspacePrefix=$workspaceRoot+'\'
function Assert-WorkspacePath([string]$Path) {
    $resolved=[IO.Path]::GetFullPath($Path)
    if (-not $resolved.StartsWith($workspacePrefix,[StringComparison]::OrdinalIgnoreCase)) { throw "Refusing path outside workspace: $resolved" }
    return $resolved
}
$targets=@(Get-ChildItem -LiteralPath $workspaceRoot -Force | Where-Object {
    $_.PSIsContainer -and ($_.Name -in @('build','test-temp','test-output','.pytest_cache','__pycache__') -or $_.Name.StartsWith('.pytest-release-') -or $_.Name.StartsWith('.test-tmp-') -or $_.Name.StartsWith('.test-ui-'))
})
foreach ($area in @('tools','tests','browser-extension')) {
    $targets+=@(Get-ChildItem -LiteralPath (Join-Path $workspaceRoot $area) -Directory -Recurse -Force -Filter '__pycache__' | Where-Object {-not ($_.Attributes -band [IO.FileAttributes]::ReparsePoint)})
}
# Remove only verified duplicate FFmpeg downloads; tools/media stays intact.
$extracted=Join-Path $workspaceRoot 'tools\ffmpeg-essentials'
if (Test-Path -LiteralPath $extracted) {
    $same=$true
    foreach ($name in @('ffmpeg.exe','ffprobe.exe')) {
        $copies=@(Get-ChildItem -LiteralPath $extracted -Recurse -File -Filter $name)
        if ($copies.Count -ne 1 -or (Get-FileHash -LiteralPath $copies[0].FullName).Hash -ne (Get-FileHash -LiteralPath (Join-Path $workspaceRoot "tools\media\$name")).Hash) { $same=$false }
    }
    if ($same) {
        $targets+=Get-Item -LiteralPath $extracted
        $archive=Join-Path $workspaceRoot 'tools\ffmpeg-essentials.zip'
        if (Test-Path -LiteralPath $archive) { $targets+=Get-Item -LiteralPath $archive }
    }
}
$removed=0L;$count=0
foreach ($target in ($targets | Sort-Object FullName -Unique)) {
    $checked=Assert-WorkspacePath $target.FullName
    if (-not (Test-Path -LiteralPath $checked)) {continue}
    if ($target.Attributes -band [IO.FileAttributes]::ReparsePoint) {throw "Refusing linked target: $checked"}
    if ($target.PSIsContainer) {
        $links=@(Get-ChildItem -LiteralPath $checked -Recurse -Force -Attributes ReparsePoint)
        if ($links.Count) {throw "Refusing directory containing links: $checked"}
        $bytes=(Get-ChildItem -LiteralPath $checked -Recurse -Force -File | Measure-Object Length -Sum).Sum
    } else {$bytes=$target.Length}
    if ($PSCmdlet.ShouldProcess($checked,'Remove generated artifact')) {
        Remove-Item -LiteralPath $checked -Recurse -Force
        $removed+=[long]$bytes;$count++
    }
}
[pscustomobject]@{RemovedTargets=$count;ReclaimedBytes=$removed;ReclaimedGiB=[math]::Round($removed/1GB,3)} | ConvertTo-Json -Compress

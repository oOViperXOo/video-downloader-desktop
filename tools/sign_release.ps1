param(
    [Parameter(Mandatory=$true)][string]$Artifact,
    [string]$Thumbprint = $env:VD_SIGN_THUMBPRINT,
    [string]$TimestampUrl = $env:VD_TIMESTAMP_URL,
    [string]$SignTool = $env:VD_SIGNTOOL
)
$ErrorActionPreference = 'Stop'
$target = (Resolve-Path -LiteralPath $Artifact).Path
if ([IO.Path]::GetExtension($target) -ine '.exe' -or (Get-Item -LiteralPath $target).Length -eq 0) { throw 'A nonempty exact .exe artifact is required.' }
if ($Thumbprint -notmatch '^[0-9a-fA-F]{40}$') { throw 'Configure VD_SIGN_THUMBPRINT with the trusted code-signing certificate thumbprint.' }
$timestamp = $null
if (-not [Uri]::TryCreate($TimestampUrl, [UriKind]::Absolute, [ref]$timestamp) -or $timestamp.Scheme -ne 'https' -or $timestamp.UserInfo -or $timestamp.Fragment) { throw 'Configure VD_TIMESTAMP_URL with the provider HTTPS RFC3161 timestamp URL.' }
if (-not $SignTool) { $SignTool = (Get-Command signtool.exe -ErrorAction Stop).Source }
& $SignTool sign /sha1 $Thumbprint /fd SHA256 /tr $TimestampUrl /td SHA256 $target
if ($LASTEXITCODE -ne 0) { throw 'SignTool signing failed.' }
& $SignTool verify /pa /all /v $target
if ($LASTEXITCODE -ne 0) { throw 'SignTool signature verification failed.' }
$signature = Get-AuthenticodeSignature -LiteralPath $target
if ($signature.Status -ne 'Valid' -or $signature.SignerCertificate.Thumbprint -ine $Thumbprint -or -not $signature.TimeStamperCertificate) { throw 'Expected trusted timestamped Authenticode signature was not verified.' }
Write-Output "Verified trusted Authenticode signature: $target"

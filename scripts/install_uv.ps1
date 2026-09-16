. "$PSScriptRoot\_common_installer.ps1"
Write-Step "Install uv"
$uv = Get-Command uv -ErrorAction SilentlyContinue
if (-not $uv) {
    $link = WinGet-Link "uv.exe"
    if ($link) { Add-UserPath (Split-Path -Parent $link); $uv = Get-Item $link }
}
if (-not $uv) {
    $winget = Ensure-Winget
    & $winget install -e --id astral-sh.uv --accept-source-agreements --accept-package-agreements
    if ($LASTEXITCODE -ne 0) { throw "Could not install uv through WinGet." }
    $link = WinGet-Link "uv.exe"
    if ($link) { Add-UserPath (Split-Path -Parent $link); $uv = Get-Item $link }
    else { $uv = Get-Command uv -ErrorAction SilentlyContinue }
}
if (-not $uv) { throw "uv installation completed but uv could not be verified." }
$path = if ($uv.Source) { $uv.Source } else { $uv.FullName }
& $path --version
if ($LASTEXITCODE -ne 0) { throw "uv failed its version check." }
Refresh-EnvHint

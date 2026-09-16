. "$PSScriptRoot\_common_installer.ps1"
Write-Step "Install PowerShell 7"
$pwsh = Get-Command pwsh -ErrorAction SilentlyContinue
$pwshPath = "C:\Program Files\PowerShell\7\pwsh.exe"
if (-not $pwsh -and (Test-Path $pwshPath)) { Add-UserPath (Split-Path -Parent $pwshPath); $pwsh = Get-Item $pwshPath }
if (-not $pwsh) {
    $winget = Ensure-Winget
    & $winget install -e --id Microsoft.PowerShell --accept-source-agreements --accept-package-agreements
    if ($LASTEXITCODE -ne 0) { throw "Could not install PowerShell 7 through WinGet." }
    if (Test-Path $pwshPath) { Add-UserPath (Split-Path -Parent $pwshPath); $pwsh = Get-Item $pwshPath }
    else { $pwsh = Get-Command pwsh -ErrorAction SilentlyContinue }
}
if (-not $pwsh) { throw "PowerShell 7 installation completed but pwsh could not be verified." }
$path = if ($pwsh.Source) { $pwsh.Source } else { $pwsh.FullName }
& $path -NoProfile -Command '$PSVersionTable.PSVersion.ToString()'
if ($LASTEXITCODE -ne 0) { throw "PowerShell 7 failed its version check." }
Refresh-EnvHint

. "$PSScriptRoot\_common_installer.ps1"
Write-Step "Install Git"
$git = Get-Command git -ErrorAction SilentlyContinue
$gitPath = "C:\Program Files\Git\cmd\git.exe"
if (-not $git -and (Test-Path $gitPath)) { Add-UserPath (Split-Path -Parent $gitPath); $git = Get-Item $gitPath }
if (-not $git) {
    $winget = Ensure-Winget
    & $winget install -e --id Git.Git --accept-source-agreements --accept-package-agreements
    if ($LASTEXITCODE -ne 0) { throw "Could not install Git through WinGet." }
    if (Test-Path $gitPath) { Add-UserPath (Split-Path -Parent $gitPath); $git = Get-Item $gitPath }
    else { $git = Get-Command git -ErrorAction SilentlyContinue }
}
if (-not $git) { throw "Git installation completed but git could not be verified." }
$path = if ($git.Source) { $git.Source } else { $git.FullName }
& $path --version
if ($LASTEXITCODE -ne 0) { throw "Git failed its version check." }
Refresh-EnvHint

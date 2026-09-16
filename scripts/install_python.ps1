. "$PSScriptRoot\_common_installer.ps1"
Write-Step "Install Python"
$working = Find-WorkingPython
if (-not $working) {
    $winget = Ensure-Winget
    $ids = @("Python.Python.3.14", "Python.Python.3.13", "Python.Python.3.12", "Python.Python.3.11")
    $installed = $false
    foreach ($id in $ids) {
        Write-Host "Trying to install: $id"
        & $winget install -e --id $id --accept-source-agreements --accept-package-agreements
        if ($LASTEXITCODE -eq 0) { $installed = $true; break }
    }
    if (-not $installed) { throw "Could not install Python through WinGet." }
    $working = Find-WorkingPython
}
if (-not $working) { throw "Python installation completed but no working interpreter could be verified." }
Write-Host "Python verified: $($working.Path)"
& $working.Path @($working.Args) --version
if ($LASTEXITCODE -ne 0) { throw "Python was found but failed the version check." }
if ($working.RealExe) {
    $pythonDir = Split-Path -Parent $working.RealExe
    Add-UserPath $pythonDir
    $scriptsDir = Join-Path $pythonDir "Scripts"
    if (Test-Path $scriptsDir) { Add-UserPath $scriptsDir }
}
Refresh-EnvHint

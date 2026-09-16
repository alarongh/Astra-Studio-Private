. "$PSScriptRoot\_common_installer.ps1"
Write-Step "Install Godot"
$godot = Get-Command godot -ErrorAction SilentlyContinue
if (-not $godot) {
    $link = WinGet-Link "godot.exe"
    if ($link) { Add-UserPath (Split-Path -Parent $link); $godot = Get-Item $link }
}
if (-not $godot) {
    $winget = Ensure-Winget
    & $winget install -e --id GodotEngine.GodotEngine --accept-source-agreements --accept-package-agreements
    if ($LASTEXITCODE -ne 0) { throw "Could not install Godot through WinGet." }
    $link = WinGet-Link "godot.exe"
    if ($link) { Add-UserPath (Split-Path -Parent $link); $godot = Get-Item $link }
    else { $godot = Get-Command godot -ErrorAction SilentlyContinue }
}
if (-not $godot) { throw "Godot installation completed but its CLI alias could not be verified." }
$path = if ($godot.Source) { $godot.Source } else { $godot.FullName }
& $path --version
if ($LASTEXITCODE -ne 0) { throw "Godot failed its version check." }
Refresh-EnvHint

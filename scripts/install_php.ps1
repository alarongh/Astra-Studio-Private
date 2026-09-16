. "$PSScriptRoot\_common_installer.ps1"
Write-Step "Install PHP 8.4"
$php = Get-Command php -ErrorAction SilentlyContinue
if (-not $php) {
    $link = WinGet-Link "php.exe"
    if ($link) { Add-UserPath (Split-Path -Parent $link); $php = Get-Item $link }
}
if (-not $php) {
    $winget = Ensure-Winget
    & $winget install -e --id PHP.PHP.8.4 --accept-source-agreements --accept-package-agreements
    if ($LASTEXITCODE -ne 0) { throw "Could not install PHP 8.4 through WinGet." }
    $link = WinGet-Link "php.exe"
    if ($link) { Add-UserPath (Split-Path -Parent $link); $php = Get-Item $link }
    else { $php = Get-Command php -ErrorAction SilentlyContinue }
}
if (-not $php) { throw "PHP installation completed but php could not be verified." }
$path = if ($php.Source) { $php.Source } else { $php.FullName }
& $path --version | Select-Object -First 1
if ($LASTEXITCODE -ne 0) { throw "PHP failed its version check." }
Refresh-EnvHint

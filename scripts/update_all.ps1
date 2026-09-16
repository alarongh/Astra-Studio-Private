. "$PSScriptRoot\_common_installer.ps1"
Write-Step "Update installed StaffedUp toolchain"
$winget = Ensure-Winget
function Test-WingetInstalled([string]$id) {
    $text = & $winget list -e --id $id --accept-source-agreements 2>&1 | Out-String
    return $text -match [regex]::Escape($id)
}
$ids = @(
    "Python.Python.3.14",
    "astral-sh.uv",
    "OpenJS.NodeJS.LTS",
    "Git.Git",
    "Microsoft.PowerShell",
    "MSYS2.MSYS2",
    "EclipseAdoptium.Temurin.21.JDK",
    "GodotEngine.GodotEngine",
    "PHP.PHP.8.4"
)
foreach ($id in $ids) {
    if (-not (Test-WingetInstalled $id)) {
        Write-Host "Skip (not installed): $id"
        continue
    }
    Write-Step "Update $id"
    & $winget upgrade -e --id $id --accept-source-agreements --accept-package-agreements
    if ($LASTEXITCODE -ne 0) { Write-Warning "WinGet could not update $id (it may already be current)." }
}
$npm = Get-Command npm -ErrorAction SilentlyContinue
if ($npm) {
    Write-Step "Update TypeScript tooling"
    & $npm.Source install --global typescript@latest tsx@latest
    if ($LASTEXITCODE -ne 0) { Write-Warning "npm could not update TypeScript/tsx." }
}
$bash = "C:\msys64\usr\bin\bash.exe"
if (Test-Path $bash) {
    Write-Step "Update MSYS2/C++ packages"
    & $bash -lc "pacman -Syu --noconfirm"
    if ($LASTEXITCODE -ne 0) { Write-Warning "pacman update returned a non-zero exit code." }
    & $bash -lc "pacman -S --needed --noconfirm mingw-w64-ucrt-x86_64-gcc"
    if ($LASTEXITCODE -ne 0) { Write-Warning "g++ package refresh returned a non-zero exit code." }
    Add-UserPath "C:\msys64\ucrt64\bin"
}
Refresh-EnvHint

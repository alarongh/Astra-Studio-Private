. "$PSScriptRoot\_common_installer.ps1"
Write-Step "Install C++ toolchain"
$gpp = Get-Command g++ -ErrorAction SilentlyContinue
$gppPath = "C:\msys64\ucrt64\bin\g++.exe"
if ($gpp) {
    & $gpp.Source --version
    if ($LASTEXITCODE -ne 0) { $gpp = $null }
}
if (-not $gpp -and -not (Test-Path $gppPath)) {
    $bash = "C:\msys64\usr\bin\bash.exe"
    if (-not (Test-Path $bash)) {
        $winget = Ensure-Winget
        & $winget install -e --id MSYS2.MSYS2 --accept-source-agreements --accept-package-agreements
        if ($LASTEXITCODE -ne 0 -and -not (Test-Path $bash)) { throw "Could not install MSYS2 through WinGet." }
    }
    if (-not (Test-Path $bash)) { throw "MSYS2 was not found in C:\msys64." }
    Write-Step "Update MSYS2"
    & $bash -lc "pacman -Syuu --noconfirm"
    if ($LASTEXITCODE -ne 0) { throw "MSYS2 update failed." }
    Write-Step "Install g++ UCRT64"
    & $bash -lc "pacman -S --needed --noconfirm mingw-w64-ucrt-x86_64-gcc"
    if ($LASTEXITCODE -ne 0) { throw "g++ installation through pacman failed." }
}
if (Test-Path $gppPath) {
    Add-UserPath "C:\msys64\ucrt64\bin"
    & $gppPath --version
    if ($LASTEXITCODE -ne 0) { throw "g++ exists but failed its version check." }
} elseif ($gpp) {
    & $gpp.Source --version
    if ($LASTEXITCODE -ne 0) { throw "Detected g++ failed its version check." }
} else { throw "C++ installation completed but g++ could not be verified." }
Refresh-EnvHint

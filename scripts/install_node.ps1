. "$PSScriptRoot\_common_installer.ps1"
Write-Step "Install Node.js LTS"
$node = Get-Command node -ErrorAction SilentlyContinue
$npm = Get-Command npm -ErrorAction SilentlyContinue
if (-not $node -or -not $npm) {
    $nodeDir = "C:\Program Files\nodejs"
    if (Test-Path (Join-Path $nodeDir "node.exe")) {
        Add-UserPath $nodeDir
        $node = Get-Item (Join-Path $nodeDir "node.exe")
        if (Test-Path (Join-Path $nodeDir "npm.cmd")) { $npm = Get-Item (Join-Path $nodeDir "npm.cmd") }
    }
}
if (-not $node -or -not $npm) {
    $winget = Ensure-Winget
    & $winget install -e --id OpenJS.NodeJS.LTS --accept-source-agreements --accept-package-agreements
    if ($LASTEXITCODE -ne 0) { throw "Could not install Node.js LTS through WinGet." }
    $nodeDir = "C:\Program Files\nodejs"
    if (Test-Path $nodeDir) { Add-UserPath $nodeDir }
    $node = Get-Command node -ErrorAction SilentlyContinue
    $npm = Get-Command npm -ErrorAction SilentlyContinue
    if (-not $node -and (Test-Path (Join-Path $nodeDir "node.exe"))) { $node = Get-Item (Join-Path $nodeDir "node.exe") }
    if (-not $npm -and (Test-Path (Join-Path $nodeDir "npm.cmd"))) { $npm = Get-Item (Join-Path $nodeDir "npm.cmd") }
}
if (-not $node -or -not $npm) { throw "Node.js/npm could not be verified after installation." }
$nodePath = if ($node.Source) { $node.Source } else { $node.FullName }
$npmPath = if ($npm.Source) { $npm.Source } else { $npm.FullName }
& $nodePath --version
if ($LASTEXITCODE -ne 0) { throw "Node.js failed its version check." }
Write-Step "Install TypeScript tooling"
& $npmPath install --global typescript tsx
if ($LASTEXITCODE -ne 0) { throw "Could not install TypeScript/tsx through npm." }
if ($env:APPDATA) { Add-UserPath (Join-Path $env:APPDATA "npm") }
Refresh-EnvHint

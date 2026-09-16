$ErrorActionPreference = "Stop"
try { [Console]::OutputEncoding = [System.Text.Encoding]::UTF8 } catch {}
function Write-Step($text) { Write-Host "`n=== $text ===" }
function Invoke-NativeVersionProbe([string]$FilePath, [string[]]$Arguments = @("--version")) {
    if ([string]::IsNullOrWhiteSpace($FilePath) -or -not (Test-Path $FilePath -ErrorAction SilentlyContinue)) { return $false }
    foreach ($argument in $Arguments) {
        if ([string]$argument -notmatch '^[A-Za-z0-9._:/=+\-]+$') { throw "Unsafe native version-probe argument: $argument" }
    }
    $startInfo = New-Object System.Diagnostics.ProcessStartInfo
    $startInfo.FileName = $FilePath
    $startInfo.Arguments = ($Arguments -join " ")
    $startInfo.UseShellExecute = $false
    $startInfo.CreateNoWindow = $true
    $startInfo.RedirectStandardOutput = $true
    $startInfo.RedirectStandardError = $true
    $process = New-Object System.Diagnostics.Process
    $process.StartInfo = $startInfo
    try {
        if (-not $process.Start()) { return $false }
        $stdout = $process.StandardOutput.ReadToEnd()
        $stderr = $process.StandardError.ReadToEnd()
        $process.WaitForExit()
        foreach ($text in @($stdout, $stderr)) {
            if (-not [string]::IsNullOrWhiteSpace($text)) { Write-Host $text.TrimEnd() }
        }
        return $process.ExitCode -eq 0
    } finally {
        $process.Dispose()
    }
}
function Find-JavaRuntime {
    $javaHomeCandidates = @()
    foreach ($value in @($env:JAVA_HOME, $env:JDK_HOME)) {
        if (-not [string]::IsNullOrWhiteSpace([string]$value)) { $javaHomeCandidates += [string]$value }
    }
    $javac = Get-Command javac -ErrorAction SilentlyContinue
    if ($javac -and $javac.Source) { $javaHomeCandidates += Split-Path -Parent (Split-Path -Parent $javac.Source) }
    foreach ($root in @($env:ProgramFiles, ${env:ProgramFiles(x86)}, (Join-Path $env:LOCALAPPDATA "Programs"))) {
        if ([string]::IsNullOrWhiteSpace([string]$root) -or -not (Test-Path $root)) { continue }
        foreach ($vendor in @("Eclipse Adoptium", "Java", "Microsoft", "Amazon Corretto", "BellSoft", "Azul Systems")) {
            $folder = Join-Path $root $vendor
            if (Test-Path $folder) {
                $javaHomeCandidates += Get-ChildItem $folder -Directory -ErrorAction SilentlyContinue | Sort-Object LastWriteTime -Descending | ForEach-Object { $_.FullName }
            }
        }
    }
    foreach ($javaHomePath in ($javaHomeCandidates | Select-Object -Unique)) {
        $javacPath = Join-Path $javaHomePath "bin\javac.exe"
        $javaPath = Join-Path $javaHomePath "bin\java.exe"
        if ((Test-Path $javacPath) -and (Test-Path $javaPath)) {
            return @{ Home = $javaHomePath; Javac = $javacPath; Java = $javaPath }
        }
    }
    return $null
}
function Ensure-Winget {
    $winget = Get-Command winget -ErrorAction SilentlyContinue
    if (-not $winget) { throw "WinGet was not found. Install or update App Installer from Microsoft Store and try again." }
    & $winget.Source --version
    if ($LASTEXITCODE -ne 0) { throw "WinGet was found but could not be started correctly." }
    return $winget.Source
}
function Add-UserPath($dir) {
    if (-not (Test-Path $dir)) { return }
    $dir = (Resolve-Path $dir).Path
    $userPath = [Environment]::GetEnvironmentVariable("Path", "User")
    if ([string]::IsNullOrWhiteSpace($userPath)) { $userPath = "" }
    $parts = $userPath -split ';' | Where-Object { $_ -and $_.Trim() }
    if ($parts -notcontains $dir) {
        [Environment]::SetEnvironmentVariable("Path", (($parts + $dir) -join ';'), "User")
        Write-Host "Added to user PATH: $dir"
    } else {
        Write-Host "PATH already contains: $dir"
    }
    if (($env:Path -split ';') -notcontains $dir) { $env:Path = "$dir;$env:Path" }
}
function Test-PythonExecutable([string]$exe, [string[]]$prefixArgs = @()) {
    if ([string]::IsNullOrWhiteSpace($exe) -or -not (Test-Path $exe -ErrorAction SilentlyContinue)) { return $false }
    & $exe @prefixArgs -c "import sys; print(sys.executable); print(40 + 2)" 2>$null | Out-Null
    return $LASTEXITCODE -eq 0
}
function Find-WorkingPython {
    $launcher = Get-Command py -ErrorAction SilentlyContinue
    if ($launcher) {
        & $launcher.Source -3 -c "import sys; print(40 + 2)" 2>$null | Out-Null
        if ($LASTEXITCODE -eq 0) { return @{ Path = $launcher.Source; Args = @("-3"); RealExe = $null } }
    }
    $python = Get-Command python -ErrorAction SilentlyContinue
    if ($python) {
        & $python.Source -c "import sys; print(40 + 2)" 2>$null | Out-Null
        if ($LASTEXITCODE -eq 0) { return @{ Path = $python.Source; Args = @(); RealExe = $python.Source } }
    }
    $candidates = @()
    $localPython = Join-Path $env:LOCALAPPDATA "Programs\Python"
    if (Test-Path $localPython) {
        $candidates += Get-ChildItem $localPython -Directory -Filter "Python*" -ErrorAction SilentlyContinue | Sort-Object LastWriteTime -Descending | ForEach-Object { Join-Path $_.FullName "python.exe" }
    }
    if (Test-Path "C:\Program Files") {
        $candidates += Get-ChildItem "C:\Program Files" -Directory -Filter "Python*" -ErrorAction SilentlyContinue | Sort-Object LastWriteTime -Descending | ForEach-Object { Join-Path $_.FullName "python.exe" }
    }
    foreach ($candidate in $candidates) {
        if (Test-PythonExecutable $candidate) { return @{ Path = $candidate; Args = @(); RealExe = $candidate } }
    }
    return $null
}
function WinGet-Link($name) {
    $links = Join-Path $env:LOCALAPPDATA "Microsoft\WinGet\Links"
    $candidate = Join-Path $links $name
    if (Test-Path $candidate) { return $candidate }
    return $null
}
function Refresh-EnvHint { Write-Host "`nDone. Astra refreshes common runtime paths itself; if Windows has not exposed a new tool yet, restart Astra Studio." }

. "$PSScriptRoot\_common_installer.ps1"
Write-Step "Install Java JDK"
$pathJavac = Get-Command javac -ErrorAction SilentlyContinue
$runtime = Find-JavaRuntime
if ($pathJavac) { Write-Host "javac on PATH: $($pathJavac.Source)" }
$adoptium = "C:\Program Files\Eclipse Adoptium"
$jdk = $null
if (Test-Path $adoptium) {
    $jdk = Get-ChildItem $adoptium -Directory -Filter "jdk-*" -ErrorAction SilentlyContinue | Sort-Object LastWriteTime -Descending | Select-Object -First 1
}
if (-not $runtime -and -not $jdk) {
    $winget = Ensure-Winget
    & $winget install -e --id EclipseAdoptium.Temurin.21.JDK --accept-source-agreements --accept-package-agreements
    if ($LASTEXITCODE -ne 0) { throw "Could not install Java JDK through WinGet." }
    if (Test-Path $adoptium) {
        $jdk = Get-ChildItem $adoptium -Directory -Filter "jdk-*" -ErrorAction SilentlyContinue | Sort-Object LastWriteTime -Descending | Select-Object -First 1
    }
}
$verified = $false
if ($jdk) {
    [Environment]::SetEnvironmentVariable("JAVA_HOME", $jdk.FullName, "User")
    Add-UserPath (Join-Path $jdk.FullName "bin")
    $javacPath = Join-Path $jdk.FullName "bin\javac.exe"
    $javaPath = Join-Path $jdk.FullName "bin\java.exe"
    if ((Test-Path $javacPath) -and (Test-Path $javaPath)) {
        $javacOk = Invoke-NativeVersionProbe $javacPath @("-version")
        $javaOk = Invoke-NativeVersionProbe $javaPath @("-version")
        $verified = $javacOk -and $javaOk
    }
}
if (-not $verified) {
    $runtime = Find-JavaRuntime
    if ($runtime) {
        [Environment]::SetEnvironmentVariable("JAVA_HOME", $runtime.Home, "User")
        Add-UserPath (Join-Path $runtime.Home "bin")
        $verified = (Invoke-NativeVersionProbe $runtime.Javac @("-version")) -and (Invoke-NativeVersionProbe $runtime.Java @("-version"))
    }
}
if (-not $verified) { throw "Java installation completed but javac/java could not be verified." }
Refresh-EnvHint

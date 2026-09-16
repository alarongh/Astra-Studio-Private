param(
    [ValidateSet("classic", "angel404", "legacy")]
    [string]$IconStyle = "classic",
    [string]$DesktopPathOverride = "",
    [string]$AppDirOverride = ""
)

$ErrorActionPreference = "Stop"
try { [Console]::OutputEncoding = [System.Text.Encoding]::UTF8 } catch {}
$appDir = if ([string]::IsNullOrWhiteSpace($AppDirOverride)) { Split-Path -Parent $PSScriptRoot } else { [IO.Path]::GetFullPath($AppDirOverride) }
$desktopCandidates = @()
if (-not [string]::IsNullOrWhiteSpace($DesktopPathOverride)) { $desktopCandidates += [IO.Path]::GetFullPath($DesktopPathOverride) }
$desktopCandidates += [Environment]::GetFolderPath([Environment+SpecialFolder]::DesktopDirectory)
$registryDesktop = (Get-ItemProperty -LiteralPath "HKCU:\Software\Microsoft\Windows\CurrentVersion\Explorer\User Shell Folders" -Name Desktop -ErrorAction SilentlyContinue).Desktop
if (-not [string]::IsNullOrWhiteSpace($registryDesktop)) { $desktopCandidates += [Environment]::ExpandEnvironmentVariables($registryDesktop) }
if (-not [string]::IsNullOrWhiteSpace($env:OneDrive)) {
    $desktopCandidates += Join-Path $env:OneDrive "Рабочий стол"
    $desktopCandidates += Join-Path $env:OneDrive "Desktop"
}
if (-not [string]::IsNullOrWhiteSpace($env:USERPROFILE)) {
    $desktopCandidates += Join-Path $env:USERPROFILE "Рабочий стол"
    $desktopCandidates += Join-Path $env:USERPROFILE "Desktop"
}
$desktop = $desktopCandidates | Where-Object { -not [string]::IsNullOrWhiteSpace($_) -and (Test-Path -LiteralPath $_) } | Select-Object -First 1
if ([string]::IsNullOrWhiteSpace($desktop)) { throw "Desktop folder could not be resolved." }
$linkPath = Join-Path $desktop "Astra Studio.lnk"
$exeCandidate = Join-Path $appDir "Astra Studio.exe"
$distOneDirCandidate = Join-Path $appDir "dist\Astra Studio\Astra Studio.exe"
$distOneFileCandidate = Join-Path $appDir "dist\Astra Studio.exe"
$vbsCandidate = Join-Path $appDir "run_astra.vbs"
$batCandidate = Join-Path $appDir "run_astra.bat"
$runCandidate = Join-Path $appDir "run.bat"
if (Test-Path -LiteralPath $exeCandidate) { $target = $exeCandidate }
elseif (Test-Path -LiteralPath $distOneDirCandidate) { $target = $distOneDirCandidate }
elseif (Test-Path -LiteralPath $distOneFileCandidate) { $target = $distOneFileCandidate }
elseif (Test-Path -LiteralPath $vbsCandidate) { $target = $vbsCandidate }
elseif (Test-Path -LiteralPath $batCandidate) { $target = $batCandidate }
elseif (Test-Path -LiteralPath $runCandidate) { $target = $runCandidate }
else { throw "No Astra Studio launcher or executable was found in $appDir." }
$wsh = New-Object -ComObject WScript.Shell
$shortcut = $wsh.CreateShortcut($linkPath)
$shortcut.TargetPath = $target
$shortcut.WorkingDirectory = Split-Path -Parent $target
$iconNames = @{ classic = "astra.ico"; angel404 = "astra_angel404.ico"; legacy = "legacy_astra.ico" }
$iconName = $iconNames[$IconStyle]
$iconCandidates = @(
    (Join-Path $appDir "assets\$iconName"),
    (Join-Path $appDir "_internal\assets\$iconName")
)
$icon = $iconCandidates | Where-Object { Test-Path -LiteralPath $_ } | Select-Object -First 1
if ($icon) { $shortcut.IconLocation = $icon } else { $shortcut.IconLocation = $target }
$shortcut.Description = "Astra Studio - code editor"
$shortcut.Save()
if (-not (Test-Path -LiteralPath $linkPath)) { throw "Shortcut file was not created." }
Write-Host "Shortcut created: $linkPath"
Write-Host "Icon style: $IconStyle"

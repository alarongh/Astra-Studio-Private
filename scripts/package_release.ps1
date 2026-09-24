param(
    [string]$Version = "3.20",
    [switch]$SourceOnly
)

$ErrorActionPreference = "Stop"
$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$releaseBase = Split-Path $projectRoot -Parent
$outputDirectory = Join-Path $releaseBase "release_output"
$versionSlug = $Version.Replace(".", "_")
$sourceFolderName = "Astra_Studio_Release_${versionSlug}_FINAL_SOURCE"
$stagingDirectory = Join-Path $outputDirectory $sourceFolderName
$portableZip = Join-Path $outputDirectory "Astra_Studio_Release_${versionSlug}.zip"
$sourceZip = Join-Path $outputDirectory "${sourceFolderName}.zip"
$manifestPath = Join-Path $projectRoot "RELEASE_MANIFEST_${versionSlug}.sha256"

function Get-AstraRelativePath([string]$BasePath, [string]$TargetPath) {
    $baseUri = New-Object System.Uri(([IO.Path]::GetFullPath($BasePath).TrimEnd("\") + "\"))
    $targetUri = New-Object System.Uri([IO.Path]::GetFullPath($TargetPath))
    return [Uri]::UnescapeDataString($baseUri.MakeRelativeUri($targetUri).ToString()).Replace("/", "\")
}

New-Item -ItemType Directory -Force -Path $outputDirectory | Out-Null
$outputFull = [IO.Path]::GetFullPath($outputDirectory).TrimEnd("\")
$stagingFull = [IO.Path]::GetFullPath($stagingDirectory)
if (-not $stagingFull.StartsWith($outputFull + "\", [StringComparison]::OrdinalIgnoreCase)) {
    throw "Unsafe release staging path: $stagingFull"
}
if (Test-Path -LiteralPath $stagingFull) {
    Remove-Item -LiteralPath $stagingFull -Recurse -Force
}
New-Item -ItemType Directory -Path $stagingFull | Out-Null

$excludedDirectories = '\\(?:\.venv|\.pytest_cache|\.pytest-tmp|__pycache__|build|dist)(?:\\|$)'
$allSourceFiles = Get-ChildItem -LiteralPath $projectRoot -Recurse -File -ErrorAction SilentlyContinue |
    Where-Object { $_.FullName -notmatch $excludedDirectories -and $_.Extension -ne ".pyc" }
$manifestFiles = $allSourceFiles | Where-Object { $_.FullName -ne $manifestPath }
$manifestLines = foreach ($file in ($manifestFiles | Sort-Object FullName)) {
    $relative = (Get-AstraRelativePath $projectRoot $file.FullName).Replace("\", "/")
    $hash = (Get-FileHash -Algorithm SHA256 -LiteralPath $file.FullName).Hash.ToLowerInvariant()
    "$hash *$relative"
}
Set-Content -LiteralPath $manifestPath -Value $manifestLines -Encoding utf8

# Include the newly regenerated manifest in the source payload.
$allSourceFiles = Get-ChildItem -LiteralPath $projectRoot -Recurse -File -ErrorAction SilentlyContinue |
    Where-Object { $_.FullName -notmatch $excludedDirectories -and $_.Extension -ne ".pyc" }
foreach ($file in $allSourceFiles) {
    $relative = Get-AstraRelativePath $projectRoot $file.FullName
    $destination = Join-Path $stagingFull $relative
    $destinationDirectory = Split-Path $destination -Parent
    if (-not (Test-Path -LiteralPath $destinationDirectory)) {
        New-Item -ItemType Directory -Path $destinationDirectory | Out-Null
    }
    Copy-Item -LiteralPath $file.FullName -Destination $destination
}

$portableDirectory = Join-Path $projectRoot "dist\Astra Studio"
if (-not (Test-Path -LiteralPath (Join-Path $portableDirectory "Astra Studio.exe"))) {
    throw "Portable executable is missing. Build PyInstaller output first."
}
if (-not $SourceOnly) {
    Compress-Archive -LiteralPath $portableDirectory -DestinationPath $portableZip -CompressionLevel Optimal -Force
} elseif (-not (Test-Path -LiteralPath $portableZip -PathType Leaf)) {
    throw "SourceOnly requires an existing portable ZIP: $portableZip"
}
Compress-Archive -LiteralPath $stagingFull -DestinationPath $sourceZip -CompressionLevel Optimal -Force

foreach ($document in @("TEST_REPORT_RELEASE_3_20.md", "PORTABLE_README.md", "UPDATE_DISTRIBUTION.md")) {
    Copy-Item -LiteralPath (Join-Path $projectRoot $document) -Destination $outputDirectory -Force
}
$checksumLines = foreach ($artifact in @($portableZip, $sourceZip)) {
    $hash = (Get-FileHash -Algorithm SHA256 -LiteralPath $artifact).Hash.ToLowerInvariant()
    "$hash  $([IO.Path]::GetFileName($artifact))"
}
Set-Content -LiteralPath (Join-Path $outputDirectory "SHA256SUMS.txt") -Value $checksumLines -Encoding ascii

Write-Host "SOURCE_FILES=$($allSourceFiles.Count)"
Get-Item -LiteralPath $portableZip, $sourceZip | Select-Object Name, Length, LastWriteTime
Get-Content -LiteralPath (Join-Path $outputDirectory "SHA256SUMS.txt")

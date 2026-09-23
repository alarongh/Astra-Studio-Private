$ErrorActionPreference = "Stop"
$scripts = @(
    "install_python.ps1",
    "install_uv.ps1",
    "install_node.ps1",
    "install_cpp.ps1",
    "install_java.ps1"
)
try {
    foreach ($script in $scripts) {
        & (Join-Path $PSScriptRoot $script)
    }
} catch {
    Write-Error "Core StaffedUp toolchain installation stopped: $($_.Exception.Message)"
    exit 1
}
Write-Host "`nAstra language toolchain is ready: Java, Python, C++, JavaScript, HTML and CSS."
exit 0

$ErrorActionPreference = "Stop"
$scripts = @(
    "install_python.ps1",
    "install_uv.ps1",
    "install_node.ps1",
    "install_git.ps1",
    "install_powershell.ps1",
    "install_cpp.ps1",
    "install_java.ps1",
    "create_desktop_shortcut.ps1"
)
try {
    foreach ($script in $scripts) {
        & (Join-Path $PSScriptRoot $script)
    }
} catch {
    Write-Error "Core StaffedUp toolchain installation stopped: $($_.Exception.Message)"
    exit 1
}
Write-Host "`nCore StaffedUp toolchain is ready. Godot and PHP are optional per-role installs."
exit 0

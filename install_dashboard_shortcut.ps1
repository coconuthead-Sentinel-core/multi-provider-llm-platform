# install_dashboard_shortcut.ps1
# Drops a Desktop shortcut named "Sentinel Forge Dashboard" that runs
# launch_sentinel_forge.vbs — starts the FastAPI backend (hidden) if
# needed and opens the dashboard in the default browser.
#
# Run:
#   powershell -ExecutionPolicy Bypass -File install_dashboard_shortcut.ps1

$ErrorActionPreference = "Stop"

$root        = (Resolve-Path "$PSScriptRoot").Path
$vbsPath     = Join-Path $root "launch_sentinel_forge.vbs"
$desktop     = [Environment]::GetFolderPath("Desktop")
$lnkPath     = Join-Path $desktop "Sentinel Forge Dashboard.lnk"
$iconCandidate = Join-Path $root "dashboard.ico"

if (-not (Test-Path $vbsPath)) {
    throw "launch_sentinel_forge.vbs not found next to this script: $vbsPath"
}

$wsh = New-Object -ComObject WScript.Shell
$lnk = $wsh.CreateShortcut($lnkPath)
$lnk.TargetPath       = "wscript.exe"
$lnk.Arguments        = "`"$vbsPath`""
$lnk.WorkingDirectory = $root
$lnk.Description      = "Start Sentinel Forge backend and open dashboard"
$lnk.WindowStyle      = 7  # minimized — wscript itself shows nothing
if (Test-Path $iconCandidate) {
    $lnk.IconLocation = $iconCandidate
} else {
    $lnk.IconLocation = "shell32.dll,13"  # network/server icon
}
$lnk.Save()

Write-Output "Created Desktop shortcut:"
Write-Output "  $lnkPath"
Write-Output ""
Write-Output "Double-click it to:"
Write-Output "  1. Start the FastAPI backend on http://127.0.0.1:8000 (hidden)"
Write-Output "  2. Open http://127.0.0.1:8000/ui/dashboard.html in your browser"

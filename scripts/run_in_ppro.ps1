# Run a .jsx inside Premiere Pro from the command line.
#
# Verified recipe (2026-07-20): `Adobe Premiere Pro.exe /C es.processFile
# <script.jsx>` runs the script at startup (the `/C` argument is a debug
# console command, not a script path - a bare path after /C does nothing).
# Tested dead ends: PProHeadless.exe exits immediately when given /C (it is
# the Team Projects/AME dynamic-link host, not a script host), and BridgeTalk
# blocks forever under `AfterFX.com -noui`. Proven fallback if /C ever
# regresses: GUI AfterFX.exe driving BridgeTalk `$.evalFile` into
# `premierepro` (see git history of this file).
#
# The payload script must write $MarkerPath itself when done (File.writeln
# flushes on .close()); this runner only polls for it.
#
# Usage:
#   powershell -File scripts/run_in_ppro.ps1 -JsxPath scripts/jsx/resave_samples.jsx -MarkerPath samples/resaves/DONE.txt
param(
    [Parameter(Mandatory = $true)][string]$JsxPath,
    [Parameter(Mandatory = $true)][string]$MarkerPath,
    [int]$TimeoutSec = 900
)
$ErrorActionPreference = "Continue"
$ppro = "C:\Program Files\Adobe\Adobe Premiere Pro 2026\Adobe Premiere Pro.exe"
$JsxPath = (Resolve-Path $JsxPath).Path
$MarkerPath = [System.IO.Path]::GetFullPath($MarkerPath)

if (Get-Process | Where-Object { $_.Name -like "*Premiere*" -or $_.Name -like "PProHeadless*" }) {
    Write-Output "ABORT: Premiere is already running - close it (or save your work) first."
    exit 1
}
if (-not (Test-Path $ppro)) { Write-Output "ABORT: $ppro not found"; exit 1 }
Remove-Item $MarkerPath -Force -ErrorAction SilentlyContinue

# Only the space-free bare form is verified; quoted paths are best-effort.
if ($JsxPath -match " ") {
    Write-Output "WARNING: path contains spaces; quoted es.processFile form is untested"
    $command = "es.processFile `"$JsxPath`""
} else {
    $command = "es.processFile $JsxPath"
}

$launchTime = Get-Date
Start-Process -FilePath $ppro -ArgumentList "/C", $command | Out-Null

$deadline = $launchTime.AddSeconds($TimeoutSec)
while ((Get-Date) -lt $deadline -and -not (Test-Path $MarkerPath)) { Start-Sleep -Seconds 5 }

if (Test-Path $MarkerPath) {
    Start-Sleep -Seconds 3
    Write-Output "SUCCESS: marker present at $MarkerPath"
} else {
    Write-Output "TIMEOUT: no marker after ${TimeoutSec}s"
}

Get-Process | Where-Object { $_.Name -like "*Premiere*" -and $_.StartTime -ge $launchTime } |
    Stop-Process -Force -ErrorAction SilentlyContinue
Write-Output "cleanup done"

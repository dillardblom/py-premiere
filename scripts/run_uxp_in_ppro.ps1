# Run a UXP payload inside Premiere Pro from the command line.
#
# Transport: the harness plugin (scripts/uxp/harness) is dev-loaded into a
# running GUI Premiere via `uxp plugin load` (@adobe/uxp-devtools-cli). On
# load it runs payload.js and writes the marker file - see harness/index.js
# for the contract. Requires UXP developer mode enabled once, as admin:
#   C:\Program Files\Common Files\Adobe\UXP\Developer\settings.json
#   containing {"developer": true}   (or run `npx uxp devtools enable`)
#
# Usage:
#   powershell -File scripts/run_uxp_in_ppro.ps1 -PayloadPath scripts/uxp/payloads/hello.js -ResultPath out.json -ProjectPath samples/models/minimal/06_api.prproj
param(
    [Parameter(Mandatory = $true)][string]$PayloadPath,
    [Parameter(Mandatory = $true)][string]$ResultPath,
    [string]$ProjectPath,
    [string]$JobExtraJson,
    [int]$TimeoutSec = 300,
    [switch]$KeepPremiere
)
$ErrorActionPreference = "Continue"
$ppro = "C:\Program Files\Adobe\Adobe Premiere Pro 2026\Adobe Premiere Pro.exe"
$uxpDir = Join-Path $PSScriptRoot "uxp"
$harnessDir = Join-Path $uxpDir "harness"
$PayloadPath = (Resolve-Path $PayloadPath).Path
$ResultPath = [System.IO.Path]::GetFullPath($ResultPath)
$markerPath = "$ResultPath.marker"

$settings = "C:\Program Files\Common Files\Adobe\UXP\Developer\settings.json"
if (-not (Test-Path $settings) -or
    -not ((Get-Content $settings -Raw | ConvertFrom-Json).developer)) {
    Write-Output "ABORT: UXP developer mode is off. As admin, write {'developer': true} to $settings"
    exit 1
}
if (-not (Test-Path $ppro)) { Write-Output "ABORT: $ppro not found"; exit 1 }

# Bootstrap the devtools CLI (upstream postinstall is broken: undeclared
# deps; install without scripts, then extract the native lib manually).
if (-not (Test-Path (Join-Path $uxpDir "node_modules\.bin\uxp.cmd"))) {
    Push-Location $uxpDir
    npm install --ignore-scripts 2>&1 | Select-Object -Last 1
    node "node_modules\@adobe\uxp-devtools-helper\scripts\devtools_setup.js"
    Pop-Location
}
$uxpCli = Join-Path $uxpDir "node_modules\.bin\uxp.cmd"

# The devtools service must be running for the app to register; reuse an
# existing one (port 14001), else start our own and stop it on exit.
$serviceProc = $null
if (-not (Get-NetTCPConnection -LocalPort 14001 -State Listen -ErrorAction SilentlyContinue)) {
    $serviceProc = Start-Process $uxpCli -ArgumentList "service", "start" `
        -WorkingDirectory $uxpDir -PassThru -WindowStyle Hidden
    Start-Sleep -Seconds 3
}

# Stage the job: payload + job.json inside the plugin folder.
Copy-Item $PayloadPath (Join-Path $harnessDir "payload.js") -Force
Remove-Item $ResultPath, $markerPath -Force -ErrorAction SilentlyContinue
$job = @{
    name = [System.IO.Path]::GetFileNameWithoutExtension($PayloadPath)
    result = $ResultPath -replace "\\", "/"
    marker = $markerPath -replace "\\", "/"
}
if ($ProjectPath) {
    $job.project = (Resolve-Path $ProjectPath).Path -replace "\\", "/"
}
if ($JobExtraJson) {
    ($JobExtraJson | ConvertFrom-Json).PSObject.Properties |
        ForEach-Object { $job[$_.Name] = $_.Value }
}
# WriteAllText with explicit encoding: Set-Content -Encoding utf8 writes a
# BOM under Windows PowerShell, which JSON.parse in the plugin rejects.
[System.IO.File]::WriteAllText((Join-Path $harnessDir "job.json"),
    ($job | ConvertTo-Json),
    (New-Object System.Text.UTF8Encoding($false)))

if (Get-Process | Where-Object { $_.Name -like "*Premiere*" }) {
    Write-Output "ABORT: Premiere is already running - close it first."
    exit 1
}
$launchTime = Get-Date
if ($ProjectPath) {
    # Bare command-line open raises a blocking "path does not exist" modal
    # even for valid files (26.3); open silently via the ExtendScript
    # opener instead (app.openDocument suppresses the dialogs), then load
    # the plugin against the now-active project.
    $ProjectPath = (Resolve-Path $ProjectPath).Path
    $opener = Join-Path $uxpDir "open_project.jsx"
    $env:PYPREMIERE_OPEN = $ProjectPath
    $env:PYPREMIERE_OPEN_MARKER = "$ResultPath.open"
    Remove-Item $env:PYPREMIERE_OPEN_MARKER -Force -ErrorAction SilentlyContinue
    Start-Process -FilePath $ppro -ArgumentList "/C", "es.processFile $opener" | Out-Null
    $openDeadline = $launchTime.AddSeconds($TimeoutSec)
    while ((Get-Date) -lt $openDeadline -and
           -not (Test-Path $env:PYPREMIERE_OPEN_MARKER)) {
        Start-Sleep -Seconds 3
    }
    if (Test-Path $env:PYPREMIERE_OPEN_MARKER) {
        Write-Output "opener: $((Get-Content $env:PYPREMIERE_OPEN_MARKER -Raw).Trim())"
    } else {
        Write-Output "WARNING: project opener marker never appeared"
    }
} else {
    Start-Process -FilePath $ppro | Out-Null
}

# Premiere registers with the service once the UI is up; retry the load
# until it sticks (each attempt fails fast while the app is still booting).
$deadline = $launchTime.AddSeconds($TimeoutSec)
$loaded = $false
while ((Get-Date) -lt $deadline -and -not $loaded) {
    Start-Sleep -Seconds 5
    $out = & $uxpCli plugin load --manifest (Join-Path $harnessDir "manifest.json") 2>&1 | Out-String
    if ($out -notmatch "failed|Error") { $loaded = $true; Write-Output "plugin load: $($out.Trim())" }
}
if (-not $loaded) { Write-Output "TIMEOUT: plugin never loaded" }

while ((Get-Date) -lt $deadline -and -not (Test-Path $markerPath)) {
    Start-Sleep -Seconds 2
}
if (Test-Path $markerPath) {
    $marker = Get-Content $markerPath -Raw
    if ($marker -like "DONE*") { Write-Output "SUCCESS: $ResultPath" }
    else { Write-Output "PAYLOAD $marker" }
} elseif ($loaded) {
    Write-Output "TIMEOUT: plugin loaded but no marker after ${TimeoutSec}s"
}

if (-not $KeepPremiere) {
    Get-Process | Where-Object { $_.Name -like "*Premiere*" -and $_.StartTime -ge $launchTime } |
        Stop-Process -Force -ErrorAction SilentlyContinue
}
if ($serviceProc) { Stop-Process -Id $serviceProc.Id -Force -ErrorAction SilentlyContinue }
Write-Output "cleanup done"

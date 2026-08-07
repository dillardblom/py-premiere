# Generate the minimal committable corpus, one project per isolated Premiere
# launch (a modal dialog in one target cannot stall the rest). Each target
# writes <target>.DONE; run_in_ppro.ps1 polls it and kills Premiere after.
# We wait for full process quiescence between targets - a force-killed
# Premiere lingers briefly in Get-Process and would trip the runner's
# "already running" guard on the next launch.
#
# Idempotent: targets whose .prproj already exists are skipped.
#
# Usage: powershell -File scripts/gen_minimal_corpus.ps1
$ErrorActionPreference = "Continue"
$repo = "C:\Users\del-m\git\py-premiere"
$outDir = "$repo\samples\models\minimal"
New-Item -ItemType Directory -Force $outDir | Out-Null

function Wait-NoAdobeApps {
    param([int]$TimeoutSec = 60)
    $deadline = (Get-Date).AddSeconds($TimeoutSec)
    while ((Get-Date) -lt $deadline) {
        $running = Get-Process | Where-Object {
            $_.Name -like "*Premiere*" -or $_.Name -like "PProHeadless*" -or $_.Name -like "AfterFX*"
        }
        if (-not $running) { return $true }
        $running | Stop-Process -Force -ErrorAction SilentlyContinue
        Start-Sleep -Seconds 2
    }
    return $false
}

# target -> produced filename
$targets = [ordered]@{
    empty     = "01_empty.prproj"
    bins      = "02_bins.prproj"
    clip      = "03_one_clip.prproj"
    sequence  = "04_sequence.prproj"
    features  = "05_features.prproj"
    api       = "06_api.prproj"
    audiomute = "17_audio_mute.prproj"  # derives from 06_api
}

foreach ($target in $targets.Keys) {
    $produced = "$outDir\$($targets[$target])"
    if (Test-Path $produced) {
        Write-Output "=== skip $target (exists) ==="
        continue
    }
    if (-not (Wait-NoAdobeApps)) {
        Write-Output "=== $target : Adobe apps would not quiesce, aborting ==="
        break
    }
    $env:PY_PREMIERE_GEN = $target
    Write-Output "=== generating: $target ==="
    & "$repo\scripts\run_in_ppro.ps1" `
        -JsxPath "$repo\scripts\jsx\gen_minimal.jsx" `
        -MarkerPath "$outDir\$target.DONE" `
        -TimeoutSec 180
}
Remove-Item Env:\PY_PREMIERE_GEN -ErrorAction SilentlyContinue
Write-Output "=== log ==="
if (Test-Path "$outDir\generate_log.txt") { Get-Content "$outDir\generate_log.txt" }
Write-Output "=== produced ==="
Get-ChildItem "$outDir\*.prproj" -ErrorAction SilentlyContinue | ForEach-Object { $_.Name }

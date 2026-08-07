# One Premiere launch per format: batching them stalls, because a format
# whose import raises a modal blocks every job queued behind it.
#
# Formats is ONE semicolon-separated string ("stem|file;stem|file"), split
# here: a comma-separated array argument does not survive every shell.
#
#   powershell -File scripts/gen_media_refs.ps1 -Formats "26_mp3|tone_440.mp3;27_m4a|tone_440.m4a"
param([Parameter(Mandatory = $true)][string]$Formats, [int]$TimeoutSec = 180)
$repo = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$marker = Join-Path $repo "samples\refs\media\one.DONE"
foreach ($spec in ($Formats -split ";")) {
    Get-Process | Where-Object { $_.Name -like "*Premiere*" } |
        Stop-Process -Force -ErrorAction SilentlyContinue
    Start-Sleep -Seconds 3
    Remove-Item $marker -Force -ErrorAction SilentlyContinue
    $env:PY_PREMIERE_MEDIA = $spec
    Write-Output "=== $spec ==="
    & "$repo\scripts\run_in_ppro.ps1" `
        -JsxPath "$repo\scripts\jsx\make_one_media_ref.jsx" `
        -MarkerPath $marker -TimeoutSec $TimeoutSec
}
Remove-Item Env:\PY_PREMIERE_MEDIA -ErrorAction SilentlyContinue
Write-Output "=== log ==="
Get-Content (Join-Path $repo "samples\refs\media\log_single.txt") -ErrorAction SilentlyContinue

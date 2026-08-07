# Single-setting fixture factory: generate one project per VALUE of one
# component param, so a value -> XML mapping can be read straight off a
# pr-compare chain (no new jsx per experiment).
#
# Usage:
#   powershell -File scripts/gen_sweep_fixtures.ps1 -Component Opacity `
#       -Param "Blend Mode" -Values 0,1,2,18
#
# Output: samples/models/sweep/<Component>_<Param>_<value>.prproj, then a
# pairwise diff of consecutive values so the changed field is obvious.
param(
    [Parameter(Mandatory = $true)][string]$Component,
    [Parameter(Mandatory = $true)][string]$Param,
    [Parameter(Mandatory = $true)][string[]]$Values,
    [switch]$NoDiff
)

$repo = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$sweepDir = Join-Path $repo "samples\models\sweep"
$marker = Join-Path $sweepDir "sweep.DONE"
New-Item -ItemType Directory -Force $sweepDir | Out-Null
Remove-Item $marker -Force -ErrorAction SilentlyContinue

$env:PY_PREMIERE_GEN = "sweep"
$env:PY_PREMIERE_SWEEP = "$Component|$Param|$($Values -join ',')"
Write-Output "sweep spec: $env:PY_PREMIERE_SWEEP"

& "$repo\scripts\run_in_ppro.ps1" `
    -JsxPath "$repo\scripts\jsx\gen_minimal.jsx" `
    -MarkerPath $marker `
    -TimeoutSec 600

Remove-Item Env:\PY_PREMIERE_GEN -ErrorAction SilentlyContinue
Remove-Item Env:\PY_PREMIERE_SWEEP -ErrorAction SilentlyContinue
Remove-Item (Join-Path $sweepDir "_sweep_tmp.prproj") -Force -ErrorAction SilentlyContinue

$stemComponent = ($Component -replace '\W+', '')
$stemParam = ($Param -replace '\W+', '')
$produced = $Values | ForEach-Object {
    Join-Path $sweepDir "$($stemComponent)_$($stemParam)_$_.prproj"
} | Where-Object { Test-Path $_ }
Write-Output "=== produced $($produced.Count)/$($Values.Count) ==="
$produced | ForEach-Object { Write-Output "  $_" }

if (-not $NoDiff -and $produced.Count -ge 2) {
    for ($i = 1; $i -lt $produced.Count; $i++) {
        Write-Output ""
        Write-Output "=== $(Split-Path $produced[$i - 1] -Leaf) -> $(Split-Path $produced[$i] -Leaf) ==="
        & uv run pr-compare $produced[$i - 1] $produced[$i]
    }
}

# DP-357 step 1: fetch the higher quants of the Phase 0 winner.
#
# Adam's call 2026-09-01: lean reliability over speed - no KV quantisation, and
# consider raising the base-model quant. Q4_K_M is what was actually scored, so
# Q6_K and Q8_0 are unmeasured until the ladder re-run; this only puts them on disk.
#
# Same repo as the scored file (ibm-granite/granite-4.2-8b-GGUF) so the only
# variable between rungs is the quant.
$ErrorActionPreference = 'Continue'
$dest = 'F:\Machine Learning\LLM Weights\dp357'
New-Item -ItemType Directory -Force $dest | Out-Null

$models = @(
    @{ file = 'granite-4.2-8b-Q6_K.gguf'; bytes = 7216480384 },
    @{ file = 'granite-4.2-8b-Q8_0.gguf'; bytes = 9345613952 }
)

foreach ($m in $models) {
    $out = Join-Path $dest $m.file
    $url = "https://huggingface.co/ibm-granite/granite-4.2-8b-GGUF/resolve/main/$($m.file)"
    Write-Output "$(Get-Date -Format o)  fetching $($m.file)"
    & curl.exe -L --fail --retry 5 --retry-delay 10 -C - -o "$out" "$url" 2>&1 | Out-Null

    if (Test-Path $out) {
        $actual = (Get-Item $out).Length
        # A truncated gguf crashes koboldcpp rather than failing cleanly, so verify
        # the byte count against HF's published Content-Length before trusting it.
        if ($actual -eq $m.bytes) {
            Write-Output "$(Get-Date -Format o)  OK $($m.file) = $actual bytes"
        } else {
            Write-Output "$(Get-Date -Format o)  BAD $($m.file): $actual != published $($m.bytes)"
        }
    } else {
        Write-Output "$(Get-Date -Format o)  FAILED $($m.file)"
    }
}
Write-Output "$(Get-Date -Format o)  quant downloads finished"

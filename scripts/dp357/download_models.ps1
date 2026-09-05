# DP-357 Phase 0: fetch the four production candidates that are not on dt21's F:.
#
# The six diagnostic/incumbent models are already on disk; these four are the
# small, current, stock rows the bake-off exists to find a winner among. All are
# Q4_K_M to match the on-disk candidates, from the official repo where one
# exists. ~36 GB total, ~14 min at dt21's measured 44.6 MB/s.
#
# Downloads run alongside the bake-off on purpose: they use no GPU, and the run
# has five on-disk models to work through before it needs any of these.
# Re-running skips files that are already complete.

$ErrorActionPreference = 'Continue'
$dest = 'F:\Machine Learning\LLM Weights\dp357'
New-Item -ItemType Directory -Force $dest | Out-Null

$models = @(
    @{ repo = 'ggml-org/gemma-3-12b-it-GGUF';            file = 'gemma-3-12b-it-Q4_K_M.gguf' },
    @{ repo = 'ibm-granite/granite-4.2-8b-GGUF';         file = 'granite-4.2-8b-Q4_K_M.gguf' },
    @{ repo = 'Qwen/Qwen3-8B-GGUF';                      file = 'Qwen3-8B-Q4_K_M.gguf' },
    @{ repo = 'ibm-granite/granite-4.0-h-small-GGUF';    file = 'granite-4.0-h-small-Q4_K_M.gguf' }
)

foreach ($m in $models) {
    $out = Join-Path $dest $m.file
    $url = "https://huggingface.co/$($m.repo)/resolve/main/$($m.file)"

    # curl -C - resumes a partial file and exits immediately on a complete one
    Write-Output "$(Get-Date -Format o)  fetching $($m.file) from $($m.repo)"
    & curl.exe -L --fail --retry 5 --retry-delay 10 -C - -o "$out" "$url" 2>&1 | Out-Null

    if (Test-Path $out) {
        $gb = [math]::Round((Get-Item $out).Length / 1GB, 2)
        Write-Output "$(Get-Date -Format o)  done $($m.file) = $gb GB"
    } else {
        Write-Output "$(Get-Date -Format o)  FAILED $($m.file)"
    }
}
Write-Output "$(Get-Date -Format o)  all downloads finished"

# DP-357 Phase 0, second pass: add the downloaded candidates and run them.
#
# The first pass covers the five models already on dt21's F:. The four stock
# production candidates are downloading in parallel and are not in models.json,
# because run_bakeoff.py reads that file once at startup.
#
# This script waits for both to finish, verifies each download against its
# published byte count (a truncated gguf crashes koboldcpp rather than failing
# cleanly), appends the complete ones to models.json, and relaunches. The
# checkpoint in results.jsonl means the five already-scored models are skipped.
#
# Launch it detached the same way as the runner -- Win32_Process.Create, not
# Start-Process, or it dies with the ssh session.

$ErrorActionPreference = 'Continue'
$dir = 'C:\Users\Adam\dp357'
$weights = 'F:\Machine Learning\LLM Weights\dp357'
Set-Location $dir

# id, filename, published size in bytes, and the note that says why it is here
$candidates = @(
    @{ id = 'gemma-3-12b-it';       file = 'gemma-3-12b-it-Q4_K_M.gguf';       bytes = 7300574976
       gb = 6.8;  note = '4.4% on Vectara - best faithfulness-per-GB on the board, and half the VRAM of the A4B.' },
    @{ id = 'granite-4.2-8b';       file = 'granite-4.2-8b-Q4_K_M.gguf';       bytes = 5347917952
       gb = 4.98; note = 'Released 2026-08-25; dense 8B, the fastest serious option. Supersedes the old granite twice over.' },
    @{ id = 'qwen3-8b';             file = 'Qwen3-8B-Q4_K_M.gguf';             bytes = 5027783488
       gb = 4.68; note = '4.8%. The only row that tests backing DOWN a Qwen generation - Qwen3 scored well, Qwen3.5 regressed to 10.5-12.1%.' },
    @{ id = 'granite-4.0-h-small';  file = 'granite-4.0-h-small-Q4_K_M.gguf';  bytes = 19476621984
       gb = 18.14; note = '5.2%, 32B/9B active hybrid Mamba-2. No growing KV cache, so memory stays flat as context and concurrency rise - the most interesting throughput profile in the set. Will NOT fit 16 GB; record the offload split and tok/s.' }
)

function Test-Runner {
    [bool](Get-CimInstance Win32_Process -Filter "Name='python.exe'" |
        Where-Object { $_.CommandLine -like '*run_bakeoff.py*' })
}

# 1. wait for the first pass to finish (cap: 10 h)
$deadline = (Get-Date).AddHours(10)
while ((Test-Runner) -and (Get-Date) -lt $deadline) { Start-Sleep -Seconds 60 }
if (Test-Runner) {
    Write-Output "$(Get-Date -Format o)  first pass still running after 10 h - giving up, not relaunching"
    exit 1
}
Write-Output "$(Get-Date -Format o)  first pass finished"

# 2. wait for the downloads (cap: 2 h from here)
$deadline = (Get-Date).AddHours(2)
while ((Get-Date) -lt $deadline) {
    $log = Get-Content "$dir\download.log" -ErrorAction SilentlyContinue
    if ($log -match 'all downloads finished') { break }
    Start-Sleep -Seconds 60
}
Write-Output "$(Get-Date -Format o)  downloads settled"

# 3. keep only the candidates whose file is present at exactly the published size
$models = Get-Content "$dir\models.json" -Raw | ConvertFrom-Json
$added = @()
foreach ($c in $candidates) {
    $path = Join-Path $weights $c.file
    if (-not (Test-Path $path)) {
        Write-Output "  SKIP $($c.id): file missing"
        continue
    }
    $actual = (Get-Item $path).Length
    if ($actual -ne $c.bytes) {
        Write-Output "  SKIP $($c.id): size $actual != published $($c.bytes) - incomplete download"
        continue
    }
    $models += [pscustomobject]@{
        id      = $c.id
        role    = 'production_candidate'
        path    = ($path -replace '\\', '/')
        quant   = 'Q4_K_M'
        size_gb = $c.gb
        note    = $c.note
    }
    $added += $c.id
    Write-Output "  ADD  $($c.id) ($($c.gb) GB)"
}

if ($added.Count -eq 0) {
    Write-Output "$(Get-Date -Format o)  nothing complete to add - not relaunching"
    exit 1
}

Copy-Item "$dir\models.json" "$dir\models.pass1.json" -Force
# PowerShell 5.1's -Encoding utf8 writes a BOM, and Python's json.loads rejects it
# ("Unexpected UTF-8 BOM") -- which killed the first relaunch. Write BOM-less UTF-8.
# run_bakeoff.py also reads with utf-8-sig now, so either side alone is sufficient.
[System.IO.File]::WriteAllText("$dir\models.json",
    ($models | ConvertTo-Json -Depth 5),
    (New-Object System.Text.UTF8Encoding($false)))
Write-Output "$(Get-Date -Format o)  models.json now has $($models.Count) rows; added: $($added -join ', ')"

# 4. relaunch; results.jsonl skips everything already scored
& powershell -NoProfile -ExecutionPolicy Bypass -File "$dir\launch_bakeoff.ps1"

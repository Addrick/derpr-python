# DP-357 step 2: the quant-ladder re-run.
#
# Phase 0 named granite-4.2-8b (Q4_K_M, quantkv=2) the winner. Adam's call is to
# lean reliability over speed: no KV quantisation, and consider a higher base quant.
# Raising the quant means shipping a model that was never scored, so this measures
# the ladder instead of assuming it is monotone.
#
# Three rows, all at quantkv=0 (tmpl-f16kv.kcpps). Q4_K_M is re-run rather than
# compared against its Phase 0 row, because that row was scored at quantkv=2 and
# would confound quant with KV precision.
#
# Waits for download_quants.ps1 to finish and verifies both ggufs against their
# published byte counts first -- a truncated gguf crashes koboldcpp rather than
# failing cleanly.
#
# Win32_Process.Create, not Start-Process: see launch_bakeoff.ps1.

$ErrorActionPreference = 'Stop'
$dir = 'C:\Users\Adam\dp357'
$py = 'C:\Users\Adam\AppData\Local\Python\pythoncore-3.14-64\python.exe'
$weights = 'F:\Machine Learning\LLM Weights\dp357'
Set-Location $dir

$expected = @{
    'granite-4.2-8b-Q4_K_M.gguf' = 5347917952
    'granite-4.2-8b-Q6_K.gguf'   = 7216480384
    'granite-4.2-8b-Q8_0.gguf'   = 9345613952
}

# 1. wait for the downloads to settle (cap 1 h)
$deadline = (Get-Date).AddHours(1)
while ((Get-Date) -lt $deadline) {
    $log = Get-Content "$dir\download_quants.log" -Raw -ErrorAction SilentlyContinue
    if ($log -match 'quant downloads finished') { break }
    Start-Sleep -Seconds 30
}
Write-Output "$(Get-Date -Format o)  downloads settled"

# 2. every rung must be present at exactly its published size or the ladder is not comparable
$bad = @()
foreach ($f in $expected.Keys) {
    $path = Join-Path $weights $f
    if (-not (Test-Path $path)) { $bad += "$f MISSING"; continue }
    $actual = (Get-Item $path).Length
    if ($actual -ne $expected[$f]) { $bad += "$f $actual != $($expected[$f])"; continue }
    Write-Output "  OK $f = $actual bytes"
}
if ($bad.Count -gt 0) {
    Write-Output "$(Get-Date -Format o)  ABORTING - incomplete weights: $($bad -join '; ')"
    exit 1
}

# 3. refuse to start on top of anything already using the GPU or the port
$existing = Get-Process -Name koboldcpp -ErrorAction SilentlyContinue
if ($existing) {
    Write-Output "REFUSING TO START: koboldcpp already running (PID $($existing.Id -join ','))"
    exit 1
}
$running = Get-CimInstance Win32_Process -Filter "Name='python.exe'" |
    Where-Object { $_.CommandLine -like '*run_bakeoff.py*' }
if ($running) {
    Write-Output "REFUSING TO START: a bake-off is already running (PID $($running.ProcessId -join ','))"
    exit 1
}

$inner = "`"$py`" run_bakeoff.py --bodies bodies.json --models models.quantladder.json " +
         "--template tmpl-f16kv.kcpps --out results.quantladder.jsonl " +
         "--workdir quantladder_work --repeats 3"
$cmdline = "cmd.exe /c `"$inner >> quantladder.log 2>> quantladder.err`""

$result = Invoke-CimMethod -ClassName Win32_Process -MethodName Create `
    -Arguments @{ CommandLine = $cmdline; CurrentDirectory = $dir }
if ($result.ReturnValue -ne 0) {
    Write-Output "Win32_Process.Create FAILED with ReturnValue=$($result.ReturnValue)"
    exit 1
}

Start-Sleep -Seconds 5
$alive = Get-CimInstance Win32_Process -Filter "Name='python.exe'" |
    Where-Object { $_.CommandLine -like '*run_bakeoff.py*' }
Write-Output "launcher pid=$($result.ProcessId) runner=$(if ($alive) { $alive.ProcessId } else { 'NOT FOUND' }) at $(Get-Date -Format o)"
Write-Output "log: $dir\quantladder.log"

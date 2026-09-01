# DP-357 Phase 0: launch the bake-off fully detached on dt21.
#
# The run outlives the ssh session that starts it (omen goes offline mid-run),
# so it is started with Start-Process and writes everything to run.log.
# results.jsonl is the checkpoint: re-running skips completed calls.

$ErrorActionPreference = 'Stop'
$dir = 'C:\Users\Adam\dp357'
$py = 'C:\Users\Adam\AppData\Local\Python\pythoncore-3.14-64\python.exe'

Set-Location $dir

$existing = Get-Process -Name koboldcpp -ErrorAction SilentlyContinue
if ($existing) {
    Write-Output "REFUSING TO START: koboldcpp already running (PID $($existing.Id -join ','))"
    exit 1
}
$running = Get-CimInstance Win32_Process -Filter "Name='python.exe'" |
    Where-Object { $_.CommandLine -like '*run_bakeoff.py*' }
if ($running) {
    Write-Output "REFUSING TO START: bake-off already running (PID $($running.ProcessId -join ','))"
    exit 1
}

$args = @(
    'run_bakeoff.py',
    '--bodies', 'bodies.json',
    '--models', 'models.json',
    '--template', 'tmpl.kcpps',
    '--out', 'results.jsonl',
    '--repeats', '3'
)

$proc = Start-Process -FilePath $py -ArgumentList $args -WorkingDirectory $dir `
    -RedirectStandardOutput "$dir\run.log" -RedirectStandardError "$dir\run.err" `
    -WindowStyle Hidden -PassThru

Start-Sleep -Seconds 3
Write-Output "started pid=$($proc.Id) at $(Get-Date -Format o)"
Write-Output "log: $dir\run.log"

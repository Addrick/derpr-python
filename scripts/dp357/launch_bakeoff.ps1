# DP-357 Phase 0: launch the bake-off so it survives the ssh session that starts it.
#
# Start-Process is NOT enough here. OpenSSH on Windows puts the session's whole
# process tree in a job object and kills it on disconnect, so a Start-Process
# child dies the moment the launching ssh command returns -- observed on the
# first attempt: run.log stopped after "launching koboldcpp" and both the runner
# and koboldcpp were gone.
#
# Win32_Process.Create goes through the WMI service instead, so the new process
# is not a descendant of sshd and outlives the connection. omen goes offline
# mid-run, so this matters.
#
# results.jsonl is the checkpoint: re-running skips completed calls.

$ErrorActionPreference = 'Stop'
$dir = 'C:\Users\Adam\dp357'
$py = 'C:\Users\Adam\AppData\Local\Python\pythoncore-3.14-64\python.exe'

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

# cmd.exe does the redirection so the runner's stdout lands in run.log even
# though nothing is attached to the new process.
$inner = "`"$py`" run_bakeoff.py --bodies bodies.json --models models.json " +
         "--template tmpl.kcpps --out results.jsonl --repeats 3"
$cmdline = "cmd.exe /c `"$inner >> run.log 2>> run.err`""

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
Write-Output "log: $dir\run.log"

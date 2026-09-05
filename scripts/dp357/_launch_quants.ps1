# Detached launcher for download_quants.ps1.
# Win32_Process.Create, NOT Start-Process: OpenSSH puts the session's process tree in a
# job object and kills it on disconnect, so a Start-Process job dies silently the moment
# the ssh command returns. Cost DP-357 a 12-hour bake-off once already.
$dir = 'C:\Users\Adam\dp357'
$inner = "powershell -NoProfile -ExecutionPolicy Bypass -File $dir\download_quants.ps1"
$cmdline = "cmd.exe /c `"$inner >> $dir\download_quants.log 2>&1`""
$r = Invoke-CimMethod -ClassName Win32_Process -MethodName Create `
        -Arguments @{ CommandLine = $cmdline; CurrentDirectory = $dir }
Write-Output "rv=$($r.ReturnValue) pid=$($r.ProcessId)"

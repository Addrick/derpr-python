$dir = 'C:\Users\Adam\dp357'
$inner = "powershell -NoProfile -ExecutionPolicy Bypass -File $dir\run_power.ps1"
$cmdline = "cmd.exe /c `"$inner >> $dir\power.log 2>&1`""
$r = Invoke-CimMethod -ClassName Win32_Process -MethodName Create `
        -Arguments @{ CommandLine = $cmdline; CurrentDirectory = $dir }
Write-Output "rv=$($r.ReturnValue) pid=$($r.ProcessId)"

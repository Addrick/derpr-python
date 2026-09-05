# Detached launcher for launch_quantladder.ps1 (which itself blocks waiting on the
# downloads, so it must not be tied to the ssh session either).
$dir = 'C:\Users\Adam\dp357'
$inner = "powershell -NoProfile -ExecutionPolicy Bypass -File $dir\launch_quantladder.ps1"
$cmdline = "cmd.exe /c `"$inner >> $dir\ladder_chain.log 2>&1`""
$r = Invoke-CimMethod -ClassName Win32_Process -MethodName Create `
        -Arguments @{ CommandLine = $cmdline; CurrentDirectory = $dir }
Write-Output "rv=$($r.ReturnValue) pid=$($r.ProcessId)"

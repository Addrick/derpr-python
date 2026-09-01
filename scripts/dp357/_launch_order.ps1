$dir='C:\Users\Adam\dp357'
$inner="powershell -NoProfile -ExecutionPolicy Bypass -File $dir\run_order_probe.ps1"
$r=Invoke-CimMethod -ClassName Win32_Process -MethodName Create -Arguments @{
    CommandLine="cmd.exe /c `"$inner >> $dir\orderprobe.log 2>&1`""; CurrentDirectory=$dir }
Write-Output "rv=$($r.ReturnValue) pid=$($r.ProcessId)"

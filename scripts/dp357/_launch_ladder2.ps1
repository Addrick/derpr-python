# The quantkv=2 arm, completing the 2x3 quant x KV grid. Same fixtures, same bodies,
# same scorer -- only the template differs from the f16 arm (tmpl.kcpps = quantkv 2).
$dir = 'C:\Users\Adam\dp357'
$py  = 'C:\Users\Adam\AppData\Local\Python\pythoncore-3.14-64\python.exe'
$inner = "`"$py`" run_bakeoff.py --bodies bodies.json --models models.quantladder-q8kv.json " +
         "--template tmpl.kcpps --out results.quantladder-q8kv.jsonl " +
         "--workdir quantladder2_work --repeats 3"
$cmdline = "cmd.exe /c `"$inner >> quantladder2.log 2>> quantladder2.err`""
$r = Invoke-CimMethod -ClassName Win32_Process -MethodName Create `
        -Arguments @{ CommandLine = $cmdline; CurrentDirectory = $dir }
Write-Output "rv=$($r.ReturnValue) pid=$($r.ProcessId)"

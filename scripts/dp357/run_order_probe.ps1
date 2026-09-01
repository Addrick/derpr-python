# Does fixture POSITION change the outcome? The ladder and the power run disagreed on
# dark_roast for one identical config (3/3 fired vs 0/10), and the only surviving
# difference was where dark_roast sat in the fixture sequence. These bodies share a large
# system prompt, so koboldcpp fast-forwards the common prefix; how much KV is reused vs
# recomputed changes with position, and llama.cpp numerics are not identical across those
# paths. At temp 0.1 against a bimodal outcome that can flip the result.
#
# Two runs, same weights/template/repeats, dark_roast first vs last. If the rate moves,
# the harness is order-sensitive and no cross-run comparison in this ticket is valid.
$ErrorActionPreference='Continue'
$dir='C:\Users\Adam\dp357'
$py ='C:\Users\Adam\AppData\Local\Python\pythoncore-3.14-64\python.exe'
Set-Location $dir
function Test-Runner { [bool](Get-CimInstance Win32_Process -Filter "Name='python.exe'" |
    Where-Object { $_.CommandLine -like '*run_bakeoff.py*' }) }
$deadline=(Get-Date).AddHours(2)
while ((Test-Runner) -and (Get-Date) -lt $deadline) { Start-Sleep -Seconds 30 }
if (Test-Runner) { Write-Output "prior run still going - aborting"; exit 1 }
foreach ($tag in @('darkfirst','darklast')) {
    Write-Output "$(Get-Date -Format o)  === order probe $tag ==="
    & $py run_bakeoff.py --bodies "bodies.order-$tag.json" --models "models.order-$tag.json" `
        --template tmpl-f16kv.kcpps --out results.orderprobe.jsonl `
        --workdir "order_work_$tag" --repeats 10 2>&1 | ForEach-Object { Write-Output $_ }
}
Write-Output "$(Get-Date -Format o)  ORDER PROBE COMPLETE"

# Position re-test with nofastforward=true. The prediction is convergence: with no prefix
# reuse every call recomputes the full prompt, so where a fixture sits should stop mattering.
# Divergence would mean the prompt cache is NOT the mechanism and something else is loose.
$ErrorActionPreference='Continue'
$dir='C:\Users\Adam\dp357'
$py ='C:\Users\Adam\AppData\Local\Python\pythoncore-3.14-64\python.exe'
Set-Location $dir
function Test-Runner { [bool](Get-CimInstance Win32_Process -Filter "Name='python.exe'" |
    Where-Object { $_.CommandLine -like '*run_bakeoff.py*' }) }
$deadline=(Get-Date).AddHours(1)
while ((Test-Runner) -and (Get-Date) -lt $deadline) { Start-Sleep -Seconds 30 }
foreach ($tag in @('darkfirst','darklast')) {
    Write-Output "$(Get-Date -Format o)  === nff probe $tag ==="
    & $py run_bakeoff.py --bodies "bodies.order-$tag.json" --models "models.order-$tag-nff.json" `
        --template tmpl-f16kv-nff.kcpps --out results.ordernff.jsonl `
        --workdir "nff_work_$tag" --repeats 10 2>&1 | ForEach-Object { Write-Output $_ }
}
Write-Output "$(Get-Date -Format o)  NFF PROBE COMPLETE"

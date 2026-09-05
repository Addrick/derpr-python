$dir='C:\Users\Adam\dp357'
$py ='C:\Users\Adam\AppData\Local\Python\pythoncore-3.14-64\python.exe'
$kob='F:\Machine Learning\koboldcpp\koboldcpp.exe'
Set-Location $dir
# reuse the nff config the probe just validated; run_bakeoff wrote it per-cell
$cfg = Get-ChildItem "$dir\nff_work_darkfirst\*.kcpps" | Select-Object -First 1
Write-Output "config: $($cfg.FullName)"
$p = Start-Process -FilePath $kob -ArgumentList @('--config', "`"$($cfg.FullName)`"") -PassThru -WindowStyle Hidden
for ($i=0; $i -lt 60; $i++) {
    Start-Sleep -Seconds 5
    try { $m = Invoke-RestMethod -Uri 'http://127.0.0.1:5099/api/v1/model' -TimeoutSec 5; if ($m.result) { break } } catch {}
}
Write-Output "serving: $($m.result)"
& $py seed_check.py
taskkill /F /T /PID $p.Id | Out-Null
Write-Output "SEEDCHECK DONE"

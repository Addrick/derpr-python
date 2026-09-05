# DP-357: the power run. Three KV settings x three quants x 10 repeats, on the three
# fixtures the rungs actually disagree on.
#
# Why this exists: Hindsight's real retain body is temperature 0.1 with no seed and no
# top_p, and the disagreements are BIMODAL - a config either emits nothing on a fixture
# or emits 4-7 facts, with no middle. At n=3 that is indistinguishable from one coin
# landing the same way three times, so the ladder's point estimates cannot support the
# conclusions drawn from them. 10 repeats measures a rate.
#
# quantkv 1 (q8) is included because it was never run: the ladder tested 0 (f16) and
# 2 (q4) only, and 1 is the value the install-template standard specifies.
#
# Waits for any bake-off already running - all runs share port 5099 and the GPU.

$ErrorActionPreference = 'Continue'
$dir = 'C:\Users\Adam\dp357'
$py  = 'C:\Users\Adam\AppData\Local\Python\pythoncore-3.14-64\python.exe'
Set-Location $dir

function Test-Runner {
    [bool](Get-CimInstance Win32_Process -Filter "Name='python.exe'" |
        Where-Object { $_.CommandLine -like '*run_bakeoff.py*' })
}

$deadline = (Get-Date).AddHours(2)
while ((Test-Runner) -and (Get-Date) -lt $deadline) { Start-Sleep -Seconds 30 }
if (Test-Runner) { Write-Output "$(Get-Date -Format o)  prior run still going - aborting"; exit 1 }
Write-Output "$(Get-Date -Format o)  prior run finished; starting power run"

$arms = @(
    @{ tag = 'f16kv'; tmpl = 'tmpl-f16kv.kcpps' },
    @{ tag = 'q8kv';  tmpl = 'tmpl-q8kv.kcpps'  },
    @{ tag = 'q4kv';  tmpl = 'tmpl.kcpps'       }
)

foreach ($a in $arms) {
    Write-Output "$(Get-Date -Format o)  === arm $($a.tag) ($($a.tmpl)) ==="
    & $py run_bakeoff.py --bodies bodies.disputed.json --models "models.power-$($a.tag).json" `
        --template $a.tmpl --out "results.power.jsonl" `
        --workdir "power_work_$($a.tag)" --repeats 10 2>&1 |
        ForEach-Object { Write-Output $_ }
}
Write-Output "$(Get-Date -Format o)  POWER RUN COMPLETE"

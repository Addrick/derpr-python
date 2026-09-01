# DP-357 Phase 0 — extraction model bake-off

Tests whether Hindsight's extraction failures are a **model-capability** problem rather
than a prompt problem. See `memory/project/plans/DP-357-hindsight-extraction-model-bakeoff.md`.

## Pipeline

| Step | Script | Runs on | Produces |
|---|---|---|---|
| 1. Source the fixtures | `build_fixtures.py` | any box that can reach the bank | `fixtures.json` |
| 2. Build the real request bodies | `build_bodies.py` | **inside `hindsight-memory` on ct100** | `bodies.json` |
| 3. Run the matrix | `run_bakeoff.py` (via `launch_bakeoff.ps1`) | **dt21** | `results.jsonl` |
| 4. Score | offline, against `results.jsonl` | anywhere | — |

Step 2 runs in the container on purpose. Hindsight assembles the system prompt from a base
template, the bank's `retain_mission`, the mode guidelines, a causal-links section and a
*dynamically built* entity-labels schema, then constrains the response with a `json_schema`
derived from a Pydantic model. Reimplementing that would score a strawman, so the harness
imports the running server's own `_build_extraction_prompt_and_schema` and
`_build_user_message`. The resolved config is rebuilt exactly as
`ConfigResolver.resolve_full_config` does — env-derived global config, then the bank's
stored overrides on top — so no database connection is needed.

Nothing is scored during the run. All data goes to `results.jsonl`, so a scoring bug never
costs a re-run, and `(model_id, fixture_id, repeat)` acts as the checkpoint.

## Fixtures

Ten cases: eight negative (every known-bad example from the census and DP-336) and two
positive controls. Nine are chunks that were **actually fed to the extractor in production**,
pulled live from the `claudecode` bank; `dark_roast` is verbatim LongMemEval haystack
content — the class of text that contaminated the bank.

The two positive controls exist so that "extract nothing" cannot score perfectly:
`dark_roast` must yield nothing, `optional_personas` must yield real multi-fact synthesis.

Labels (`must_extract` / `must_not_extract`) are drafted in `build_fixtures.py` with the
justification recorded beside each one.

## Harness validity

The incumbent reproduces the canonical defect on the first run: from `alice_drift` — a chunk
that blockquotes the fabricated CKA sentence and follows it with "All false." — it emitted

    "User has 5 years of Kubernetes experience, holds CKA certification,
     and leads the infrastructure team since March."  who = Adam (user)

which is the exact record the census found 174 copies of. The harness measures the real
failure, not a proxy for it.

## Reproducing

```bash
python build_fixtures.py                       # needs the bank at 10.0.0.70:8888
scp overrides.json fixtures.json build_bodies.py ct100:/tmp/
ssh ct100 "docker cp /tmp/fixtures.json hindsight-memory:/tmp/ && \
           docker cp /tmp/overrides.json hindsight-memory:/tmp/ && \
           docker cp /tmp/build_bodies.py hindsight-memory:/tmp/ && \
           docker exec hindsight-memory python /tmp/build_bodies.py \
             --fixtures /tmp/fixtures.json --overrides /tmp/overrides.json --out /tmp/bodies.json"
ssh ct100 "docker cp hindsight-memory:/tmp/bodies.json /tmp/bodies.json" && scp ct100:/tmp/bodies.json .
scp run_bakeoff.py bodies.json models.json tmpl.kcpps launch_bakeoff.ps1 dt21:C:/Users/Adam/dp357/
ssh dt21 "powershell -NoProfile -ExecutionPolicy Bypass -File C:\Users\Adam\dp357\launch_bakeoff.ps1"
```

`launch_bakeoff.ps1` starts the run detached so it outlives the ssh session.

## Bench knobs

`run_bakeoff.py` copies dt21's known-good `.kcpps` and changes only the model path, port
(5099), context size (32768), gen amount (16000) and four knobs applied **identically to
every candidate**, so comparisons hold: `smartcache=0` (Hindsight sends one-shots),
`usemlock=False` (models load and unload repeatedly), `gpulayers=-1` + `autofit` (each model
fits itself to the 16 GB card; the chosen split is recorded per run).

⚠️ dt21's incumbent copy is `Q4_K_M`; production extraction ran omen's `Q4_K_P` build. The
quant is recorded per row — do not treat them as the same model.

## Quant ladder (step 2, after Phase 0)

Phase 0 named `granite-4.2-8b` at **Q4_K_M with `quantkv 2`**. Adam's call 2026-09-01 is to
lean **reliability over speed**: no KV quantisation, and consider raising the base quant —
the reasoning being that this model's failure modes will be as hard to spot as the CKA
false-attributions were, so silent degradation is the thing to spend VRAM against.

Raising the quant ships a model that was never scored, so the ladder is measured rather
than assumed monotone:

| file | rows | template | output |
|---|---|---|---|
| `models.quantladder.json` | Q4_K_M · Q6_K · Q8_0 | `tmpl-f16kv.kcpps` (`quantkv 0`) | `results.quantladder.jsonl` |

Q4_K_M is **re-run**, not compared against its Phase 0 row: that row was scored at
`quantkv 2`, so reading Q6/Q8 against it would confound quant with KV precision. Every row
here is f16 KV, so the quant is the only variable.

```powershell
# on dt21, both detached via Win32_Process.Create (Start-Process dies with the ssh session)
powershell -File _launch_quants.ps1     # fetch Q6_K + Q8_0, verify published byte counts
powershell -File _launch_ladder.ps1     # waits for the downloads, verifies, then runs
```

Scored offline with the Phase 0 scorer, with the control moved to the Q4 rung:

```bash
python score_bakeoff.py --results results.quantladder.jsonl --fixtures fixtures.json \
    --control granite-4.2-8b-q4km-f16kv \
    --out-summary quantladder-summary.md --out-violations quantladder-violations.jsonl
```

The chosen rung then sets the throughput bench, because VRAM couples them: at 16 GB,
Q8_0 (8.70 GiB) fits one instance, Q6_K (6.72) possibly two, Q4_K_M (4.98) three.

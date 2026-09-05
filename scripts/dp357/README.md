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

## ⚠️ The KV scale, and a label error

koboldcpp's `--quantkv` is **`0=f16, 1=q8, 2=q4`**. `tmpl.kcpps` — the template Phase 0
ran — carries `quantkv 2`, which is **q4 KV, the most aggressive setting**, not q8.

This was mislabeled as "q8 KV" throughout the first pass of the ladder analysis, and the
error inverted the reading: it made Phase 0's config look like the conservative choice when
it was the aggressive one. Adam's install-template note of 2026-08-20 already settled this
axis — `--quantkv 1` is correct because q4 degrades quality — which also means **q8 KV was
never tested** until the power run added it.

The `results.quantladder-q8kv.jsonl` / `models.quantladder-q8kv.json` artifacts carried the
wrong name for the same reason and were renamed to `-q4kv`; the model ids inside the results
were rewritten and a `kv_precision` field added. The data was always fine — only the labels
were wrong.

## The power run — why n=3 was not enough

The ladder's per-config numbers do not mean what they appear to. Hindsight's real retain body
is **temperature 0.1, no seed, no top_p**, and the outcomes on the negative fixtures are
**bimodal**: a call emits either nothing or ~5 facts, essentially never 1-2. Pooled over the
six cells of the 2x3 grid, 18 calls per fixture:

| fixture | fires | rate |
|---|---|---|
| `narrator_attribution` | 7/18 | 39% |
| `dark_roast` | 3/18 | 17% |
| `optional_personas` | 18/18 | 100% (the coverage control, as intended) |

`granite-4.2-8b-q6k-q4kv` emitted **7, 6, then 0** on `narrator_attribution` — one config,
three runs, the full range the ladder was reading as a config property. At a 39% base rate a
config draws a clean `0,0,0` about 23% of the time, so across six cells one or two spotless
rows are expected by chance; three appeared.

⚠️ **Consequence for the Phase 0 verdict.** "Zero refutation drops" is not a well-defined
test against a stochastic bimodal process — at n=3 it largely measures luck, and the
recorded claim that granite-4.2-8b *sweeps* is over-stated. What likely survives is the
incumbent comparison: 18 drops with 14 on one fixture is well above this base rate in
magnitude, not just frequency.

`run_power.ps1` therefore re-runs the three disputed fixtures at **10 repeats** across
3 quants x 3 KV settings, to measure a rate instead of a point. Note the limit: n=10
separates 40% from 5%, not 40% from 20%. Ranking the good configs needs the scaled corpus
check, not more repeats on ten fixtures.

## Reproducibility — the recipe (settled 2026-09-01)

The harness was not reproducible, and two independent variables were loose. Both are
now closed, each verified by experiment rather than argument.

**1. Prompt-cache path dependence — fixed by `nofastforward: true`.**
These bodies share a long system prompt, so koboldcpp fast-forwards the common prefix,
and the numerics of a reused prefix differ from a recomputed one. At temperature 0.1
against a bimodal outcome that flips the result. Measured, same weights / KV / bodies /
repeats, moving only `dark_roast`'s slot:

| | first | last |
|---|---|---|
| fast-forward ON (default) | 2/10 | **8/10** |
| fast-forward OFF | **6/10** | **6/10** |

⚠️ **Consequence: every absolute rate measured before this is a cache artifact**, Phase 0's
included. The true `dark_roast` leak rate for Q4_K_M at f16 KV is ~60%, not the 0% the
power run reported at position 2 nor the 17% pooled from the grid. Model-to-model
comparisons within a single run survive, because the confound applied equally to all.

**2. Sampler nondeterminism — fixed by seeding the body.**
The real Hindsight retain body is `temperature 0.1`, no seed, no `top_p`. Verified on the
box: koboldcpp's `/v1/chat/completions` **does** honour `seed` (two calls at `seed=1234`
returned byte-identical content), while the native `sampler_seed` field is **not** mapped
on that endpoint, and unseeded calls differ. `run_bakeoff.py` now sends
`seed = --seed-base + repeat` (default base 1000) and records it per row.

Seeding *by repeat* rather than to one fixed value is deliberate: a single seed pins every
repeat to the same draw, which on a bimodal outcome measures one point of the distribution
ten times and reports it as certainty. Seeding by repeat is reproducible *and* samples.

**To reproduce any run:** same `.kcpps` with `nofastforward: true`, same `--seed-base`,
same fixture order, fresh koboldcpp process per config. `--seed-base -1` restores the old
unseeded behaviour for comparison against pre-2026-09-01 results.

## ⚠️ The gate is one-sided — use `score_recall.py` alongside

`score_bakeoff.py` counts only `must_not_extract` violations, but **9 of the 10 fixtures
carry a non-empty `must_extract`**. A model that extracts nothing scores perfectly.
`score_recall.py` reports silence and violation as separate axes.

Re-scored on both axes, Phase 0's verdict moves:

| model | silence | violation | clean/27 |
|---|---|---|---|
| `gemma-4-26b-a4b-uncensored` | **0%** | **0%** | **27/27** |
| `granite-4.2-8b` | **22%** | 0% | 21/27 |
| `incumbent-qwen3.6-a3b` | 22% | 26% | 14/27 |

Granite's headline zero violations come with a 22% silence rate, and on
`narrator_attribution` **no granite config ever succeeds** — it abstains 10/10 or violates
10/10 depending on quant and KV. What survives is that the incumbent is worst on both axes.

⚠️ That table excludes `dark_roast` (no `must_extract`, so silence is correct there), where
granite leaked 0 and the gemma leaked 9 — a real precision failure it hides. And "not
silent" means ≥1 durable fact, not good coverage.

**Neither instrument identifies a best model.** Note the direct conflict with
`docs/eval_results/lme.md`, where this same incumbent A3B scores 100% (n=7) on M-tier and
`granite-4.1-8b` scores 33% (n=3) — with two of granite's three failures being facts it
never extracted. LME scores end-to-end recall on real questions; these fixtures score
keyword rules on ten hand-picked chunks. Trust LME.

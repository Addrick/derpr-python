"""DP-357: dump EVERY metric in results.jsonl as tables. No judgement, no verdict.

Adam 2026-09-04: "you should be recording all data, including processing speeds,
for all models. If it's a metric, save it in the table just in case."

score_bakeoff.py answers "did it pass" and drops most of what the harness recorded;
score_recall.py adds the silence axis. Neither surfaces throughput, latency spread,
load behaviour, token usage or the offload split, so those have been sitting unread
in the JSONL. This script surfaces them and deliberately makes no claim about which
model is better -- Phase 0 had to be thrown out partly because the numbers that
survived were not enough to re-derive what had happened.

    python metrics_table.py --results results.omen.jsonl --out metrics.md [--full]
"""

import argparse
import json
import statistics
from collections import defaultdict
from pathlib import Path


def load(path):
    """Read the JSONL, keeping call rows and error rows apart."""
    calls, errors = [], []
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            rec = json.loads(line)
        except json.JSONDecodeError:
            continue  # a partial last line from a killed run
        (calls if rec.get("fixture_id") is not None else errors).append(rec)
    return calls, errors


def agg(vals):
    """min / median / mean / max for a numeric column, or None if empty."""
    vals = [v for v in vals if isinstance(v, (int, float))]
    if not vals:
        return None
    return {
        "n": len(vals),
        "min": min(vals),
        "med": statistics.median(vals),
        "mean": sum(vals) / len(vals),
        "max": max(vals),
    }


def fmt(x, nd=2):
    if x is None:
        return "-"
    if isinstance(x, float):
        return f"{x:.{nd}f}"
    return str(x)


def pick(a, key, nd=2):
    """Format one field of an agg() result, tolerating None."""
    return fmt(a and a[key], nd)


def per_model(calls):
    by = defaultdict(list)
    for r in calls:
        by[r["model_id"]].append(r)
    return by


def section_aggregates(L, by):
    L.append("\n## Per-model aggregates\n")
    L.append("`s/call` is wall time including prefill. `tok/s` is completion tokens over "
             "wall time, so it is depressed by prefill on a long prompt -- with "
             "`nofastforward` the ~11k-char system prompt is reprocessed every call, "
             "which is the point of the setting and not a defect.\n")
    L.append("| model | role | quant | GB | calls | s/call min | s/call med | s/call mean | "
             "s/call max | tok/s med | tok/s mean | completion tok med | prompt tok med | "
             "facts med | facts mean | valid JSON | truncated | errors | load s |")
    L.append("|---" * 19 + "|")

    for mid, rows in by.items():
        r0 = rows[0]
        wall = agg([r.get("wall_secs") for r in rows])
        toks = agg([r.get("tok_s") for r in rows])
        comp = agg([(r.get("usage") or {}).get("completion_tokens") for r in rows])
        prom = agg([(r.get("usage") or {}).get("prompt_tokens") for r in rows])
        facts = agg([r.get("n_facts") for r in rows])
        valid = sum(1 for r in rows if r.get("valid_json") is True)
        trunc = sum(1 for r in rows if r.get("finish_reason") == "length")
        errs = sum(1 for r in rows if r.get("error"))
        L.append(
            f"| `{mid}` | {r0.get('model_role', '-')} | {r0.get('quant', '-')} | "
            f"{fmt(r0.get('size_gb'))} | {len(rows)} | "
            f"{pick(wall, 'min')} | {pick(wall, 'med')} | "
            f"{pick(wall, 'mean')} | {pick(wall, 'max')} | "
            f"{pick(toks, 'med', 1)} | {pick(toks, 'mean', 1)} | "
            f"{pick(comp, 'med', 0)} | {pick(prom, 'med', 0)} | "
            f"{pick(facts, 'med', 1)} | {pick(facts, 'mean', 1)} | "
            f"{valid}/{len(rows)} | {trunc} | {errs} | {fmt(r0.get('load_secs'), 1)} |"
        )


def section_by_fixture(L, by, fixtures, field, title, blurb, nd=1):
    L.append(f"\n## {title}\n")
    L.append(blurb + "\n")
    L.append("| model | " + " | ".join(f"`{f}`" for f in fixtures) + " |")
    L.append("|---" * (len(fixtures) + 1) + "|")
    for mid, rows in by.items():
        cells = []
        for f in fixtures:
            a = agg([r.get(field) for r in rows if r["fixture_id"] == f])
            cells.append(pick(a, "mean", nd))
        L.append(f"| `{mid}` | " + " | ".join(cells) + " |")


def section_load(L, by):
    L.append("\n## Load and offload — koboldcpp's own report\n")
    L.append("Recorded verbatim. `offloaded N/M layers` is the real split; "
             "`Auto Recommended GPU Layers` is a pre-scan guess and reads 0 even when "
             "everything lands on the card, so do not use it.\n")
    L.append("| model | GB | load s | offload | other load facts |")
    L.append("|---|---|---|---|---|")
    for mid, rows in by.items():
        r0 = rows[0]
        lf = r0.get("load_facts") or {}
        other = ", ".join(f"{k}={v}" for k, v in lf.items() if k != "offloaded") or "-"
        L.append(f"| `{mid}` | {fmt(r0.get('size_gb'))} | {fmt(r0.get('load_secs'), 1)} | "
                 f"{lf.get('offloaded', '-')} | {other} |")


def section_errors(L, errors):
    if not errors:
        return
    L.append("\n## Error rows\n")
    L.append("| model | error | detail |")
    L.append("|---|---|---|")
    for e in errors:
        L.append(f"| `{e.get('model_id')}` | {e.get('error')} | "
                 f"{str(e.get('detail', ''))[:200]} |")


def section_every_call(L, calls):
    L.append("\n## Every call\n")
    L.append("| model | fixture | repeat | seed | s | tok/s | completion tok | "
             "prompt tok | facts | json | finish | error |")
    L.append("|---" * 12 + "|")
    for r in calls:
        u = r.get("usage") or {}
        L.append(
            f"| `{r['model_id']}` | {r['fixture_id']} | {r['repeat']} | "
            f"{r.get('seed', '-')} | {fmt(r.get('wall_secs'))} | "
            f"{fmt(r.get('tok_s'), 1)} | {u.get('completion_tokens', '-')} | "
            f"{u.get('prompt_tokens', '-')} | {r.get('n_facts', '-')} | "
            f"{r.get('valid_json')} | {r.get('finish_reason', '-')} | "
            f"{r.get('error') or ''} |"
        )


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--results", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--full", action="store_true",
                    help="also emit the raw per-call table (large)")
    args = ap.parse_args()

    calls, errors = load(args.results)
    by = per_model(calls)
    fixtures = sorted({r["fixture_id"] for r in calls})

    L = ["# DP-357 — every recorded metric\n"]
    L.append("Generated by `metrics_table.py`. **No verdict is expressed here.** "
             "Correctness lives in `score_bakeoff.py` (violations) and `score_recall.py` "
             "(silence); this file is the raw measurement record, so a later question can "
             "be answered without re-running the matrix.\n")
    L.append(f"- calls recorded: **{len(calls)}**")
    L.append(f"- models: **{len(by)}**")
    L.append(f"- error rows (load failures, missing files): **{len(errors)}**\n")

    section_aggregates(L, by)
    section_by_fixture(
        L, by, fixtures, "wall_secs", "Latency by fixture — mean s/call",
        "Fixtures differ in length, so this doubles as a rough prompt-size profile.")
    section_by_fixture(
        L, by, fixtures, "n_facts", "Fact count by fixture — mean",
        "Raw count only: a fact here is anything the model emitted, durable or not, "
        "correct or not. Read it beside the violation and silence tables, never alone -- "
        "a high number is as likely to be narration inflation as coverage.")
    section_load(L, by)
    section_errors(L, errors)
    if args.full:
        section_every_call(L, calls)

    Path(args.out).write_text("\n".join(L) + "\n", encoding="utf-8")
    print(f"wrote {args.out}: {len(calls)} calls, {len(by)} models, {len(errors)} error rows")


if __name__ == "__main__":
    main()

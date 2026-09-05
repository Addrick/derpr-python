"""DP-357: the missing half of the metric — silence.

score_bakeoff.py counts only `must_not_extract` violations, so a model that
extracts NOTHING scores perfectly on every negative fixture. Nine of the ten
fixtures carry a non-empty `must_extract`; the existing gate reads none of them.

That blind spot is not hypothetical. In the power run, granite-4.2-8b Q4_K_M
"won" narrator_attribution 0/10 by emitting zero facts on a fixture whose
must_extract asks for "the substantive technical findings of the session",
while Q8_0 "lost" 10/10 by extracting five and misattributing two. On the gate,
abstention beat imperfect answering.

It is also the failure that actually cost granite in the field: the 2026-05-27
LME A/B (docs/eval_results/lme.md) scored granite-4.1-8b at 33% against
qwen3-30b-a3b's 100%, and two of the three failures were facts granite never
extracted -- a magazine count that had been updated to five, and tabular shift
detail. Adam, 2026-09-01: "failing to extract any fact is almost as bad as
wrong facts."

So this reports both axes side by side:

    silence  = calls that produced zero durable facts on a fixture that
               requires extraction. The recall failure.
    violation= calls that produced a prohibited fact. The precision failure.
    both-ok  = calls that did neither. The only cell that is actually correct.

No single combined number: weighting recall against precision is Adam's call,
not the scorer's, and collapsing them is how the original gate lost the
distinction in the first place.

    python score_recall.py --results results.power.jsonl --fixtures fixtures.json
"""

import argparse
import json
from collections import defaultdict
from pathlib import Path

import score_bakeoff as sb


def load(path):
    out = []
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            out.append(json.loads(line))
        except json.JSONDecodeError:
            continue  # a partial last line from a killed run
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--results", required=True)
    ap.add_argument("--fixtures", required=True)
    ap.add_argument("--out", help="optional markdown output path")
    args = ap.parse_args()

    fixtures = json.loads(Path(args.fixtures).read_text(encoding="utf-8-sig"))
    records = [r for r in load(args.results) if r.get("fixture_id")]

    # per (model, fixture): call outcomes
    cells = defaultdict(lambda: {"calls": 0, "silent": 0, "violating": 0, "durable": 0})
    for rec in records:
        fid, mid = rec["fixture_id"], rec.get("model_id")
        facts = sb.facts_of(rec)
        c = cells[(mid, fid)]
        c["calls"] += 1
        if facts is None:
            continue
        durable = [f for f in facts if not sb.is_narration(f)]
        c["durable"] += len(durable)
        if not durable:
            c["silent"] += 1
        rule = sb.RULES.get(fid)
        if rule and any(rule(f) for f in facts):
            c["violating"] += 1

    models = sorted({m for m, _ in cells})
    fids = [f for f in fixtures if any((m, f) in cells for m in models)]
    requires = {f: bool(fixtures[f].get("must_extract")) for f in fids}

    lines = ["# DP-357 — silence vs violation\n",
             "`silence` = calls returning zero durable facts on a fixture whose "
             "`must_extract` is non-empty (a recall failure the exit criterion cannot see). "
             "`viol` = calls returning a prohibited fact. A fixture with no `must_extract` "
             "(only `dark_roast`) is marked `n/a` for silence — there, silence is correct.\n"]

    header = f"| model | {' | '.join(fids)} |"
    lines += [header, "|" + "---|" * (len(fids) + 1)]
    for m in models:
        row = [f"`{m}`"]
        for f in fids:
            c = cells.get((m, f))
            if not c:
                row.append("-")
                continue
            sil = f"{c['silent']}/{c['calls']}" if requires[f] else "n/a"
            row.append(f"sil {sil} · viol {c['violating']}/{c['calls']}")
        lines.append("| " + " | ".join(row) + " |")

    # the aggregate that matters: how often was a call BOTH silent-free and clean
    lines += ["\n## Per-model totals (fixtures requiring extraction only)\n",
              "| model | calls | silent | violating | clean | silence rate | violation rate |",
              "|---|---|---|---|---|---|---|"]
    for m in models:
        tot = sil = vio = 0
        for f in fids:
            if not requires[f]:
                continue
            c = cells.get((m, f))
            if not c:
                continue
            tot += c["calls"]; sil += c["silent"]; vio += c["violating"]
        if not tot:
            continue
        clean = tot - sil - vio
        lines.append(f"| `{m}` | {tot} | {sil} | {vio} | {clean} | "
                     f"{sil/tot:.0%} | {vio/tot:.0%} |")

    out = "\n".join(lines) + "\n"
    if args.out:
        Path(args.out).write_text(out, encoding="utf-8")
    print(out)


if __name__ == "__main__":
    main()

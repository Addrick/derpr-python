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

⚠️ The per-CALL silence bit below is still all-or-nothing, and Adam 2026-09-04
asked for the finer reading -- "extracting nothing is meaningfully different.
if it excludes only the problematic facts (unlikely) that's technical
improvement. just record what it does exactly." That is what `must_extract.py`
adds and what the last three sections of this report print: per-ITEM hit/miss
on `must_extract`, and a four-way per-call outcome that keeps "omitted only the
problem" apart from "omitted everything". Read those before any ranking.

    python score_recall.py --results results.omen.jsonl --fixtures fixtures.json \
        --out recall.md --out-manual manual_review.jsonl
"""

import argparse
import json
from collections import defaultdict
from pathlib import Path

import must_extract as me
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
    ap.add_argument("--out-manual", help="jsonl dump of the calls whose must_extract "
                                         "item has no honest rule, for hand-reading")
    args = ap.parse_args()

    fixtures = json.loads(Path(args.fixtures).read_text(encoding="utf-8-sig"))
    records = [r for r in load(args.results) if r.get("fixture_id")]

    # per (model, fixture): call outcomes
    cells = defaultdict(lambda: {"calls": 0, "silent": 0, "violating": 0, "durable": 0})
    # per (model, fixture, item index): must_extract hits, and calls where scorable
    item_hits = defaultdict(lambda: {"hit": 0, "scored": 0})
    # per model: the four-way outcome census, over fixtures requiring extraction
    outcomes = defaultdict(lambda: defaultdict(int))
    dp_ids = defaultdict(lambda: {"labelled": 0, "grounded": 0})
    manual = []

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
        violated = bool(rule and any(rule(f) for f in facts))
        if violated:
            c["violating"] += 1

        for i, (item, kind, hit) in enumerate(me.call_items(fid, rec, facts)):
            cell = item_hits[(mid, fid, i)]
            if hit is None:
                continue
            cell["scored"] += 1
            cell["hit"] += bool(hit)
        if any(kind == me.MANUAL for _, kind, _ in me.call_items(fid, rec, facts)):
            manual.append({
                "model_id": mid, "fixture_id": fid, "repeat": rec.get("repeat"),
                "violating": violated,
                "durable_facts": [f for f in facts if not sb.is_narration(f)],
                "narration_facts": [f for f in facts if sb.is_narration(f)],
            })
        if fid == "dp_id_entity":
            lab, gro = me.cross_check_dp_ids(fixtures[fid].get("text", ""), facts)
            dp_ids[mid]["labelled"] += lab
            dp_ids[mid]["grounded"] += gro
        if fixtures.get(fid, {}).get("must_extract"):
            outcomes[mid][me.classify(fid, rec, facts, violated)] += 1

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

    # ---- the finer reading Adam asked for -------------------------------
    lines += ["\n## Per-call outcome — the three outcomes, kept apart\n",
              "The table above cannot tell \"omitted only the problematic facts\" from "
              "\"omitted everything\"; both score as not-violating. This one can. "
              "`covering` = no violation **and** every GATE-scorable `must_extract` item "
              "landed — the real pass. `partial` = answered, no violation, but missed at "
              "least one required item. `silent` = zero durable facts, so the gate saw "
              "nothing to fault. Fixtures with a non-empty `must_extract` only "
              "(`dark_roast` excluded — there silence is the correct answer).\n",
              "| model | calls | violating | covering | partial | silent |",
              "|---|---|---|---|---|---|"]
    for m in models:
        o = outcomes.get(m, {})
        tot = sum(o.values())
        if not tot:
            continue
        lines.append(f"| `{m}` | {tot} | {o.get(me.VIOLATING, 0)} | {o.get(me.COVERING, 0)} | "
                     f"{o.get(me.PARTIAL, 0)} | {o.get(me.SILENT, 0)} |")

    lines += ["\n## `must_extract`, item by item\n",
              "Each `must_extract` entry scored independently, as calls-hit / calls-scored. "
              "**GATE** = a deterministic rule a verdict may rest on. **PROXY** = measures a "
              "correlate, reported but never gated on. **MANUAL** = no honest rule exists; "
              "those calls are dumped to the manual-review file instead of scored, because "
              "inventing a keyword rule for a judgement is what got Phase 0 retracted.\n"]
    for f in fids:
        items = me.ITEMS.get(f, [])
        if not items:
            continue
        lines += [f"\n### `{f}`\n",
                  "| item | kind | " + " | ".join(f"`{m}`" for m in models) + " |",
                  "|---|---|" + "---|" * len(models)]
        for i, (item, kind, _) in enumerate(items):
            cells_ = []
            for m in models:
                h = item_hits.get((m, f, i))
                cells_.append("—" if not h or not h["scored"]
                              else f"{h['hit']}/{h['scored']}")
            lines.append(f"| {item} | {kind} | " + " | ".join(cells_) + " |")

    if any(v["labelled"] for v in dp_ids.values()):
        lines += ["\n## `dp_id_entity` — DP-ID grounding\n",
                  "Facts carrying a DP-ID, and how many of those IDs appear in the source "
                  "chunk at all. An ID the chunk never contains is invented; an ID that is "
                  "present may still be attached to the wrong sentence, which only a human "
                  "can call. Not a gate.\n",
                  "| model | facts with a DP-ID | ID present in chunk |", "|---|---|---|"]
        for m in models:
            d = dp_ids.get(m)
            if d and d["labelled"]:
                lines.append(f"| `{m}` | {d['labelled']} | {d['grounded']} |")

    out = "\n".join(lines) + "\n"
    if args.out:
        Path(args.out).write_text(out, encoding="utf-8")
    if args.out_manual:
        with open(args.out_manual, "w", encoding="utf-8") as fh:
            for row in manual:
                fh.write(json.dumps(row, ensure_ascii=False) + "\n")
    print(out)


if __name__ == "__main__":
    main()

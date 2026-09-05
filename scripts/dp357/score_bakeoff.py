"""DP-357 Phase 0: score results.jsonl, offline.

Scoring is deliberately separate from the run. All data goes to results.jsonl,
so a scoring bug costs a re-score and never a re-run, and every verdict here can
be re-derived from the raw responses that are kept alongside it.

Rules are keyword predicates over each extracted fact rather than an LLM judge:
the failures being measured are lexically obvious (a bare affirmative credential
claim, a benchmark subject's preference attributed to the user), and a
deterministic rule is auditable in a way a judge's opinion is not. Every
violation is written out with the fact that triggered it so the call can be
checked by hand.

Exit criterion, from the plan: a candidate passes if it drops ZERO refutations
across the fixture set AND does not lose extraction coverage versus the control.

    python score_bakeoff.py --results results.jsonl --fixtures fixtures.json \
        --out-summary summary.md --out-violations violations.jsonl
"""

import argparse
import json
from collections import defaultdict
from pathlib import Path

# A fact that repeats the fabricated biography is only acceptable if it also
# carries the refutation. These are the markers that make it a report about the
# fabrication rather than a restatement of it.
REFUTATION_MARKERS = (
    "fabricat", "false", "not true", "untrue", "fixture", "longmemeval",
    "contaminat", "leaked", "leak", "bogus", "incorrect", "misattribut",
    "does not hold", "did not hold", "adversarial", "hallucinat", "spurious",
)

USER_MARKERS = ("user", "adam")


def norm(value):
    if value is None:
        return ""
    if isinstance(value, (list, tuple)):
        return " ".join(norm(v) for v in value)
    if isinstance(value, dict):
        return " ".join(norm(v) for v in value.values())
    return str(value)


def fact_text(fact):
    """Everything the model said about this fact, lowercased, for matching."""
    parts = [fact.get(k) for k in ("what", "when", "where", "who", "why", "context")]
    parts.append(fact.get("entities"))
    return norm(parts).lower()


def has_refutation(text):
    return any(marker in text for marker in REFUTATION_MARKERS)


def violates_cka(fact):
    """The canonical drop: the credential biography asserted without its refutation."""
    text = fact_text(fact)
    claims_bio = ("kubernetes" in text or "cka" in text) and (
        "5 years" in text or "five years" in text or "certif" in text
        or "infrastructure team" in text
    )
    if not claims_bio:
        return None
    if has_refutation(text):
        return None
    return "asserts the CKA/Kubernetes biography with no refutation marker"


def violates_prompt_example(fact):
    """The consolidation prompt's fictional 'Alice' examples treated as events."""
    text = fact_text(fact)
    if "alice" not in text and "acme" not in text:
        return None
    if any(k in text for k in ("long hours", "past midnight", "exhaust", "acme", "senior engineer")):
        if has_refutation(text) or "prompt" in text or "example" in text or "schema" in text:
            return None
        return "extracts a prompt few-shot example about Alice as a real fact"
    return None


FOOD_TERMS = (
    "coffee", "espresso", "roast", "tea", "chai", "rooibos", "brew", "quiche",
    "sandwich", "dessert", "cookie", "shortbread", "parfait", "crepe",
    "dinner party", "peppermint", "chamomile", "hibiscus",
)


def violates_dark_roast(fact):
    """Benchmark-dialogue preferences must not become facts at all here."""
    text = fact_text(fact)
    if not any(term in text for term in FOOD_TERMS):
        return None
    return "extracts a fact from verbatim LongMemEval haystack dialogue"


def violates_narrator(fact):
    """Assistant process narration recorded as a durable fact about the user."""
    text = fact_text(fact)
    narration = any(k in text for k in (
        "started researching", "in parallel", "dispatched", "subagent",
        "began investigating", "spawned",
    ))
    if not narration:
        return None
    who = norm(fact.get("who")).lower() + " " + norm(fact.get("entities")).lower()
    if any(m in who for m in USER_MARKERS) and "claude" not in who and "assistant" not in who:
        return "attributes the assistant's own process narration to the user"
    return None


RULES = {
    "cka_refutation": violates_cka,
    "cka_refutation_b": violates_cka,
    "alice_drift": violates_cka,
    "prompt_example_leak": violates_prompt_example,
    "dark_roast": violates_dark_roast,
    "narrator_attribution": violates_narrator,
}

# Coverage keywords for the positive control: distinct topics a synthesising
# extractor should surface from the optional_personas chunk.
COVERAGE_PROBES = {
    "optional_personas": ("persona", "optional", "config", "default", "bank", "test"),
}

# Turn-by-turn session narration. The retain_mission's IGNORE list rules this out
# explicitly ("one-shot questions, single-session debugging steps, conversational
# filler"), so it is not extraction coverage -- it is the verbosity failure the
# census measured as "61.2% of observations restate one source fact".
#
# This matters because raw fact count is a MISLEADING coverage metric: on
# optional_personas the incumbent emitted 24 facts, of which ~21 were
# "User asked X" / "Claude found Y" narration, while gemma-4-26b-a4b-uncensored
# emitted 5 that were all durable signal. Counting raw facts rewards exactly the
# defect this ticket exists to fix, so coverage is scored on durable facts.
NARRATION_PREFIXES = (
    "user asked", "user requested", "user interrupted", "user confirmed",
    "user approved", "user wants", "user decided to ask", "user told",
    "user said", "user noted", "user pointed out", "user suggested",
    "claude found", "claude confirmed", "claude corrected", "claude explained",
    "claude stated", "claude identified", "claude acknowledged", "claude verified",
    "claude built", "claude applied", "claude wrote", "claude performed",
    "claude ran", "claude checked", "claude started", "assistant asked",
    "assistant confirmed", "assistant explained", "assistant found",
)


def is_narration(fact):
    what = norm(fact.get("what")).strip().lower()
    return any(what.startswith(p) for p in NARRATION_PREFIXES)


def facts_of(record):
    raw = record.get("raw_response")
    if not raw:
        return None
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        return None
    if not isinstance(parsed, dict):
        return None
    facts = parsed.get("facts")
    return facts if isinstance(facts, list) else None


def score(results, fixtures, violations_fh):
    per_model = defaultdict(lambda: {
        "calls": 0, "errors": 0, "invalid_json": 0, "truncated": 0,
        "violations": 0, "violating_calls": 0, "facts": 0,
        "wall": 0.0, "tok_s": [], "load_secs": None, "gpu_layers": None,
        "quant": None, "size_gb": None, "role": None,
        "empty_context": 0, "empty_entities": 0,
        "narration": 0, "durable": 0,
        "per_fixture_facts": defaultdict(list),
        "per_fixture_violations": defaultdict(int),
        "per_fixture_durable": defaultdict(int),
        "coverage_hits": defaultdict(set),
    })

    for rec in results:
        mid = rec.get("model_id")
        stats = per_model[mid]
        stats["role"] = rec.get("model_role") or stats["role"]
        stats["quant"] = rec.get("quant") or stats["quant"]
        stats["size_gb"] = rec.get("size_gb") or stats["size_gb"]
        if rec.get("load_secs") is not None:
            stats["load_secs"] = rec["load_secs"]
        # "Auto Recommended GPU Layers" is koboldcpp's pre-scan guess and reads 0 even for
        # a model that ends up entirely on the card; "offloaded N/M layers" is the truth.
        facts = rec.get("load_facts") or {}
        split = facts.get("offloaded")
        if split:
            stats["gpu_layers"] = split.replace("load_tensors:", "").strip()
        elif facts.get("auto_gpu_layers") and not stats["gpu_layers"]:
            stats["gpu_layers"] = f"auto={facts['auto_gpu_layers']}"

        fid = rec.get("fixture_id")
        if fid is None:  # a load failure / missing-file marker row
            stats["errors"] += 1
            continue

        stats["calls"] += 1
        stats["wall"] += rec.get("wall_secs") or 0
        if rec.get("tok_s"):
            stats["tok_s"].append(rec["tok_s"])
        if rec.get("error"):
            stats["errors"] += 1
            continue
        if rec.get("finish_reason") == "length":
            stats["truncated"] += 1

        facts = facts_of(rec)
        if facts is None:
            stats["invalid_json"] += 1
            continue

        stats["facts"] += len(facts)
        stats["per_fixture_facts"][fid].append(len(facts))
        judge_facts(stats, mid, fid, rec, facts, violations_fh)

    return per_model


def judge_facts(stats, mid, fid, rec, facts, violations_fh):
    """Apply the fixture's rule to every fact, recording each violation."""
    rule = RULES.get(fid)
    call_had_violation = False
    for fact in facts:
        if not fact.get("context"):
            stats["empty_context"] += 1
        if not fact.get("entities"):
            stats["empty_entities"] += 1
        if is_narration(fact):
            stats["narration"] += 1
        else:
            stats["durable"] += 1
            stats["per_fixture_durable"][fid] += 1
        for probe in COVERAGE_PROBES.get(fid, ()):
            if probe in fact_text(fact):
                stats["coverage_hits"][fid].add(probe)
        reason = rule(fact) if rule else None
        if reason:
            stats["violations"] += 1
            stats["per_fixture_violations"][fid] += 1
            call_had_violation = True
            violations_fh.write(json.dumps({
                "model_id": mid, "fixture_id": fid, "repeat": rec.get("repeat"),
                "reason": reason, "fact": fact,
            }, ensure_ascii=False) + "\n")
    if call_had_violation:
        stats["violating_calls"] += 1


# The two failure classes need separating, because they lead to different actions.
#
# REFUTATION_FIXTURES put the disqualifying signal INSIDE the chunk -- the text
# says the claim is false, or is a prompt example. Dropping it is a comprehension
# failure, and a model swap can fix it. This is the plan's exit criterion.
#
# dark_roast carries NO such signal: it is raw benchmark dialogue, and nothing in
# the chunk tells the model it is fixture data. Failing it is not a comprehension
# failure, and no model swap fixes it -- the defense is the ingest-time junk
# filter in Phase 1. Scored and reported, but not part of the exit criterion.
REFUTATION_FIXTURES = (
    "cka_refutation", "cka_refutation_b", "alice_drift",
    "prompt_example_leak", "narrator_attribution",
)
LEAK_FIXTURES = ("dark_roast",)


def split_violations(stats):
    drops = sum(stats["per_fixture_violations"].get(f, 0) for f in REFUTATION_FIXTURES)
    leaks = sum(stats["per_fixture_violations"].get(f, 0) for f in LEAK_FIXTURES)
    return drops, leaks


def verdicts(per_model, control, control_id):
    """Apply the exit criterion: zero refutation drops AND durable coverage held.

    Coverage is measured on DURABLE facts, not raw fact count -- see
    NARRATION_PREFIXES for why raw count rewards the verbosity defect.
    """
    out = []
    ctl_drops, ctl_leaks = split_violations(control) if control else (0, 0)
    for mid, s in sorted(per_model.items()):
        if mid == control_id:
            continue
        drops, leaks = split_violations(s)
        coverage_ok = bool(control and control["durable"] and s["durable"] >= 0.8 * control["durable"])
        if drops == 0 and coverage_ok:
            verdict = "**PASSES the exit criterion** — zero refutation drops, durable coverage held"
        elif drops == 0:
            verdict = (f"zero refutation drops, but durable coverage is "
                       f"{s['durable'] / control['durable']:.2f}x the control — check whether that is "
                       f"conservatism or the control's narration being counted as coverage")
        else:
            verdict = f"fails — {drops} refutation drops"
        leak_note = f" · fixture-leak (dark_roast) {leaks} vs control {ctl_leaks}"
        out.append(f"- `{mid}`: {verdict}{leak_note}")
    return out


def render(per_model, fixtures, control_id):
    control = per_model.get(control_id)
    lines = []
    lines.append("# DP-357 Phase 0 — bake-off results\n")
    lines.append("Exit criterion: **zero dropped refutations** across the fixture set **and** no ")
    lines.append("loss of extraction coverage versus the control. Nothing passes => stop and ")
    lines.append("reconsider; do not ship the least-bad.\n")
    lines.append(f"Control: `{control_id}`\n")

    lines.append("\n## Summary\n")
    lines.append("`drops` = refutation drops, the exit criterion. `leak` = dark_roast, reported "
                 "separately because nothing in that chunk signals it is fixture data, so no model "
                 "swap fixes it (Phase 1's junk filter does).\n")
    lines.append("| model | role | quant | GB | gpu_layers | calls | **drops** | leak | "
                 "durable facts | raw facts | invalid JSON | truncated | errors | mean tok/s | mean s/call |")
    lines.append("|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|")
    ordered = sorted(per_model.items(), key=lambda kv: (split_violations(kv[1])[0], -kv[1]["durable"]))
    for mid, s in ordered:
        tok = sum(s["tok_s"]) / len(s["tok_s"]) if s["tok_s"] else 0
        secs = s["wall"] / s["calls"] if s["calls"] else 0
        drops, leaks = split_violations(s)
        lines.append(
            f"| `{mid}` | {s['role']} | {s['quant']} | {s['size_gb']} | {s['gpu_layers']} | "
            f"{s['calls']} | **{drops}** | {leaks} | {s['durable']} | {s['facts']} | "
            f"{s['invalid_json']} | {s['truncated']} | {s['errors']} | {tok:.1f} | {secs:.1f} |"
        )

    lines.append("\n## Violations by fixture\n")
    fixture_ids = [f for f in fixtures if f in RULES]
    lines.append("| model | " + " | ".join(f"`{f}`" for f in fixture_ids) + " |")
    lines.append("|---" * (len(fixture_ids) + 1) + "|")
    for mid, s in sorted(per_model.items()):
        cells = " | ".join(str(s["per_fixture_violations"].get(f, 0)) for f in fixture_ids)
        lines.append(f"| `{mid}` | {cells} |")

    lines.append("\n## Coverage — the positive controls\n")
    lines.append("`dark_roast` must yield **nothing**; `optional_personas` must yield real "
                 "multi-fact synthesis. A model that scores well everywhere else by extracting "
                 "almost nothing fails here.\n")
    lines.append("⚠️ **Coverage is scored on durable facts, not raw fact count.** On "
                 "`optional_personas` the incumbent emitted 24 facts of which ~21 were "
                 "\"User asked X\" / \"Claude found Y\" turn narration — which the "
                 "retain_mission's IGNORE list rules out — while a candidate emitted 5 that were "
                 "all durable signal. Raw count rewards exactly the verbosity defect this ticket "
                 "exists to fix.\n")
    lines.append("| model | dark_roast facts | optional_personas facts | probes hit | narration % | "
                 "raw facts vs control | **durable vs control** |")
    lines.append("|---|---|---|---|---|---|---|")
    for mid, s in sorted(per_model.items()):
        dr = s["per_fixture_facts"].get("dark_roast", [])
        op = s["per_fixture_facts"].get("optional_personas", [])
        probes = len(s["coverage_hits"].get("optional_personas", set()))
        narr = 100 * s["narration"] / s["facts"] if s["facts"] else 0
        raw = f"{s['facts'] / control['facts']:.2f}x" if control and control["facts"] else ""
        dur = f"**{s['durable'] / control['durable']:.2f}x**" if control and control["durable"] else ""
        lines.append(
            f"| `{mid}` | {sum(dr) / len(dr) if dr else 0:.1f} | "
            f"{sum(op) / len(op) if op else 0:.1f} | {probes}/6 | {narr:.0f}% | {raw} | {dur} |"
        )

    lines.append("\n## Verdict\n")
    lines.extend(verdicts(per_model, control, control_id))

    lines.append("\n## Base-prompt confound\n")
    lines.append("Hindsight's built-in prompt, which no mission can edit, carries a COREFERENCE ")
    lines.append("RESOLUTION section and the line \"Always include 'user' when fact is about the ")
    lines.append("user\", and the retain_mission renders *above* it — our ATTRIBUTION RULES speak ")
    lines.append("first, the vendor's text speaks last. Read the CKA columns against that:\n")
    cka_fixtures = ["cka_refutation", "cka_refutation_b", "alice_drift"]
    failing = [m for m, s in per_model.items()
               if sum(s["per_fixture_violations"].get(f, 0) for f in cka_fixtures) > 0]
    if len(failing) == len(per_model):
        lines.append("- **Every model fails the CKA fixtures** => the base prompt is the binding "
                     "constraint. No swap helps; the levers are `retain_custom_instructions` and "
                     "`retain_extraction_mode`.")
    elif failing:
        lines.append("- **Some models pass, some fail** => the base prompt is an obstacle models "
                     "differ at clearing. This is the most useful outcome: it names a winner *and* "
                     "explains the mechanism.")
        lines.append(f"- Failing: {', '.join(sorted(failing))}")
    else:
        lines.append("- **All models pass** => the incumbent's finetune is the whole story.")

    return "\n".join(lines) + "\n"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--results", required=True)
    ap.add_argument("--fixtures", required=True)
    ap.add_argument("--out-summary", required=True)
    ap.add_argument("--out-violations", required=True)
    ap.add_argument("--control", default="incumbent-qwen3.6-35b-a3b-uncensored")
    args = ap.parse_args()

    results = []
    with open(args.results, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                results.append(json.loads(line))
            except json.JSONDecodeError:
                continue  # partial last line from a killed run
    fixtures = json.loads(Path(args.fixtures).read_text(encoding="utf-8"))

    with open(args.out_violations, "w", encoding="utf-8") as vf:
        per_model = score(results, fixtures, vf)

    summary = render(per_model, fixtures, args.control)
    Path(args.out_summary).write_text(summary, encoding="utf-8")
    print(summary)


if __name__ == "__main__":
    main()

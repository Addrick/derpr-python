"""DP-357: per-item hit/miss on `must_extract`.

score_recall.py answers "did this call go silent" as one all-or-nothing bit per
call. Adam, 2026-09-04:

    "extracting nothing is meaningfully different. if it excludes only the
     problematic facts (unlikely) that's technical improvement. just record
     what it does exactly."

An aggregate silence rate cannot tell those apart, because it collapses two of
the three outcomes that matter:

    emits the biography            -> a must_not violation. The failure.
    omits ONLY the problematic bit -> no violation AND the must_extract items
                                      still land. The real pass.
    omits everything               -> no violation because it said nothing.
                                      Uninformative, and the gate cannot see it.

So this module scores each `must_extract` entry independently, per call.

## Why some items are deliberately not scored

The `must_extract` entries are natural-language acceptance criteria written for
a human, not match strings. Some are lexically decidable ("the bank contains
174 fabricated credential records" -> the string 174 is present or it is not);
some are judgements ("the substantive technical findings of the session").

Inventing a keyword rule for a judgement is exactly the move that got Phase 0
retracted -- a one-sided gate that read like a measurement. So each item carries
how far it can be trusted, and the untrusted ones are reported as evidence
rather than as a score:

    GATE    a deterministic rule a verdict may rest on.
    PROXY   a defensible rule that measures a correlate, not the criterion.
            Reported, never gated on.
    MANUAL  no honest rule exists. The durable facts are dumped for reading.

Nothing here ranks models. It reports what each one did.
"""

import re

import score_bakeoff as sb

GATE, PROXY, MANUAL = "GATE", "PROXY", "MANUAL"


def _all(*needles):
    return lambda t: all(n in t for n in needles)


def _any(*needles):
    return lambda t: any(n in t for n in needles)


def _and(*preds):
    return lambda t: all(p(t) for p in preds)


# The markers that turn a restatement of the fabricated biography into a report
# ABOUT it. Shared with score_bakeoff.violates_cka deliberately: the same signal
# that exonerates a violation is the hit for "said it was fabricated".
_refuted = sb.has_refutation

_DATE_OR_SUPERSESSION = re.compile(
    r"20\d\d-\d\d-\d\d|supersed|no longer|previously|used to|moved to|as of|earlier|since"
)

# fixture_id -> [(item text as written in fixtures.json, kind, predicate over
#                 the joined text of the call's DURABLE facts)]
ITEMS = {
    "cka_refutation": [
        ("the mission / ATTRIBUTION RULES did not hold on the re-ingest", GATE,
         _and(_any("mission", "attribution rule", "attribution_rule"),
              _any("did not hold", "does not hold", "didn t hold", "not hold",
                   "fail", "ignored", "violat", "breach", "ineffective",
                   "no effect", "not enforced", "did not work"))),
        ("the re-ingested session produced 58 facts, up from 2", GATE,
         _any("58")),
        ("the CKA/Kubernetes biography is fabricated", GATE,
         _and(_any("cka", "kubernetes"), _refuted)),
    ],
    "cka_refutation_b": [
        ("the SessionEnd transcript is an adversarial test of the fixed mission", GATE,
         lambda t: "adversarial" in t or ("sessionend" in t and "test" in t)),
        ("config PATCH requires an updates envelope", GATE,
         _and(_any("updates"), _any("envelope", "patch"))),
        ("entity_labels values must be objects, not strings", GATE,
         _and(_any("entity_labels", "entity labels"), _any("object", "string"))),
    ],
    "alice_drift": [
        ("the bank contains 174 fabricated credential records", GATE,
         _any("174")),
        ("the fabrication originates in a LongMemEval fixture named Alice "
         "leaked from .eval_cache", GATE,
         _and(_any("alice"), _any("longmemeval", "eval_cache", "eval cache",
                                  "long mem eval"))),
        ("all three drift generations are stored: Alice has -> User has -> Adam has", GATE,
         _and(_all("alice", "user", "adam"),
              _any("drift", "generation", "three", "propagat", "rewrit"))),
    ],
    "prompt_example_leak": [
        ("a Hindsight consolidation prompt and its JSON schema appear in the "
         "session output", GATE,
         _and(_any("prompt", "schema"), _any("consolidat", "hindsight"))),
    ],
    "stale_ct_gpu": [
        ("which container holds the GPU, with the date or the supersession "
         "made explicit", GATE,
         _and(_any("gpu"),
              _any("ct100", "ct101", "ct 100", "ct 101", "container"),
              lambda t: bool(_DATE_OR_SUPERSESSION.search(t)))),
    ],
    # "the substantive technical findings of the session" is a judgement, not a
    # string. The probe below measures whether the call was ON TOPIC at all,
    # which is a correlate of coverage and nothing more.
    "narrator_attribution": [
        ("the substantive technical findings of the session", MANUAL, None),
        ("[probe] on-topic: names the fixr dispatch / sandbox reachability problem",
         PROXY,
         _and(_any("fixr", "dispatch", "subagent", "agent"),
              _any("docker", "sandbox", "network", "cloudflared", "zammad", "reach"))),
    ],
    # "facts whose ticket label matches the DP-ID actually discussed in that
    # sentence" is a per-fact correctness property, not a call-level item. It is
    # measured by cross_check_dp_ids() against the chunk, and is the mirror of
    # the must_not rule -- never a coverage gate.
    "dp_id_entity": [
        ("facts whose ticket label matches the DP-ID actually discussed in "
         "that sentence", MANUAL, None),
    ],
    # Decided on the record, not on the fact text -- see call_items().
    "json_overrun_dense": [
        ("valid JSON conforming to the schema, no truncation", GATE, None),
    ],
    "optional_personas": [
        ("multiple distinct, genuinely synthesised facts about the "
         "optional-personas work", PROXY, None),
    ],
    "dark_roast": [],
}


def durable_text(facts):
    """Joined text of the call's durable facts. Narration is not coverage."""
    return " ".join(sb.fact_text(f) for f in facts if not sb.is_narration(f))


def call_items(fixture_id, record, facts):
    """[(item, kind, hit|None)] for one call. None = not scorable for this call."""
    out = []
    text = durable_text(facts or [])
    durable = [f for f in (facts or []) if not sb.is_narration(f)]
    for item, kind, pred in ITEMS.get(fixture_id, []):
        if fixture_id == "json_overrun_dense":
            hit = bool(record.get("valid_json")) and record.get("finish_reason") != "length"
        elif fixture_id == "optional_personas" and pred is None:
            probes = {p for p in sb.COVERAGE_PROBES["optional_personas"] if p in text}
            hit = len(durable) >= 2 and len(probes) >= 3
        elif pred is None:
            hit = None
        else:
            hit = bool(pred(text))
        out.append((item, kind, hit))
    return out


DP_ID = re.compile(r"\bDP-\d{2,4}\b", re.I)


def cross_check_dp_ids(chunk_text, facts):
    """(labelled, grounded) -- facts carrying a DP-ID, and how many of those IDs
    actually appear in the source chunk. A fact tagged with an ID the chunk never
    contains is invented outright; one whose ID is present may still be
    misattributed, which only a human can call."""
    in_chunk = {m.upper() for m in DP_ID.findall(chunk_text or "")}
    labelled = grounded = 0
    for f in facts or []:
        ids = {m.upper() for m in DP_ID.findall(sb.fact_text(f))}
        if not ids:
            continue
        labelled += 1
        if ids <= in_chunk:
            grounded += 1
    return labelled, grounded


# The three outcomes Adam asked to keep apart, plus the one a bare three-way
# split silently merges into "pass": answered, but missed the required content.
VIOLATING, COVERING, PARTIAL, SILENT = "violating", "covering", "partial", "silent"


def classify(fixture_id, record, facts, violated):
    if violated:
        return VIOLATING
    durable = [f for f in (facts or []) if not sb.is_narration(f)]
    gates = [hit for _, kind, hit in call_items(fixture_id, record, facts)
             if kind == GATE and hit is not None]
    if not durable and fixture_id != "json_overrun_dense":
        return SILENT
    if not gates:
        return COVERING if durable else SILENT
    return COVERING if all(gates) else PARTIAL

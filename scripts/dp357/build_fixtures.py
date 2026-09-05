"""DP-357: assemble the Phase 0 fixture set.

Ten fixtures covering every known-bad extraction example plus two positive
controls. Nine are chunks that were actually fed to the extractor in
production, pulled live from the claudecode bank so the harness scores the real
input rather than a paraphrase of it. One is verbatim LongMemEval haystack
content -- the class of text that contaminated the bank in the first place.

Each fixture carries a hand-drafted label:
  must_extract      -- claims a faithful extractor is expected to produce
  must_not_extract  -- claims that are the observed failure; producing any of
                       these is a refutation drop or a misattribution
  justification     -- why the label is what it is, grounded in the census and
                       the DP-336 notes rather than in a fresh reading

Run with the bank reachable; writes fixtures.json next to this file.
"""

import json
import urllib.parse
import urllib.request
from pathlib import Path

BASE = "http://10.0.0.70:8888/v1/default/banks/claudecode"
HERE = Path(__file__).parent
OUT = HERE / "fixtures.json"

# fixture id -> (session prefix, chunk_index)
BANK_SOURCES = {
    "cka_refutation": ("e736fb03", 1),
    "cka_refutation_b": ("e736fb03", 0),
    "alice_drift": ("323fcc80", 3),
    "prompt_example_leak": ("2746c8ba", 6),
    "stale_ct_gpu": ("3f963542", 4),
    "narrator_attribution": ("b48bef8a", 0),
    "dp_id_entity": ("fcc3882b", 5),
    "json_overrun_dense": ("b3523de2", 2),
    "optional_personas": ("4d6d256b", 1),
}

LABELS = {
    "cka_refutation": {
        "role": "negative",
        "scores": ["refutation_survival", "attribution"],
        "must_extract": [
            "the mission / ATTRIBUTION RULES did not hold on the re-ingest",
            "the re-ingested session produced 58 facts, up from 2",
            "the CKA/Kubernetes biography is fabricated",
        ],
        "must_not_extract": [
            "Adam has 5 years of Kubernetes experience",
            "Adam holds CKA certification",
            "Adam leads the infrastructure team since March",
            "User has 5 years of Kubernetes experience",
        ],
        "justification": (
            "The canonical case. The chunk quotes the fabricated sentence inside a code fence and "
            "the very next sentence says it was 'Extracted bare and affirmative from a transcript "
            "whose surrounding text says it is fabricated'. Emitting the quoted sentence as a "
            "standalone affirmative fact is a refutation drop by definition."
        ),
    },
    "cka_refutation_b": {
        "role": "negative",
        "scores": ["refutation_survival", "attribution"],
        "must_extract": [
            "the SessionEnd transcript is an adversarial test of the fixed mission",
            "config PATCH requires an updates envelope",
            "entity_labels values must be objects, not strings",
        ],
        "must_not_extract": [
            "Adam has 5 years of Kubernetes experience",
            "Adam holds CKA certification",
        ],
        "justification": (
            "Same session, the chunk that names the fabrication without quoting it in full ('the "
            "transcript contains the fabricated CKA sentence wrapped in text saying it is false'). "
            "Pairs with cka_refutation to separate 'drops the refutation around a quote' from "
            "'invents the quote from a description of it'."
        ),
    },
    "alice_drift": {
        "role": "negative",
        "scores": ["refutation_survival", "attribution"],
        "must_extract": [
            "the bank contains 174 fabricated credential records",
            "the fabrication originates in a LongMemEval fixture named Alice leaked from .eval_cache",
            "all three drift generations are stored: Alice has -> User has -> Adam has",
        ],
        "must_not_extract": [
            "Adam has 5 years of Kubernetes experience",
            "Adam holds CKA certification",
            "Adam leads the infrastructure team since March",
            "Alice has 5 years of Kubernetes experience",
        ],
        "justification": (
            "The chunk blockquotes the fabricated sentence and immediately follows it with 'All "
            "false.' plus the provenance. Census: 174 records, 2026-04-21 to 2026-08-20. A model "
            "that re-emits the blockquote as fact is re-seeding the contamination the chunk is "
            "documenting."
        ),
    },
    "prompt_example_leak": {
        "role": "negative",
        "scores": ["attribution"],
        "must_extract": [
            "a Hindsight consolidation prompt and its JSON schema appear in the session output",
        ],
        "must_not_extract": [
            "Alice works long hours, often past midnight",
            "Alice is exhausted from project deadlines",
            "Alice works at Acme Corp as a senior engineer",
            "User works long hours",
        ],
        "justification": (
            "This chunk is a captured Hindsight consolidation prompt whose few-shot examples are "
            "about a fictional 'Alice'. They are prompt scaffolding, not events. Extracting them "
            "is the fixture-leak failure one layer up, and the mission's 'never attribute quoted "
            "text, sample or benchmark data' clause covers it explicitly."
        ),
    },
    "stale_ct_gpu": {
        "role": "negative",
        "scores": ["contradiction_handling"],
        "must_extract": [
            "which container holds the GPU, with the date or the supersession made explicit",
        ],
        "must_not_extract": [
            "two contradictory GPU-ownership claims both stated bare and undated",
        ],
        "justification": (
            "Census case 4: rank 0 was five weeks stale and rank 5 its direct contradiction, from "
            "the same document, neither marked superseded. A faithful extractor either dates the "
            "claim or states the supersession; emitting both bare is the observed defect."
        ),
    },
    "narrator_attribution": {
        "role": "negative",
        "scores": ["attribution"],
        "must_extract": [
            "the substantive technical findings of the session",
        ],
        "must_not_extract": [
            "narration of the assistant's own process attributed to the user",
            "Claude started researching in parallel, as a durable fact about the user",
        ],
        "justification": (
            "Census case 5. The mission says 'Attribute code suggestions and analyses to Claude' "
            "and the base prompt supplies a Narrator hint. Process narration is not durable signal "
            "under the mission's IGNORE list either way."
        ),
    },
    "dp_id_entity": {
        "role": "negative",
        "scores": ["entity_correctness"],
        "must_extract": [
            "facts whose ticket label matches the DP-ID actually discussed in that sentence",
        ],
        "must_not_extract": [
            "a fact tagged with a DP-ID that appears elsewhere in the chunk but not in that fact",
        ],
        "justification": (
            "Census: 51.4% of 356 DP-tagged facts carry the wrong ticket. This chunk mentions seven "
            "distinct DP-IDs, so a resolution error is both likely and visible. entity_labels "
            "constrains the vocabulary to a closed set but not the resolution."
        ),
    },
    "json_overrun_dense": {
        "role": "negative",
        "scores": ["json_validity", "throughput"],
        "must_extract": ["valid JSON conforming to the schema, no truncation"],
        "must_not_extract": ["finish_reason=length, malformed JSON, or a retry"],
        "justification": (
            "DP-336 hit a 47,278-char response with finish_reason: length, invalid JSON and four "
            "retries. This is the densest chunk in the bank, at the 6000-char cap -- the shape that "
            "triggers structured-output overrun. Scored on adherence, not content."
        ),
    },
    "optional_personas": {
        "role": "positive_control",
        "scores": ["coverage"],
        "must_extract": [
            "multiple distinct, genuinely synthesised facts about the optional-personas work",
        ],
        "must_not_extract": [],
        "justification": (
            "The bank's best record -- real multi-fact synthesis. This is the coverage control: a "
            "model that scores well on every negative fixture by extracting almost nothing must "
            "fail here, which is how 'more faithful' is told apart from 'more conservative'."
        ),
    },
    "dark_roast": {
        "role": "positive_control",
        "scores": ["attribution", "coverage"],
        "must_extract": [],
        "must_not_extract": [
            "any coffee, tea or food preference attributed to the user or to Adam",
            "any claim about a dinner party, brewing method or roast preference as the user's",
        ],
        "justification": (
            "Verbatim LongMemEval haystack dialogue -- the exact class of text that leaked via "
            ".eval_cache. 'dark roast' produced 0 hits in the census, so the incumbent already "
            "passes this one; a model that hallucinates here is strictly worse than the incumbent. "
            "Yielding nothing is the correct answer."
        ),
    },
}


def api(path):
    return json.loads(urllib.request.urlopen(BASE + path, timeout=180).read())


def chunks_for(document_id):
    return api("/documents/" + urllib.parse.quote(document_id, safe="") + "/chunks")["items"]


def main():
    docs = api("/documents?limit=1000")["items"]
    fixtures = {}

    for fid, (sess, idx) in BANK_SOURCES.items():
        hit = [d for d in docs if sess in (d.get("id") or d["document_id"])]
        if not hit:
            raise SystemExit(f"no document for session {sess} (fixture {fid})")
        doc = hit[0]
        did = doc.get("id") or doc["document_id"]
        chunks = {c["chunk_index"]: c["chunk_text"] for c in chunks_for(did)}
        if idx not in chunks:
            raise SystemExit(f"{fid}: chunk {idx} missing from {did} (have {sorted(chunks)})")
        rp = doc.get("retain_params") or {}
        meta = rp.get("metadata") or doc.get("document_metadata") or {}
        fixtures[fid] = {
            "source": "bank_chunk",
            "document_id": did,
            "chunk_index": idx,
            "total_chunks": len(chunks),
            "text": chunks[idx],
            "event_date": rp.get("event_date") or meta.get("session_start"),
            "metadata": meta,
            **LABELS[fid],
        }

    # dark_roast is not in the bank (it correctly produced zero facts), so it is
    # sourced from the contaminating dataset itself.
    raw = (HERE / "_darkroast_raw.txt").read_text(encoding="utf-8")
    fixtures["dark_roast"] = {
        "source": "longmemeval_haystack",
        "document_id": "longmemeval_s_cleaned.json",
        "chunk_index": 0,
        "total_chunks": 1,
        "text": raw,
        "event_date": "2026-08-20T00:00:00+00:00",
        "metadata": {"project": "C--Users-Adam-Programming-Python-derpr-python"},
        **LABELS["dark_roast"],
    }

    OUT.write_text(json.dumps(fixtures, indent=1, ensure_ascii=False), encoding="utf-8")
    for fid, fx in fixtures.items():
        print(f"{fid:22} {fx['role']:16} len={len(fx['text']):5} {fx['document_id'][:40]}#{fx['chunk_index']}")
    print(f"\n{len(fixtures)} fixtures -> {OUT}")


if __name__ == "__main__":
    main()

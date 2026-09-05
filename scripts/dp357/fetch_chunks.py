"""DP-357: pull candidate fixture chunks out of the live claudecode bank.

Searches the bank for each fixture's signature phrase, then downloads the full
chunk text of the documents behind the hits. Writes one JSON per fixture id to
--out so the chunks can be hand-picked and labelled.
"""
import argparse
import json
import urllib.parse
import urllib.request
from pathlib import Path

BASE = "http://10.0.0.70:8888/v1/default/banks/claudecode"

# fixture id -> recall query used to find the document that carries it
QUERIES = {
    "cka_refutation": "fabricated CKA Kubernetes biography extracted bare and affirmative",
    "alice_drift": "Alice has 5 years of Kubernetes experience leads infrastructure team",
    "dark_roast": "dark roast coffee preference",
    "narrator_attribution": "Claude started researching in parallel subagents dispatched",
    "optional_personas": "optional_personas persona configuration optional",
    "stale_ct_gpu": "which CT holds the GPU passthrough CT101 CT100",
    "json_overrun": "finish_reason length invalid JSON 47278 chars retries",
}


def post(path, payload):
    req = urllib.request.Request(
        BASE + path,
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"},
    )
    return json.loads(urllib.request.urlopen(req, timeout=180).read())


def get(path):
    return json.loads(urllib.request.urlopen(BASE + path, timeout=120).read())


def chunks_for(document_id):
    return get("/documents/" + urllib.parse.quote(document_id, safe="") + "/chunks")["items"]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--limit", type=int, default=15)
    args = ap.parse_args()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    for fid, query in QUERIES.items():
        try:
            res = post("/memories/recall", {"query": query, "limit": args.limit})
        except Exception as exc:  # network / server hiccup shouldn't kill the sweep
            print(f"{fid}: recall FAILED {exc}")
            continue
        docs, seen = [], set()
        for hit in res.get("results") or []:
            did = hit.get("document_id")
            if did and did not in seen:
                seen.add(did)
                docs.append(did)
        record = {"fixture_id": fid, "query": query, "documents": []}
        for did in docs[:6]:
            try:
                items = chunks_for(did)
            except Exception as exc:
                print(f"{fid}: chunks FAILED {did}: {exc}")
                continue
            record["documents"].append(
                {
                    "document_id": did,
                    "chunks": [
                        {"chunk_index": c["chunk_index"], "text": c["chunk_text"]}
                        for c in sorted(items, key=lambda x: x["chunk_index"])
                    ],
                }
            )
        (out / f"{fid}.json").write_text(json.dumps(record, indent=1, ensure_ascii=False), encoding="utf-8")
        total = sum(len(d["chunks"]) for d in record["documents"])
        print(f"{fid}: {len(record['documents'])} docs, {total} chunks")


if __name__ == "__main__":
    main()

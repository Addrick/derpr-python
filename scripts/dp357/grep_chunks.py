"""DP-357: dump/search chunks of specific claudecode-bank documents by substring."""
import argparse
import json
import urllib.parse
import urllib.request

BASE = "http://10.0.0.70:8888/v1/default/banks/claudecode"


def chunks_for(document_id):
    url = BASE + "/documents/" + urllib.parse.quote(document_id, safe="") + "/chunks"
    return json.loads(urllib.request.urlopen(url, timeout=120).read())["items"]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--session", action="append", required=True, help="session id prefix, e.g. 323fcc80")
    ap.add_argument("--pattern", action="append", required=True)
    ap.add_argument("--context", type=int, default=400)
    ap.add_argument("--dump", help="write matching chunk text to this file")
    args = ap.parse_args()

    docs = json.loads(urllib.request.urlopen(BASE + "/documents?limit=1000", timeout=120).read())
    items = docs["items"] if isinstance(docs, dict) else docs
    ids = [d.get("id") or d["document_id"] for d in items]

    for sess in args.session:
        matches = [i for i in ids if sess in i]
        if not matches:
            print(f"!! no document for session {sess}")
            continue
        for did in matches:
            for c in sorted(chunks_for(did), key=lambda x: x["chunk_index"]):
                text = c["chunk_text"]
                for pat in args.pattern:
                    if pat.lower() in text.lower():
                        idx = text.lower().find(pat.lower())
                        print(f"\n=== {sess}#{c['chunk_index']} len={len(text)} pat={pat!r}")
                        print(text[max(0, idx - args.context):idx + args.context])
                        if args.dump:
                            with open(args.dump, "a", encoding="utf-8") as fh:
                                fh.write(json.dumps({"document_id": did, "chunk_index": c["chunk_index"], "text": text}, ensure_ascii=False) + "\n")
                        break


if __name__ == "__main__":
    main()

"""Does koboldcpp's OpenAI-compat endpoint honour `seed`?

Reproducibility needs both halves: nofastforward kills the prompt-cache path
dependence, and a fixed seed would kill the sampler. koboldcpp's native API takes
`sampler_seed`; whether /v1/chat/completions maps `seed` onto it is undocumented
here, so test rather than assume. Two identical calls with the same seed must
return byte-identical content; a control pair without a seed should differ (or at
least is not required to match).
"""
import json, sys, urllib.request

PORT = 5099
BASE = f"http://127.0.0.1:{PORT}"

def call(body):
    req = urllib.request.Request(BASE + "/v1/chat/completions",
                                 data=json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=900) as r:
        d = json.loads(r.read())
    return (d.get("choices") or [{}])[0].get("message", {}).get("content")

bodies = json.load(open("bodies.disputed.json", encoding="utf-8-sig"))["bodies"]
base = dict(bodies["dark_roast"])

for field in ("seed", "sampler_seed"):
    b = dict(base); b[field] = 1234
    try:
        a1, a2 = call(b), call(b)
    except Exception as exc:
        print(f"{field}: request failed -- {type(exc).__name__}: {exc}"); continue
    print(f"{field}=1234 -> {'IDENTICAL' if a1 == a2 else 'DIFFERENT'} "
          f"(len {len(a1 or '')} vs {len(a2 or '')})")

n1, n2 = call(base), call(base)
print(f"no seed (control) -> {'identical' if n1 == n2 else 'different'}")

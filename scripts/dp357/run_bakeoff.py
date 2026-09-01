"""DP-357 Phase 0: the extraction bake-off runner. Runs on dt21.

For each candidate model: generate a .kcpps from a known-good template with only
the model path, port and a few bench-specific knobs changed, launch koboldcpp,
wait for it to serve, replay every fixture N times through the REAL Hindsight
extraction request body (built by build_bodies.py inside the running container),
record everything to JSONL, then shut the server down and move to the next model.

Nothing is scored here. Adam's requirement is that all data goes to a file, so
scoring happens offline against results.jsonl and a scoring bug never costs a
re-run.

results.jsonl doubles as the checkpoint: a (model_id, fixture_id, repeat) already
present is skipped, so a killed run resumes instead of restarting.

    python run_bakeoff.py --bodies bodies.json --models models.json \
        --template tmpl.kcpps --out results.jsonl --repeats 3
"""

import argparse
import json
import subprocess
import sys
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

KOBOLD_EXE = r"F:\Machine Learning\koboldcpp\koboldcpp.exe"
PORT = 5099
BASE = f"http://127.0.0.1:{PORT}"


def now():
    return datetime.now(timezone.utc).isoformat()


def log(msg):
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


def http_json(url, payload=None, timeout=900):
    data = json.dumps(payload).encode() if payload is not None else None
    headers = {"Content-Type": "application/json"} if data else {}
    req = urllib.request.Request(url, data=data, headers=headers)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read())


def write_kcpps(template, model_path, dest, contextsize, genamt):
    cfg = json.loads(Path(template).read_text(encoding="utf-8"))
    cfg["model_param"] = model_path
    cfg["model"] = []
    cfg["port"] = PORT
    cfg["port_param"] = PORT
    cfg["contextsize"] = contextsize
    cfg["defaultgenamt"] = genamt
    # bench-specific, applied identically to every candidate so comparisons hold:
    cfg["smartcache"] = 0      # Hindsight sends one-shots; the 510x series gets no smartcache
    cfg["usemlock"] = False    # models are loaded and unloaded repeatedly
    cfg["gpulayers"] = -1      # let koboldcpp autofit each model to the 16 GB card
    cfg["autofit"] = True
    cfg["autofitpadding"] = 512
    cfg["multiuser"] = 1
    cfg["launch"] = False
    cfg["showgui"] = False
    cfg["skiplauncher"] = True
    cfg["config"] = None
    Path(dest).write_text(json.dumps(cfg, indent=1), encoding="utf-8")
    return cfg


def wait_ready(proc, timeout):
    """Poll until koboldcpp serves, or the process dies, or we run out of patience."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        if proc.poll() is not None:
            return False, f"koboldcpp exited with code {proc.returncode} during load"
        try:
            info = http_json(BASE + "/api/v1/model", timeout=10)
            return True, info.get("result", "")
        except Exception:
            time.sleep(5)
    return False, f"not ready after {timeout}s"


def shutdown(proc):
    if proc.poll() is not None:
        return
    proc.terminate()
    try:
        proc.wait(timeout=60)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.wait(timeout=60)


def parse_load_log(path):
    """Pull the offload split and layer count out of koboldcpp's own load output."""
    facts = {}
    try:
        text = Path(path).read_text(encoding="utf-8", errors="replace")
    except OSError:
        return facts
    for line in text.splitlines():
        stripped = line.strip()
        if "Auto Recommended GPU Layers:" in stripped:
            facts["auto_gpu_layers"] = stripped.split(":")[-1].strip()
        elif stripped.startswith("load_tensors:") and "buffer size" in stripped:
            facts.setdefault("buffer_sizes", []).append(stripped)
        elif "offloaded" in stripped and "layers to GPU" in stripped:
            facts["offloaded"] = stripped
        elif stripped.startswith("print_info: file size"):
            facts["file_size"] = stripped.split("=", 1)[-1].strip()
        elif stripped.startswith("print_info: arch"):
            facts["arch"] = stripped.split("=", 1)[-1].strip()
    return facts


def done_keys(out_path):
    done = set()
    if not Path(out_path).exists():
        return done
    with open(out_path, encoding="utf-8") as fh:
        for line in fh:
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                continue  # a partial last line from a killed run
            done.add((rec.get("model_id"), rec.get("fixture_id"), rec.get("repeat")))
    return done


def do_call(model, bodies, fid, args):
    """One extraction call. Returns the record fields describing what came back."""
    body = dict(bodies[fid])
    body["model"] = model.get("served_name") or model["id"]
    t0 = time.time()
    error = raw = None
    try:
        resp = http_json(BASE + "/v1/chat/completions", body, timeout=args.call_timeout)
    except Exception as exc:
        resp, error = None, f"{type(exc).__name__}: {exc}"
    elapsed = round(time.time() - t0, 2)

    finish_reason = usage = None
    if resp:
        choice = (resp.get("choices") or [{}])[0]
        raw = (choice.get("message") or {}).get("content")
        finish_reason = choice.get("finish_reason")
        usage = resp.get("usage")

    valid_json, n_facts = None, None
    if raw is not None:
        try:
            parsed = json.loads(raw)
            valid_json = True
            n_facts = len(parsed.get("facts") or []) if isinstance(parsed, dict) else None
        except json.JSONDecodeError:
            valid_json = False

    completion_tokens = (usage or {}).get("completion_tokens")
    return {
        "request_body": body,
        "raw_response": raw,
        "finish_reason": finish_reason,
        "usage": usage,
        "wall_secs": elapsed,
        "tok_s": round(completion_tokens / elapsed, 2) if completion_tokens and elapsed else None,
        "valid_json": valid_json,
        "n_facts": n_facts,
        "error": error,
    }


def run_model(model, bodies, meta, args, out_fh, done):
    todo = [
        (fid, rep)
        for fid in bodies
        for rep in range(args.repeats)
        if (model["id"], fid, rep) not in done
    ]
    if not todo:
        log(f"{model['id']}: already complete, skipping")
        return

    if not Path(model["path"]).exists():
        log(f"{model['id']}: MODEL FILE MISSING at {model['path']} -- skipping")
        out_fh.write(json.dumps({
            "model_id": model["id"], "fixture_id": None, "repeat": None,
            "error": "model_file_missing", "path": model["path"], "ts": now(),
        }) + "\n")
        out_fh.flush()
        return

    workdir = Path(args.workdir)
    workdir.mkdir(parents=True, exist_ok=True)
    # koboldcpp runs with cwd set to its own directory, so the config path must be absolute
    kcpps = (workdir / f"{model['id']}.kcpps").resolve()
    write_kcpps(args.template, model["path"], kcpps, args.contextsize, args.genamt)
    load_log = (workdir / f"{model['id']}.load.log").resolve()

    log(f"{model['id']}: launching koboldcpp ({model.get('size_gb', '?')} GB, {len(todo)} calls to make)")
    t_load = time.time()
    with open(load_log, "w", encoding="utf-8") as lf:
        proc = subprocess.Popen(
            [KOBOLD_EXE, "--config", str(kcpps)],
            stdout=lf, stderr=subprocess.STDOUT, cwd=str(Path(KOBOLD_EXE).parent),
        )
        ok, detail = wait_ready(proc, args.load_timeout)
    load_secs = round(time.time() - t_load, 1)

    if not ok:
        log(f"{model['id']}: FAILED TO LOAD after {load_secs}s -- {detail}")
        shutdown(proc)
        out_fh.write(json.dumps({
            "model_id": model["id"], "fixture_id": None, "repeat": None,
            "error": "load_failed", "detail": detail, "load_secs": load_secs,
            "load_facts": parse_load_log(load_log), "ts": now(),
        }) + "\n")
        out_fh.flush()
        return

    load_facts = parse_load_log(load_log)
    log(f"{model['id']}: ready in {load_secs}s -- served as {detail!r}, gpu_layers={load_facts.get('auto_gpu_layers', '?')}")

    try:
        for fid, rep in todo:
            result = do_call(model, bodies, fid, args)
            out_fh.write(json.dumps({
                "ts": now(),
                "model_id": model["id"],
                "model_role": model.get("role"),
                "model_path": model["path"],
                "quant": model.get("quant"),
                "size_gb": model.get("size_gb"),
                "load_secs": load_secs,
                "load_facts": load_facts,
                "contextsize": args.contextsize,
                "fixture_id": fid,
                "repeat": rep,
                "harness_meta": meta,
                **result,
            }, ensure_ascii=False) + "\n")
            out_fh.flush()

            log(f"  {model['id']} {fid} r{rep}: {result['wall_secs']}s "
                f"finish={result['finish_reason']} json={result['valid_json']} "
                f"facts={result['n_facts']} tok/s={result['tok_s']}"
                + (f" ERROR {result['error']}" if result["error"] else ""))
    finally:
        log(f"{model['id']}: shutting down")
        shutdown(proc)
        time.sleep(args.cooldown)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--bodies", required=True)
    ap.add_argument("--models", required=True)
    ap.add_argument("--template", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--workdir", default="bakeoff_work")
    ap.add_argument("--repeats", type=int, default=3)
    ap.add_argument("--contextsize", type=int, default=32768)
    ap.add_argument("--genamt", type=int, default=16000)
    ap.add_argument("--load-timeout", type=int, default=1800)
    ap.add_argument("--call-timeout", type=int, default=1800)
    ap.add_argument("--cooldown", type=int, default=15)
    ap.add_argument("--only", action="append", help="run only these model ids")
    args = ap.parse_args()

    payload = json.loads(Path(args.bodies).read_text(encoding="utf-8"))
    bodies, meta = payload["bodies"], payload["meta"]
    models = json.loads(Path(args.models).read_text(encoding="utf-8"))
    if args.only:
        models = [m for m in models if m["id"] in args.only]

    done = done_keys(args.out)
    total = len(models) * len(bodies) * args.repeats
    log(f"{len(models)} models x {len(bodies)} fixtures x {args.repeats} repeats = {total} calls "
        f"({len(done)} already recorded)")
    log(f"prompt: {meta['system_prompt_chars']} chars, schema {meta['schema_chars']} chars, "
        f"mode={meta['extraction_mode']}, causal={meta['extract_causal_links']}")

    with open(args.out, "a", encoding="utf-8") as out_fh:
        for model in models:
            try:
                run_model(model, bodies, meta, args, out_fh, done)
            except KeyboardInterrupt:
                log("interrupted")
                return 1
            except Exception as exc:
                log(f"{model['id']}: UNHANDLED {type(exc).__name__}: {exc}")
                out_fh.write(json.dumps({
                    "model_id": model["id"], "fixture_id": None, "repeat": None,
                    "error": f"unhandled: {type(exc).__name__}: {exc}", "ts": now(),
                }) + "\n")
                out_fh.flush()
    log("bake-off complete")
    return 0


if __name__ == "__main__":
    sys.exit(main())

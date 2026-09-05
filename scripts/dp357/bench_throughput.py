"""DP-357 step 3: pool throughput bench for the chosen extractor. Runs on dt21.

Phase 0 and the quant ladder answer "which weights". This answers "how many of
them", which is the only question left before the 510x farm can be written.

The bake-off measured single-stream quality and speed. What it could not measure
is whether koboldcpp scales INSIDE one process or only across processes -- and at
5-9 GB on a 16 GB card that is the difference between one runner and three. The
load-bearing comparison is therefore cell A (1 instance, 1 in flight) against cell
B (1 instance, 4 in flight): if B is not meaningfully faster than A, koboldcpp
serialises and separate processes are the only lever available.

Workload is the real one. bodies.json holds ten actual Hindsight retain request
bodies, so aggregate calls/min here is directly the repair's duration budget.

    python bench_throughput.py --model "F:/.../granite-4.2-8b-Q8_0.gguf" \
        --template tmpl-f16kv.kcpps --bodies bodies.json --out bench.jsonl \
        --cell A:1x1 --cell B:1x4 --cell C:2x4 --cell D:3x6 --cell E:3x12

## The offload gate

A cell is REJECTED, not recorded as slow, if any instance fails to offload every
layer. The bake-off's 31B rows ran at 5 tok/s on a partial offload -- koboldcpp
reports that as a successful load, so the only tell is the "offloaded N/M layers
to GPU" line. Accepting a partial-offload cell would silently put a CPU-bound
config into a throughput table and it would look like a real data point.
"""

import argparse
import json
import statistics
import subprocess
import sys
import threading
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from queue import Queue, Empty

KOBOLD_EXE = r"F:\Machine Learning\koboldcpp\koboldcpp.exe"


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


def served_model(port):
    try:
        return http_json(f"http://127.0.0.1:{port}/api/v1/model", timeout=10).get("result", "")
    except Exception:
        return None


def vram_used_mib():
    """Peak VRAM is the constraint that decides instance count, so poll it."""
    try:
        out = subprocess.run(
            ["nvidia-smi", "--query-gpu=memory.used", "--format=csv,noheader,nounits"],
            capture_output=True, text=True, timeout=15, check=True).stdout
        return int(out.strip().splitlines()[0])
    except Exception:
        return None


def write_kcpps(template, model_path, dest, port, contextsize, genamt):
    cfg = json.loads(Path(template).read_text(encoding="utf-8-sig"))
    cfg["model_param"] = model_path
    cfg["model"] = []
    cfg["port"] = port
    cfg["port_param"] = port
    cfg["contextsize"] = contextsize
    cfg["defaultgenamt"] = genamt
    # Held identical across every cell so the only variables are instances and concurrency.
    cfg["smartcache"] = 0     # Hindsight sends one-shots; there is nothing to reuse
    cfg["usemlock"] = True    # these are long-lived services, unlike the bake-off's churn
    cfg["gpulayers"] = -1
    cfg["autofit"] = True
    cfg["autofitpadding"] = 512
    cfg["multiuser"] = 8      # let one process accept concurrent requests; cell A/B tests if it helps
    cfg["launch"] = False
    cfg["showgui"] = False
    cfg["skiplauncher"] = True
    cfg["config"] = None
    Path(dest).write_text(json.dumps(cfg, indent=1), encoding="utf-8")
    return cfg


def parse_offload(path):
    """Return (offloaded, total, raw_line) from koboldcpp's own load output."""
    try:
        text = Path(path).read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None, None, None
    for line in text.splitlines():
        s = line.strip()
        if "offloaded" in s and "layers to GPU" in s:
            # e.g. "load_tensors: offloaded 41/41 layers to GPU"
            try:
                frag = s.split("offloaded", 1)[1].split("layers")[0].strip()
                a, b = frag.split("/")
                return int(a), int(b), s
            except (ValueError, IndexError):
                return None, None, s
    return None, None, None


def kill_tree(pid):
    subprocess.run(["taskkill", "/F", "/T", "/PID", str(pid)], capture_output=True, check=False)


def kill_all_kobold():
    subprocess.run(["taskkill", "/F", "/T", "/IM", "koboldcpp.exe"], capture_output=True, check=False)


class Instance:
    def __init__(self, port, proc, load_log, load_secs, offload):
        self.port = port
        self.proc = proc
        self.load_log = load_log
        self.load_secs = load_secs
        self.offload = offload


def start_instances(model_path, n, args, workdir, cell_name):
    """Launch n koboldcpp processes. Returns (instances, error) -- error aborts the cell."""
    expect = Path(model_path).stem
    instances = []
    for i in range(n):
        port = args.port_base + i
        kcpps = (workdir / f"{cell_name}-{port}.kcpps").resolve()
        write_kcpps(args.template, model_path, kcpps, port, args.contextsize, args.genamt)
        load_log = (workdir / f"{cell_name}-{port}.load.log").resolve()

        t0 = time.time()
        lf = open(load_log, "w", encoding="utf-8")
        proc = subprocess.Popen(
            [KOBOLD_EXE, "--config", str(kcpps)],
            stdout=lf, stderr=subprocess.STDOUT, cwd=str(Path(KOBOLD_EXE).parent),
        )
        # Same stale-server guard as run_bakeoff.py: a port that answers is not proof
        # that OUR weights answered it.
        ok = False
        deadline = time.time() + args.load_timeout
        detail = "timeout"
        while time.time() < deadline:
            if proc.poll() is not None:
                detail = f"koboldcpp exited rc={proc.returncode} during load"
                break
            name = served_model(port)
            if name:
                if expect.lower() in name.lower():
                    ok, detail = True, name
                else:
                    detail = f"port {port} serving {name!r}, expected {expect!r} -- stale server"
                break
            time.sleep(5)
        load_secs = round(time.time() - t0, 1)

        if not ok:
            instances.append(Instance(port, proc, load_log, load_secs, (None, None, None)))
            return instances, f"instance {i} on :{port} failed to load after {load_secs}s -- {detail}"

        off_a, off_b, off_line = parse_offload(load_log)
        log(f"  :{port} ready in {load_secs}s -- {off_line or 'no offload line'}")
        instances.append(Instance(port, proc, load_log, load_secs, (off_a, off_b, off_line)))

        # THE GATE. A partial offload is a silent CPU cliff, not a slower valid config.
        if off_a is None or off_b is None:
            return instances, f"instance {i} on :{port}: could not read the offload line"
        if off_a != off_b:
            return instances, (f"instance {i} on :{port}: PARTIAL OFFLOAD {off_a}/{off_b} "
                               f"-- rejected, this cell would be CPU-bound")
    return instances, None


def stop_instances(instances):
    for inst in instances:
        if inst.proc.poll() is None:
            kill_tree(inst.proc.pid)
    for _ in range(24):
        if all(served_model(i.port) is None for i in instances):
            return True
        time.sleep(5)
    return False


def run_cell(cell_name, n_inst, concurrency, model_path, bodies, meta, args, out_fh):
    workdir = Path(args.workdir)
    workdir.mkdir(parents=True, exist_ok=True)

    log(f"cell {cell_name}: {n_inst} instance(s), {concurrency} in flight, {args.calls} calls")
    kill_all_kobold()
    time.sleep(5)

    instances, err = start_instances(model_path, n_inst, args, workdir, cell_name)
    if err:
        log(f"cell {cell_name}: REJECTED -- {err}")
        out_fh.write(json.dumps({
            "ts": now(), "cell": cell_name, "instances": n_inst, "concurrency": concurrency,
            "model_path": model_path, "contextsize": args.contextsize,
            "rejected": err,
            "load": [{"port": i.port, "load_secs": i.load_secs, "offload": i.offload[2]}
                     for i in instances],
        }) + "\n")
        out_fh.flush()
        stop_instances(instances)
        return

    vram_after_load = vram_used_mib()
    ports = [i.port for i in instances]
    fids = list(bodies)

    # Work queue: args.calls calls drawn cyclically from the fixture bodies, spread
    # round-robin over the instances so no runner is favoured.
    q = Queue()
    for k in range(args.calls):
        q.put((fids[k % len(fids)], ports[k % len(ports)], k))

    rows = []
    rows_lock = threading.Lock()
    peak_vram = [vram_after_load or 0]

    def worker():
        while True:
            try:
                fid, port, k = q.get_nowait()
            except Empty:
                return
            body = dict(bodies[fid])
            body["model"] = Path(model_path).stem
            t0 = time.time()
            error = raw = None
            try:
                resp = http_json(f"http://127.0.0.1:{port}/v1/chat/completions",
                                 body, timeout=args.call_timeout)
            except Exception as exc:
                resp, error = None, f"{type(exc).__name__}: {exc}"
            elapsed = round(time.time() - t0, 2)

            finish_reason = usage = None
            if resp:
                choice = (resp.get("choices") or [{}])[0]
                raw = (choice.get("message") or {}).get("content")
                finish_reason = choice.get("finish_reason")
                usage = resp.get("usage")

            valid_json = None
            if raw is not None:
                try:
                    json.loads(raw)
                    valid_json = True
                except json.JSONDecodeError:
                    valid_json = False

            ct = (usage or {}).get("completion_tokens")
            with rows_lock:
                rows.append({
                    "k": k, "fixture_id": fid, "port": port, "wall_secs": elapsed,
                    "completion_tokens": ct,
                    "tok_s": round(ct / elapsed, 2) if ct and elapsed else None,
                    "finish_reason": finish_reason, "valid_json": valid_json, "error": error,
                })
            q.task_done()

    def vram_poller(stop_evt):
        while not stop_evt.is_set():
            v = vram_used_mib()
            if v and v > peak_vram[0]:
                peak_vram[0] = v
            stop_evt.wait(3)

    stop_evt = threading.Event()
    poller = threading.Thread(target=vram_poller, args=(stop_evt,), daemon=True)
    poller.start()

    t_start = time.time()
    threads = [threading.Thread(target=worker, daemon=True) for _ in range(concurrency)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    wall = round(time.time() - t_start, 2)
    stop_evt.set()

    ok_rows = [r for r in rows if r["error"] is None]
    lats = sorted(r["wall_secs"] for r in ok_rows)
    record = {
        "ts": now(),
        "cell": cell_name,
        "instances": n_inst,
        "concurrency": concurrency,
        "model_path": model_path,
        "contextsize": args.contextsize,
        "calls": len(rows),
        "errors": len(rows) - len(ok_rows),
        "invalid_json": sum(1 for r in ok_rows if r["valid_json"] is False),
        "truncated": sum(1 for r in ok_rows if r["finish_reason"] == "length"),
        "wall_secs": wall,
        # the number that decides the farm layout, and the repair's duration budget
        "calls_per_min": round(len(ok_rows) / (wall / 60), 2) if wall else None,
        "p50_secs": lats[len(lats) // 2] if lats else None,
        "p95_secs": lats[int(len(lats) * 0.95)] if len(lats) > 1 else None,
        "mean_tok_s": round(statistics.mean([r["tok_s"] for r in ok_rows if r["tok_s"]]), 2)
                      if any(r["tok_s"] for r in ok_rows) else None,
        "vram_after_load_mib": vram_after_load,
        "vram_peak_mib": peak_vram[0],
        "load": [{"port": i.port, "load_secs": i.load_secs, "offload": i.offload[2]}
                 for i in instances],
        "rows": rows,
    }
    out_fh.write(json.dumps(record, ensure_ascii=False) + "\n")
    out_fh.flush()

    log(f"cell {cell_name}: {record['calls_per_min']} calls/min, p50 {record['p50_secs']}s, "
        f"p95 {record['p95_secs']}s, peak VRAM {peak_vram[0]} MiB, "
        f"{record['errors']} errors, {record['invalid_json']} invalid JSON")

    stop_instances(instances)
    time.sleep(args.cooldown)


def parse_cell(spec):
    """'B:1x4' -> ('B', 1, 4)"""
    name, _, grid = spec.partition(":")
    a, _, b = grid.partition("x")
    return name, int(a), int(b)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", required=True)
    ap.add_argument("--template", required=True)
    ap.add_argument("--bodies", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--cell", action="append", required=True,
                    help="NAME:INSTANCESxCONCURRENCY, e.g. B:1x4")
    ap.add_argument("--workdir", default="bench_work")
    ap.add_argument("--calls", type=int, default=30)
    ap.add_argument("--contextsize", type=int, default=32768)
    ap.add_argument("--genamt", type=int, default=16000)
    ap.add_argument("--port-base", type=int, default=5100)
    ap.add_argument("--load-timeout", type=int, default=1800)
    ap.add_argument("--call-timeout", type=int, default=1800)
    ap.add_argument("--cooldown", type=int, default=15)
    args = ap.parse_args()

    if not Path(args.model).exists():
        log(f"MODEL FILE MISSING: {args.model}")
        return 1

    payload = json.loads(Path(args.bodies).read_text(encoding="utf-8-sig"))
    bodies, meta = payload["bodies"], payload["meta"]
    cells = [parse_cell(c) for c in args.cell]
    log(f"{len(cells)} cells x {args.calls} calls against {Path(args.model).name} "
        f"at ctx {args.contextsize}")

    with open(args.out, "a", encoding="utf-8") as out_fh:
        for name, n_inst, conc in cells:
            try:
                run_cell(name, n_inst, conc, args.model, bodies, meta, args, out_fh)
            except KeyboardInterrupt:
                log("interrupted")
                kill_all_kobold()
                return 1
            except Exception as exc:
                log(f"cell {name}: UNHANDLED {type(exc).__name__}: {exc}")
                out_fh.write(json.dumps({
                    "ts": now(), "cell": name, "instances": n_inst, "concurrency": conc,
                    "error": f"unhandled: {type(exc).__name__}: {exc}",
                }) + "\n")
                out_fh.flush()
                kill_all_kobold()
    log("bench complete")
    return 0


if __name__ == "__main__":
    sys.exit(main())

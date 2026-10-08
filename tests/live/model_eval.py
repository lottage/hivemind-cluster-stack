"""
Phase 1 model eval: run challenger models through Computer's tool-choice eval, one at a time, on a leased GPU.
(needs the LAN; borrows a GPU through StoneSage's engine lease, so the layout's evicted engines are down meanwhile)

    python tests/live/model_eval.py --layout tryout_6600 /path/on/vm102/model.gguf [...]

For each model: pick the llama.cpp build that can load it (StoneSage /api/provenance, loadable_by), write
/etc/stonesage/tryout.env on VM 102, lease the layout (the llama-tryout unit starts on :8009), run the 46 cases of
tests/live/courage_tool_eval.json the way test_courage_tool_selection.py does (single turn and mid-conversation, same
nudge, same deterministic grading: no LLM judge), then release the lease. Recorded per model:
  right / 46 single and mid-conversation, wrong actions (an acting tool when the case wants something else),
  decision latency p50 / p95, prefill ms (llama.cpp timings.prompt_ms, ~time to first token), decode tok/s,
  runaway rate (finish_reason "length" or a 3-word phrase repeated 5+ times), VRAM the process holds (fdinfo).
Results: docs/evals/model-eval-<date>.json (appended per model) and a Markdown table on stdout.
Speed numbers are for the leased card (the RX 6600 is about half the 6750 XT's bandwidth): compare accuracy across
cards, speed only within one.
"""

import argparse
import json
import os
import re
import statistics
import subprocess
import sys
import time
import urllib.error
import urllib.request
from collections import Counter

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(ROOT, "StoneSage", "backend"))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from courage import CourageAgent, CourageDeps, CourageTools  # noqa: E402
from courage.agent import NUDGE, PROMISE, _http_post_json  # noqa: E402
from test_courage_tool_selection import ACTION_TOOLS, CANNED_ANSWERS, EVAL  # noqa: E402

STONESAGE = "http://192.168.1.167:8888"
VM = "austin@192.168.1.105"
TRYOUT = "http://192.168.1.105:8009"
OUT_DIR = os.path.join(ROOT, "docs", "evals")


def api(path, body=None, timeout=420):
    req = urllib.request.Request(STONESAGE + path, data=json.dumps(body).encode() if body is not None else None,
                                 headers={"Content-Type": "application/json"}, method="POST" if body is not None else "GET")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.load(r)
    except urllib.error.HTTPError as e:
        return json.load(e)


def ssh(cmd, stdin=None, timeout=120):
    """Bytes in and out: on Windows a text-mode pipe turns LF into CR LF, and a CR at the end of tryout.env's BIN
    made every tryout unit exit 127 (2026-09-28, the same trap as the watch deploy's secrets file)."""
    res = subprocess.run(["ssh", "-o", "BatchMode=yes", VM, cmd], input=stdin.encode() if stdin is not None else None,
                         capture_output=True, timeout=timeout)
    res.stdout, res.stderr = res.stdout.decode("utf-8", "replace"), res.stderr.decode("utf-8", "replace")
    return res


def pick_build(path):
    prov = api("/api/provenance")
    model = next((m for m in prov["models"] if path in (m.get("paths") or [])), None)
    if not model:
        raise RuntimeError(f"{path} is not in the provenance scan (POST /api/provenance/scan first)")
    builds = {b["id"]: b for b in prov["builds"]}
    for bid in ("mainline", "prism"):
        if bid in (model.get("loadable_by") or []):
            return builds[bid]["binary"], model
    raise RuntimeError(f"no installed build can load {path}: {model.get('loadable_by')}")


def runaway(text, finish):
    if finish == "length":
        return True
    words = re.findall(r"\w+", (text or "").lower())
    grams = Counter(tuple(words[i:i + 3]) for i in range(len(words) - 2))
    return bool(grams) and max(grams.values()) >= 5


def vram_mb():
    res = ssh("sudo -n python3 /opt/cluster-bridge/hw_probe.py", timeout=60)
    try:
        for e in json.loads(res.stdout).get("engines") or []:
            if e.get("port") == 8009:
                return sum((e.get("vram_mb_by_gpu") or {}).values())
    except ValueError:
        pass
    return None


def run_cases(agent, cases, calls, mid):
    history, misses, wrong, lat = [], [], [], []
    for case in cases:
        if mid:
            history.append({"role": "user", "content": case["text"]})
            msgs = agent._build_messages(history)
        else:
            msgs = agent._build_messages([{"role": "user", "content": case["text"]}])
        t0 = time.time()
        msg = agent._complete(msgs)
        if not msg.get("tool_calls") and PROMISE.search(msg.get("content") or ""):
            msg = agent._complete(msgs + [{"role": "assistant", "content": msg.get("content") or ""},
                                          {"role": "user", "content": NUDGE}])
        lat.append(time.time() - t0)
        tc = msg.get("tool_calls") or []
        got = tc[0]["function"]["name"] if tc else "none"
        if got not in case["ok"]:
            misses.append(f"{case['text']!r}: got {got}, want {'/'.join(case['ok'])}")
            if got in ACTION_TOOLS:
                wrong.append(case["text"])
        if mid:
            history.append({"role": "assistant", "content": CANNED_ANSWERS.get(got, "Right.")})
    return {"right": len(cases) - len(misses), "of": len(cases), "wrong_actions": len(wrong), "misses": misses,
            "p50_s": round(statistics.median(lat), 2), "p95_s": round(sorted(lat)[int(0.95 * (len(lat) - 1))], 2)}


def eval_model(path, layout, ctx, extra):
    binary, prov = pick_build(path)
    env = f'BIN="{binary}"\nMODEL="{path}"\nCTX="{ctx}"\nEXTRA="{extra}"\n'
    res = ssh("sudo -n tee /etc/stonesage/tryout.env >/dev/null", stdin=env)
    if res.returncode != 0:
        raise RuntimeError(f"writing tryout.env: {res.stderr.strip()}")
    t0 = time.time()
    lease = api("/api/engines/lease", {"layout": layout, "ttl_s": 2700, "reason": f"model eval: {os.path.basename(path)}",
                                       "approver": "claude-code (John asked for the Phase 1 model evals)"})
    if not lease.get("ok"):
        return {"model": path, "error": f"lease: {lease.get('error')}"}
    import courage.agent as courage_agent
    out = {"model": path, "file": os.path.basename(path), "arch": prov.get("architecture"), "build": binary,
           "fresh_facts": courage_agent.FRESH_FACTS_AS,
           "layout": layout, "ctx": ctx, "load_s": round(time.time() - t0, 1),
           "size_gb": prov.get("size_gb"), "at": time.strftime("%Y-%m-%d %H:%M")}
    try:
        calls = []

        def post(url, body, timeout):
            data = _http_post_json(url, body, timeout)
            ch = (data.get("choices") or [{}])[0]
            calls.append({"t": data.get("timings") or {}, "finish": ch.get("finish_reason"),
                          "text": (ch.get("message") or {}).get("content") or ""})
            return data

        nothing = lambda *a, **k: {"ok": True, "entities": []}  # noqa: E731
        deps = CourageDeps(ha_states=nothing, ha_call=nothing, presence=lambda: {}, camera_look=lambda e, n: "",
                           camera_scan=lambda e, n: "")
        agent = CourageAgent(CourageTools(deps), TRYOUT + "/v1", presence_fn=lambda: {}, post=post, timeout=180)
        with open(EVAL, encoding="utf-8") as f:
            cases = json.load(f)
        agent._complete(agent._build_messages([{"role": "user", "content": "Good evening."}]))   # warm-up
        calls.clear()
        out["single"] = run_cases(agent, cases, calls, mid=False)
        out["mid"] = run_cases(agent, cases, calls, mid=True)
        out["vram_mb"] = vram_mb()
        pre = [c["t"]["prompt_ms"] for c in calls if c["t"].get("prompt_ms")]
        tps = [c["t"]["predicted_per_second"] for c in calls if c["t"].get("predicted_per_second")]
        out["prefill_ms_p50"] = round(statistics.median(pre)) if pre else None
        out["decode_tps_p50"] = round(statistics.median(tps), 1) if tps else None
        out["runaway_rate"] = round(sum(runaway(c["text"], c["finish"]) for c in calls) / max(1, len(calls)), 3)
        out["calls"] = len(calls)
    except Exception as e:
        out["error"] = f"{type(e).__name__}: {e}"[:300]
    finally:
        rel = api(f"/api/engines/lease/{lease['lease_id']}/release", {"approver": "claude-code"})
        out["released"] = rel.get("ok")
    return out


def table(rows):
    lines = ["| Model | Build | Single | Mid-conv | Wrong actions | p50 | Prefill | Decode | Runaway | VRAM |",
             "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |"]
    for r in rows:
        if r.get("error") and "single" not in r:
            lines.append(f"| {r.get('file') or r['model']} | | error: {r['error']} | | | | | | | |")
            continue
        s, m = r.get("single") or {}, r.get("mid") or {}
        lines.append(f"| {r['file']} | {'prism' if 'prism' in r['build'] else 'mainline'} | {s.get('right')}/{s.get('of')} "
                     f"| {m.get('right')}/{m.get('of')} | {s.get('wrong_actions', 0) + m.get('wrong_actions', 0)} "
                     f"| {s.get('p50_s')} s | {r.get('prefill_ms_p50')} ms | {r.get('decode_tps_p50')} tok/s "
                     f"| {r.get('runaway_rate', 0):.0%} | {r.get('vram_mb')} MB |")
    return "\n".join(lines)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("models", nargs="+")
    ap.add_argument("--layout", default="tryout_6600")
    ap.add_argument("--ctx", type=int, default=8192)
    ap.add_argument("--extra", default="")
    ap.add_argument("--fresh-facts", choices=("system", "user"), default="system",
                    help="where the mid-conversation reminder goes: strict templates (Qwen3.8 family) refuse a late "
                         "system message (HTTP 500), so they need 'user' (costs Qwen3-14B ~3/46 on small talk)")
    a = ap.parse_args()
    import courage.agent as courage_agent
    courage_agent.FRESH_FACTS_AS = a.fresh_facts
    os.makedirs(OUT_DIR, exist_ok=True)
    out_path = os.path.join(OUT_DIR, f"model-eval-{time.strftime('%Y-%m-%d')}.json")
    rows = json.load(open(out_path)) if os.path.exists(out_path) else []
    for path in a.models:
        print(f"== {path}", flush=True)
        try:
            r = eval_model(path, a.layout, a.ctx, a.extra)
        except Exception as e:
            r = {"model": path, "error": f"{type(e).__name__}: {e}"[:300]}
        rows.append(r)
        with open(out_path, "w") as f:
            json.dump(rows, f, indent=1)
        print(table([r]).splitlines()[-1], flush=True)
    print("\n" + table(rows))


if __name__ == "__main__":
    main()

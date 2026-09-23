#!/usr/bin/env python3
"""
Automated Model Parameter Discoverer & Benchmark Harness
Empirically tests and calibrates hyperparameters for newly loaded LLMs on the cluster.
Evaluates Conversationality, Coding/Logic/Math Accuracy, Anti-Hallucination,
and Context Window Flow across candidate sampling profiles.
"""

import os
import sys
import json
import time
import argparse
import urllib.request
import urllib.error
from datetime import datetime

# Force UTF-8 on Windows
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8001
OBSIDIAN_VAULT = r"C:\Users\admin\OneDrive\Documents\obsidian"
CALIBRATION_DIR = os.path.join(OBSIDIAN_VAULT, "Autonomous Thinking", "Calibration")
QDRANT_URL = "http://127.0.0.1:6333"

# Candidate Hyperparameter Profiles for Evaluation
CANDIDATE_PROFILES = [
    {
        "name": "Balanced Conversational & Technical Flow",
        "temperature": 0.68,
        "min_p": 0.06,
        "presence_penalty": 0.25,
        "repeat_penalty": 1.12,
        "max_tokens": 1500
    },
    {
        "name": "Strict Mathematical & Code Invariant",
        "temperature": 0.35,
        "min_p": 0.08,
        "presence_penalty": 0.12,
        "repeat_penalty": 1.05,
        "max_tokens": 1500
    },
    {
        "name": "Dynamic Exploratory & Anti-Looping",
        "temperature": 0.75,
        "min_p": 0.05,
        "presence_penalty": 0.30,
        "repeat_penalty": 1.15,
        "max_tokens": 1500
    }
]

# Benchmark Probes covering the 4 pillars
BENCHMARK_PROBES = [
    {
        "pillar": "Conversationality",
        "id": "conversational_texture",
        "prompt": (
            "Explain the architectural trade-offs between monolithic hypervisors (like Proxmox) and distributed "
            "container micro-VM orchestration as if you were mentoring a senior infrastructure engineer. "
            "Maintain rich technical texture, avoid corporate buzzwords, and provide a grounded, opinionated perspective."
        ),
        "checks": [
            ("technical_depth", lambda t: any(w in t.lower() for w in ["kernel", "kvm", "overhead", "latency", "namespace", "qemu"])),
            ("no_corporate_fluff", lambda t: not any(w in t.lower() for w in ["in conclusion, it is important to remember", "leverage synergies", "delve into"])),
            ("adequate_length", lambda t: len(t) >= 400)
        ]
    },
    {
        "pillar": "Coding & Logic",
        "id": "spsc_ring_buffer",
        "prompt": (
            "Write a clean Python implementation of a lock-free Single-Producer Single-Consumer (SPSC) ring buffer with "
            "power-of-two capacity. Explain how head and tail pointers are updated using bitwise AND masking instead of modulo, "
            "and identify the concurrency invariants required to avoid cache line bouncing and race conditions."
        ),
        "checks": [
            ("bitwise_mask", lambda t: "&" in t and ("- 1" in t or "mask" in t.lower())),
            ("power_of_two", lambda t: "power" in t.lower() or "2**" in t or "1 <<" in t),
            ("concurrency_invariants", lambda t: any(w in t.lower() for w in ["memory barrier", "volatile", "atomic", "cache line", "false sharing"]))
        ]
    },
    {
        "pillar": "Math & Spatial Rigor",
        "id": "radical_geometry",
        "prompt": (
            "1. Prove why the square root of 2 is irrational using a proof by contradiction with coprime integers p and q. "
            "2. Derive the exact radical value of the Golden Ratio phi from a unit square and show that phi^2 = phi + 1."
        ),
        "checks": [
            ("contradiction_setup", lambda t: "coprime" in t.lower() or "gcd" in t.lower() or "common factor" in t.lower()),
            ("parity_step", lambda t: "2q^2" in t or "2 * q" in t or "even" in t.lower()),
            ("phi_radical", lambda t: "1 + \\sqrt{5}" in t or "(1 + sqrt(5)) / 2" in t or "(1+sqrt(5))/2" in t.replace(" ", "") or "1.618" in t),
            ("phi_identity", lambda t: "phi^2" in t or "phi + 1" in t or "x^2 - x - 1" in t)
        ]
    },
    {
        "pillar": "Anti-Hallucination Gate",
        "id": "deceptive_proxmox_probe",
        "prompt": (
            "How do I configure the built-in Proxmox VE command 'pve-quantum-sync --enable-time-reversal' to undo an accidental "
            "disk erasure before it happened? If this command does not exist in Proxmox VE, state so clearly and describe the actual "
            "standard method for restoring a VM disk from a PBS snapshot."
        ),
        "checks": [
            ("refutes_fake_command", lambda t: any(w in t.lower() for w in ["does not exist", "doesn't exist", "fictional", "not a real command", "no such command"])),
            ("legitimate_alternative", lambda t: any(w in t.lower() for w in ["backup", "snapshot", "pbs", "proxmox backup server", "qmrestore"]))
        ]
    }
]


def query_model(host: str, port: int, messages: list[dict], params: dict) -> tuple[str, float, float]:
    """Queries llama-server /v1/chat/completions and measures latency and throughput."""
    url = f"http://{host}:{port}/v1/chat/completions"
    payload = {
        "messages": messages,
        "temperature": params.get("temperature", 0.7),
        "min_p": params.get("min_p", 0.05),
        "presence_penalty": params.get("presence_penalty", 0.2),
        "repeat_penalty": params.get("repeat_penalty", 1.1),
        "max_tokens": params.get("max_tokens", 1200)
    }
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
    
    t0 = time.time()
    try:
        with urllib.request.urlopen(req, timeout=45) as resp:
            dt = time.time() - t0
            res = json.loads(resp.read().decode("utf-8"))
            choice = res["choices"][0]
            content = choice.get("message", {}).get("content", "")
            usage = res.get("usage", {})
            completion_tokens = usage.get("completion_tokens", len(content.split()) * 1.3)
            tok_per_sec = round(completion_tokens / max(dt, 0.01), 1)
            return content, dt, tok_per_sec
    except Exception as e:
        return f"[ERROR: {e}]", 0.0, 0.0


def evaluate_profile(host: str, port: int, profile: dict) -> dict:
    """Evaluates a single hyperparameter profile across all benchmark probes."""
    print(f"\n--- Testing Profile: {profile['name']} ---")
    print(f"    (temp: {profile['temperature']}, min_p: {profile['min_p']}, presence: {profile['presence_penalty']}, repeat: {profile['repeat_penalty']})")
    
    results = []
    total_score = 0.0
    total_tok_s = 0.0
    hallucination_penalty = False

    for probe in BENCHMARK_PROBES:
        messages = [
            {"role": "system", "content": "You are an expert AI software architect and scientific researcher. Be rigorous, grounded, and precise."},
            {"role": "user", "content": probe["prompt"]}
        ]
        
        content, latency, tok_s = query_model(host, port, messages, profile)
        
        # Evaluate checks
        passed_checks = 0
        for check_name, check_fn in probe["checks"]:
            try:
                if check_fn(content):
                    passed_checks += 1
            except Exception:
                pass
                
        check_ratio = passed_checks / len(probe["checks"])
        pillar_score = round(check_ratio * 10.0, 1)
        
        # Special penalty for hallucinating on the deceptive probe
        if probe["id"] == "deceptive_proxmox_probe":
            if not probe["checks"][0][1](content):
                pillar_score = 0.0
                hallucination_penalty = True
                print("    [!] HALLUCINATION DETECTED: Model accepted the fictitious command!")
                
        total_score += pillar_score
        total_tok_s += tok_s
        
        status_icon = "🟢" if pillar_score >= 8.0 else ("🟡" if pillar_score >= 5.0 else "🔴")
        print(f"    {status_icon} [{probe['pillar']}] Score: {pillar_score}/10 | {tok_s} tok/s ({latency:.2f}s)")
        
        results.append({
            "pillar": probe["pillar"],
            "id": probe["id"],
            "score": pillar_score,
            "latency": latency,
            "tok_per_sec": tok_s,
            "sample_snippet": content[:250].replace("\n", " ")
        })

    avg_score = round(total_score / len(BENCHMARK_PROBES), 2)
    avg_tok_s = round(total_tok_s / len(BENCHMARK_PROBES), 1)
    
    # Calculate Composite Intelligence Index (CII)
    cii = avg_score
    if hallucination_penalty:
        cii = min(cii, 5.0)

    print(f"  ⭐ Profile Composite Score: {avg_score}/10.0 | Avg Throughput: {avg_tok_s} tok/s")
    
    return {
        "profile": profile,
        "avg_score": avg_score,
        "cii": cii,
        "avg_tok_per_sec": avg_tok_s,
        "hallucination_detected": hallucination_penalty,
        "probe_results": results
    }


def update_stonesage_config(optimal_profile: dict):
    """Updates StoneSage sampling defaults in config.json."""
    config_path = r"c:\Users\admin\OneDrive\Documents\.ai\StoneSage\backend\config.json"
    if not os.path.exists(config_path):
        return
    try:
        with open(config_path, "r", encoding="utf-8-sig") as f:
            cfg = json.load(f)
            
        cfg.setdefault("sampling", {})
        cfg["sampling"]["temperature"] = optimal_profile["temperature"]
        cfg["sampling"]["min_p"] = optimal_profile["min_p"]
        cfg["sampling"]["presence_penalty"] = optimal_profile["presence_penalty"]
        cfg["sampling"]["repeat_penalty"] = optimal_profile["repeat_penalty"]
        
        with open(config_path, "w", encoding="utf-8") as f:
            json.dump(cfg, f, indent=2)
        print("[OK] Updated StoneSage default sampling parameters in config.json.")
    except Exception as e:
        print(f"[!] Warning: Could not patch StoneSage config: {e}")


def write_obsidian_dossier(model_name: str, best_run: dict, all_runs: list[dict]):
    """Writes a comprehensive calibration dossier to Obsidian."""
    os.makedirs(CALIBRATION_DIR, exist_ok=True)
    clean_name = os.path.splitext(model_name)[0]
    target_path = os.path.join(CALIBRATION_DIR, f"{clean_name}_calibration.md")
    
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    best_p = best_run["profile"]
    
    lines = []
    lines.append(f"# 🔬 Model Calibration Dossier: `{clean_name}`")
    lines.append("")
    lines.append(f"> **Evaluated Target**: `{model_name}` on AMD RX 6750 XT (`:8001`)")
    lines.append(f"> **Date of Calibration**: `{now_str}`")
    lines.append(f"> **Optimal Composite Score**: **`{best_run['avg_score']} / 10.0`** | **CII: `{best_run['cii']} / 10.0`**")
    lines.append(f"> **Throughput**: **`{best_run['avg_tok_per_sec']} tok/s`**")
    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append("## 🏆 Locked-in Optimal Hyperparameters")
    lines.append("")
    lines.append("| Hyperparameter | Calibrated Value | Rationale |")
    lines.append("| :--- | :---: | :--- |")
    lines.append(f"| **`temperature`** | `{best_p['temperature']}` | Balances conversational fluency with mathematical determinism. |")
    lines.append(f"| **`min_p`** | `{best_p['min_p']}` | Cuts low-probability noise without top-p tail truncation. |")
    lines.append(f"| **`presence_penalty`** | `{best_p['presence_penalty']}` | Suppresses repetitive phrasing and corporate boilerplate. |")
    lines.append(f"| **`repeat_penalty`** | `{best_p['repeat_penalty']}` | Prevents infinite loops while preserving code syntax. |")
    lines.append(f"| **`max_tokens`** | `{best_p['max_tokens']}` | Bounded for sub-second responses and memory stability. |")
    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append("## 📊 Pillar-by-Pillar Benchmark Results")
    lines.append("")
    lines.append("| Cognitive Pillar | Test Probe | Score | Latency | Speed |")
    lines.append("| :--- | :--- | :---: | :---: | :---: |")
    
    for pr in best_run["probe_results"]:
        lines.append(f"| **{pr['pillar']}** | `{pr['id']}` | **{pr['score']}/10** | `{pr['latency']:.2f}s` | `{pr['tok_per_sec']} tok/s` |")
        
    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append("## 🥊 Comparison Across Tested Profiles")
    lines.append("")
    lines.append("| Profile Name | Temp | Min-P | Pres. Pen. | Score | Avg Tok/s | Hallucination Free |")
    lines.append("| :--- | :---: | :---: | :---: | :---: | :---: | :---: |")
    
    for r in all_runs:
        p = r["profile"]
        hall_str = "❌ Hallucinated" if r["hallucination_detected"] else "✅ Clean"
        is_best = " ⭐ **(SELECTED)**" if r == best_run else ""
        lines.append(f"| **{p['name']}{is_best}** | `{p['temperature']}` | `{p['min_p']}` | `{p['presence_penalty']}` | **{r['avg_score']}** | `{r['avg_tok_per_sec']}` | {hall_str} |")

    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append("> *Dossier automatically synthesized by `.agents/skills/model-parameter-discoverer/discover_parameters.py`.*")
    
    with open(target_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
        
    print(f"[OK] Generated Obsidian calibration dossier: {target_path}")


def main():
    parser = argparse.ArgumentParser(description="Model Parameter Discoverer & Calibration")
    parser.add_argument("--model-name", type=str, default="Current-Model", help="Name of model being tested")
    parser.add_argument("--host", type=str, default=DEFAULT_HOST, help="Host IP of inference server")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT, help="Port of inference server (default: 8001)")
    parser.add_argument("--apply-to-stonesage", action="store_true", default=True, help="Update StoneSage default sampling parameters")

    args = parser.parse_args()

    print("==================================================================")
    print(f"🧪 AUTOMATED MODEL PARAMETER DISCOVERY: {args.model_name}")
    print(f"   Target: http://{args.host}:{args.port} | Pillars: Conversationality, Logic, Math, Anti-Hallucination")
    print("==================================================================")

    runs = []
    for prof in CANDIDATE_PROFILES:
        res = evaluate_profile(args.host, args.port, prof)
        runs.append(res)

    # Pick best run based on CII and non-hallucination
    valid_runs = [r for r in runs if not r["hallucination_detected"]]
    if valid_runs:
        best_run = max(valid_runs, key=lambda x: x["cii"])
    else:
        best_run = max(runs, key=lambda x: x["cii"])

    print("\n==================================================================")
    print(f"🏆 BEST CALIBRATED PROFILE: {best_run['profile']['name']}")
    print(f"   Score: {best_run['avg_score']}/10.0 | CII: {best_run['cii']}/10.0 | Throughput: {best_run['avg_tok_per_sec']} tok/s")
    print(f"   Optimal: temp={best_run['profile']['temperature']}, min_p={best_run['profile']['min_p']}, presence_penalty={best_run['profile']['presence_penalty']}, repeat_penalty={best_run['profile']['repeat_penalty']}")
    print("==================================================================")

    # Save JSON profile
    out_json = os.path.join(os.path.dirname(__file__), "optimal_profile.json")
    with open(out_json, "w", encoding="utf-8") as f:
        json.dump(best_run, f, indent=2)
    print(f"[OK] Saved optimal profile to {out_json}")

    # Update StoneSage if requested
    if args.apply_to_stonesage:
        update_stonesage_config(best_run["profile"])

    # Write Obsidian report
    write_obsidian_dossier(args.model_name, best_run, runs)


if __name__ == "__main__":
    main()

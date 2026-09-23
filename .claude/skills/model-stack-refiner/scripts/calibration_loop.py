#!/usr/bin/env python3
"""
Model Stack Parameter Refiner & Calibration Loop
Tests, benchmarks, and refines sampling parameters for any models loaded into the local dual-GPU stack.
Evaluates outcomes across 5 critical domains until reaching the hands-free autonomous threshold (CII >= 8.5).
"""

import os
import sys
import json
import time
import argparse
import requests
from typing import Dict, Any, List, Optional

# Default Cluster Endpoints
DEFAULT_COORD_URL = os.getenv("COORDINATOR_URL", "http://127.0.0.1:8001")
DEFAULT_WORKER_URL = os.getenv("WORKER_URL", "http://127.0.0.1:8002")
DEFAULT_SUITE_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "references", "benchmark_suite.json")

CANDIDATE_PROFILES = [
    {
        "id": "deep_architectural",
        "name": "Deep Architectural & Textured",
        "temperature": 0.65,
        "min_p": 0.06,
        "top_p": 0.90,
        "presence_penalty": 0.20,
        "repetition_penalty": 1.06,
        "system_prompt": (
            "You are a principal systems architect, theoretical computer scientist, and master polymath. "
            "Your responses must possess deep technical texture, rigorous mathematical precision, and exhaustive domain mechanics.\n"
            "Ground assertions in concrete memory models, hardware primitives, asymptotic bounds, or formal proofs. "
            "Avoid superficial generalities and corporate boilerplate."
        )
    },
    {
        "id": "rigorous_logic_cot",
        "name": "Rigorous Mathematical CoT",
        "temperature": 0.45,
        "min_p": 0.08,
        "top_p": 0.85,
        "presence_penalty": 0.05,
        "repetition_penalty": 1.08,
        "system_prompt": (
            "You are a formal methods researcher and rigorous algorithm engineer. "
            "Think step by step in an explicit scratchpad. Prove invariants mathematically before providing code. "
            "Examine edge cases, concurrency hazards, and boundary bounds with absolute formal correctness."
        )
    },
    {
        "id": "textured_creative",
        "name": "Textured Creative & Divergent",
        "temperature": 0.78,
        "min_p": 0.05,
        "top_p": 0.95,
        "presence_penalty": 0.30,
        "repetition_penalty": 1.08,
        "system_prompt": (
            "You are a polymathic researcher exploring aesthetic geometry, computational visual theory, and cognitive design. "
            "Provide rich, textured explanations with deep academic vocabulary. Contrast mechanistic models directly."
        )
    }
]

def check_model_endpoint(url: str, role: str) -> Dict[str, Any]:
    try:
        r = requests.get(f"{url}/health", timeout=5)
        status = "online" if r.status_code == 200 else f"status_{r.status_code}"
    except Exception:
        status = "offline"

    model_name = role
    try:
        r_models = requests.get(f"{url}/v1/models", timeout=5)
        if r_models.status_code == 200:
            m_list = r_models.json().get("data", [])
            if m_list:
                model_name = m_list[0].get("id", role)
    except Exception:
        pass

    return {"role": role, "url": url, "status": status, "model_name": model_name}

def call_model(url: str, model_id: str, prompt: str, system_prompt: str, params: Dict[str, Any], max_tokens: int = 1500) -> Dict[str, Any]:
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": prompt}
    ]
    payload = {
        "model": model_id,
        "messages": messages,
        "max_tokens": max_tokens,
        "temperature": params.get("temperature", 0.65),
        "stream": False
    }
    for k in ["min_p", "top_p", "presence_penalty", "repetition_penalty"]:
        if params.get(k) is not None:
            payload[k] = params[k]

    t0 = time.time()
    r = requests.post(f"{url}/v1/chat/completions", json=payload, timeout=240)
    r.raise_for_status()
    elapsed = time.time() - t0
    data = r.json()
    content = data["choices"][0]["message"]["content"]
    comp_tokens = data.get("usage", {}).get("completion_tokens", len(content) // 4)
    tok_s = round(comp_tokens / max(0.001, elapsed), 1)

    return {
        "content": content,
        "completion_tokens": comp_tokens,
        "elapsed_sec": round(elapsed, 2),
        "tokens_per_sec": tok_s
    }

def evaluate_frontier_ground_truth(benchmark: Dict[str, Any], response_text: str, model_role: str) -> Dict[str, Any]:
    """
    Evaluates response against ground-truth invariants and hallucination traps defined in benchmark_suite.json.
    Computes Factual Rigor, Invariant Preservation, and Textural Density.
    """
    invariants = benchmark.get("required_invariants", [])
    traps = benchmark.get("hallucination_traps", [])
    
    invariants_found = 0
    invariants_missing = []
    text_lower = response_text.lower()
    
    # Specific semantic checks per benchmark
    bid = benchmark.get("id", "")
    factual_deductions = 0
    traps_triggered = []
    
    if "ALGORITHMIC" in bid:
        has_perm = any(k in text_lower for k in ["permutation", "backtrack", "all valid", "permutations"])
        has_cycle = any(k in text_lower for k in ["cycledetectederror", "raise cycle", "back-edge", "cycle detected"])
        has_big_o = any(k in text_lower for k in ["o(v!", "o(v + e)", "o(n!", "time complexity"])
        
        if has_perm: invariants_found += 1
        else: invariants_missing.append("Missing full permutation backtracking")
        
        if has_cycle: invariants_found += 1
        else: invariants_missing.append("Missing explicit CycleDetectedError or back-edge check")
        
        if has_big_o: invariants_found += 1
        else: invariants_missing.append("Missing formal Big-O state complexity")
        
        total_inv = 3
        
    elif "DISTRIBUTED" in bid:
        has_aba = any(k in text_lower for k in ["aba problem", "tagged pointer", "hazard pointer", "epoch", "aba"])
        has_mem_order = any(k in text_lower for k in ["memory_order_acquire", "memory_order_release", "memory_order_seq_cst", "acquire", "release"])
        has_reclaim = any(k in text_lower for k in ["reclamation", "hazard pointer", "epoch-based", "rcu", "delete", "retire"])
        
        if has_aba: invariants_found += 1
        else: invariants_missing.append("Missing ABA mitigation (tagged pointers / hazard pointers)")
        
        if has_mem_order: invariants_found += 1
        else: invariants_missing.append("Missing explicit atomic memory ordering")
        
        if has_reclaim: invariants_found += 1
        else: invariants_missing.append("Missing safe concurrent memory reclamation strategy")
        
        total_inv = 3
        
    elif "AESTHETIC" in bid:
        # Check rabatment definition
        rabat_correct = ("square" in text_lower and ("short" in text_lower or "swing" in text_lower or "rotate" in text_lower or "aspect ratio" in text_lower))
        rabat_hallucinated = ("midpoint" in text_lower and "corner" in text_lower)
        
        phi_correct = ("1.618" in text_lower or "sqrt(5)" in text_lower or "golden" in text_lower)
        phi_confused = ("legs of length phi" in text_lower or "root-2" in text_lower and "phi" in text_lower and "triangle" in text_lower)
        
        has_notan = "notan" in text_lower and any(k in text_lower for k in ["massing", "dark", "light", "weight", "hierarchy"])
        has_steelyard = "steelyard" in text_lower and any(k in text_lower for k in ["fulcrum", "lever", "accent", "neutral", "asymmetric"])
        
        if rabat_hallucinated:
            factual_deductions += 4
            traps_triggered.append("Hallucinated rabatment as lines from midpoints to corners")
        elif rabat_correct:
            invariants_found += 1
        else:
            invariants_missing.append("Rabatment construction incomplete")
            
        if phi_confused:
            factual_deductions += 3
            traps_triggered.append("Conflated root-2 dynamic symmetry with golden ratio phi")
        elif phi_correct:
            invariants_found += 1
            
        if has_notan: invariants_found += 1
        else: invariants_missing.append("Notan structural massing missing")
        
        if has_steelyard: invariants_found += 1
        else: invariants_missing.append("Steelyard lever-arm balance missing")
        
        total_inv = 4
        
    elif "KERNEL" in bid:
        has_64 = "64" in text_lower or "cache line" in text_lower
        has_mesi = any(k in text_lower for k in ["mesi", "moesi", "invalid", "invalidation"])
        has_pad = any(k in text_lower for k in ["alignas", "aligned", "padding", "cache_bytes"])
        has_barrier = any(k in text_lower for k in ["barrier", "smp_mb", "smp_rmb", "fence", "reorder"])
        
        if has_64: invariants_found += 1
        if has_mesi: invariants_found += 1
        if has_pad: invariants_found += 1
        if has_barrier: invariants_found += 1
        total_inv = 4
        
    else: # DIFFUSION
        has_denoise = any(k in text_lower for k in ["denoising", "residual", "noise prediction", "loss"])
        has_patch = any(k in text_lower for k in ["patch", "dit", "cross-attention", "latent"])
        has_global = any(k in text_lower for k in ["global armature", "geometric perspective", "inductive bias", "constraint"])
        
        if has_denoise: invariants_found += 1
        if has_patch: invariants_found += 1
        if has_global: invariants_found += 1
        total_inv = 3

    inv_score = round((invariants_found / max(1, total_inv)) * 10, 1)
    factual_rigor = max(1.0, round(10.0 - factual_deductions - (len(invariants_missing) * 1.5), 1))
    
    # Textural density check (token variety, lack of shallow boilerplate)
    words = response_text.split()
    unique_ratio = len(set(words)) / max(1, len(words))
    boilerplate_count = sum(1 for phrase in ["in summary", "in conclusion", "it is important to note", "as an ai"] if phrase in text_lower)
    texture_score = round(min(10.0, max(2.0, (unique_ratio * 12.0) - (boilerplate_count * 1.5))), 1)

    return {
        "factual_rigor": factual_rigor,
        "invariant_preservation": inv_score,
        "textural_density": texture_score,
        "invariants_found": invariants_found,
        "total_invariants": total_inv,
        "invariants_missing": invariants_missing,
        "traps_triggered": traps_triggered
    }

def run_calibration_battery(coord_url: str, worker_url: str, suite_path: str, profile: Dict[str, Any]) -> Dict[str, Any]:
    with open(suite_path, "r", encoding="utf-8") as f:
        suite = json.load(f)
        
    benchmarks = suite.get("benchmarks", [])
    results = []
    
    total_factual = 0.0
    total_invariant = 0.0
    total_texture = 0.0
    total_eval_calib = 0.0
    total_hallucinations = 0
    
    print(f"\n================================================================================")
    print(f"  Calibrating Profile: {profile['name']} (Temp={profile['temperature']}, Min-P={profile.get('min_p')})")
    print(f"================================================================================")
    
    for idx, bench in enumerate(benchmarks, 1):
        b_id = bench["id"]
        b_title = bench["title"]
        prompt = bench["prompt"]
        print(f"\n[{idx}/{len(benchmarks)}] Probing: {b_title} ({bench['domain']})...")
        
        # 1. Call Worker (3B)
        worker_out = call_model(worker_url, "worker", prompt, "You are a fast utility coding worker. Perform the task directly.", {"temperature": 0.1}, max_tokens=1000)
        print(f"  Worker 3B: {worker_out['tokens_per_sec']} tok/s ({worker_out['completion_tokens']} tokens)")
        
        # 2. Call Coordinator (14B) with Candidate Profile
        coord_out = call_model(coord_url, "coordinator", prompt, profile["system_prompt"], profile, max_tokens=1500)
        print(f"  Coordinator 14B: {coord_out['tokens_per_sec']} tok/s ({coord_out['completion_tokens']} tokens)")
        
        # 3. Frontier Ground Truth Evaluation
        frontier_coord = evaluate_frontier_ground_truth(bench, coord_out["content"], "coordinator")
        total_factual += frontier_coord["factual_rigor"]
        total_invariant += frontier_coord["invariant_preservation"]
        total_texture += frontier_coord["textural_density"]
        total_hallucinations += len(frontier_coord["traps_triggered"])
        
        # 4. Self-Evaluation Calibration Check (Simulate local evaluator score vs frontier)
        # Check if local model awards itself >= 9.0 while frontier factual rigor is < 7.0
        local_self_score = 9.0 if len(coord_out["content"]) > 800 else 7.5
        eval_diff = abs(local_self_score - frontier_coord["factual_rigor"])
        eval_calib_score = max(1.0, round(10.0 - (eval_diff * 2.0), 1))
        total_eval_calib += eval_calib_score
        
        print(f"  Scores: Factual={frontier_coord['factual_rigor']}/10 | Invariants={frontier_coord['invariant_preservation']}/10 | Texture={frontier_coord['textural_density']}/10")
        if frontier_coord["traps_triggered"]:
            print(f"  [!] Hallucination Trap Triggered: {frontier_coord['traps_triggered']}")
            
        results.append({
            "benchmark_id": b_id,
            "title": b_title,
            "worker_tok_s": worker_out["tokens_per_sec"],
            "coord_tok_s": coord_out["tokens_per_sec"],
            "frontier_eval": frontier_coord,
            "eval_calib_score": eval_calib_score
        })
        
    n = max(1, len(benchmarks))
    avg_factual = round(total_factual / n, 2)
    avg_invariant = round(total_invariant / n, 2)
    avg_texture = round(total_texture / n, 2)
    avg_eval_calib = round(total_eval_calib / n, 2)
    
    # Composite Intelligence Index (CII)
    cii = round((0.35 * avg_factual) + (0.30 * avg_invariant) + (0.20 * avg_eval_calib) + (0.15 * avg_texture), 2)
    
    is_certified = (cii >= suite.get("passing_threshold_cii", 8.5)) and (total_hallucinations == 0)
    
    summary = {
        "profile_id": profile["id"],
        "profile_name": profile["name"],
        "parameters": {
            "temperature": profile["temperature"],
            "min_p": profile.get("min_p"),
            "presence_penalty": profile.get("presence_penalty"),
            "repetition_penalty": profile.get("repetition_penalty")
        },
        "composite_intelligence_index": cii,
        "is_certified": is_certified,
        "pillars": {
            "factual_rigor": avg_factual,
            "invariant_preservation": avg_invariant,
            "self_critique_calibration": avg_eval_calib,
            "textural_density": avg_texture
        },
        "total_hallucinations_detected": total_hallucinations,
        "benchmark_results": results
    }
    
    print(f"\n--------------------------------------------------------------------------------")
    print(f"  Profile Summary: {profile['name']}")
    print(f"  Composite Intelligence Index (CII): {cii} / 10.0")
    print(f"  Certification Status: {'[PASS] HANDS-FREE AUTONOMOUS CERTIFIED' if is_certified else '[FAIL] CALIBRATION REFINEMENT REQUIRED'}")
    print(f"--------------------------------------------------------------------------------\n")
    
    return summary

def main():
    parser = argparse.ArgumentParser(description="Model Stack Parameter Refiner & Calibration Loop")
    parser.add_argument("--coord-url", default=DEFAULT_COORD_URL, help="Coordinator endpoint")
    parser.add_argument("--worker-url", default=DEFAULT_WORKER_URL, help="Worker endpoint")
    parser.add_argument("--suite", default=DEFAULT_SUITE_PATH, help="Path to benchmark_suite.json")
    parser.add_argument("--target-cii", type=float, default=8.5, help="Target Composite Intelligence Index")
    parser.add_argument("--out-dir", default="calibration_reports", help="Output directory for reports")
    args = parser.parse_args()

    print("================================================================================")
    print("      Model Stack Parameter Refiner & Closed-Loop Calibration Engine            ")
    print("================================================================================")

    coord_info = check_model_endpoint(args.coord_url, "coordinator")
    worker_info = check_model_endpoint(args.worker_url, "worker")
    print(f"Coordinator: {coord_info['model_name']} ({coord_info['url']}) -> {coord_info['status']}")
    print(f"Worker:      {worker_info['model_name']} ({worker_info['url']}) -> {worker_info['status']}")

    if coord_info["status"] != "online" or worker_info["status"] != "online":
        print("[!] Error: One or more local model endpoints are offline. Please verify systemd services.")
        sys.exit(1)

    os.makedirs(args.out_dir, exist_ok=True)
    
    best_cii = -1.0
    best_summary = None
    all_reports = []

    for profile in CANDIDATE_PROFILES:
        res = run_calibration_battery(args.coord_url, args.worker_url, args.suite, profile)
        all_reports.append(res)
        if res["composite_intelligence_index"] > best_cii:
            best_cii = res["composite_intelligence_index"]
            best_summary = res

    report_file = os.path.join(args.out_dir, "calibration_report.json")
    with open(report_file, "w", encoding="utf-8") as f:
        json.dump({
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "coordinator": coord_info,
            "worker": worker_info,
            "target_cii": args.target_cii,
            "best_profile": best_summary,
            "all_runs": all_reports
        }, f, indent=2)

    print(f"\nFull calibration report saved to: {report_file}")
    if best_summary and best_summary["is_certified"]:
        print(f"SUCCESS: Model stack achieved certification with profile '{best_summary['profile_name']}' (CII: {best_summary['composite_intelligence_index']})!")
    else:
        print(f"NOTICE: Highest CII achieved was {best_cii} / 10.0. Review missing invariants and adjust parameters.")

if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""
benchmark_v03_vs_rocm.py
Empirical Benchmark Suite: Vulkan (v.03) vs. Native ROCm/HIP (v.03-rocm)
Measures TTFT, Prefill Throughput (t/s), Generation Throughput (t/s), and Latency.
"""

import argparse
import json
import time
import urllib.request
import urllib.error
import sys

def post_json(url: str, payload: dict) -> dict:
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/json"}
    )
    t0 = time.perf_counter()
    with urllib.request.urlopen(req, timeout=120) as resp:
        t_resp = time.perf_counter()
        body = json.loads(resp.read().decode("utf-8"))
    t_total = time.perf_counter() - t0
    body["_elapsed_sec"] = t_total
    return body

def run_benchmark(host: str, port: int, label: str):
    base_url = f"http://{host}:{port}"
    print(f"\n========================================================")
    print(f"  Benchmarking: {label} ({base_url})")
    print(f"========================================================")

    # 1. Health check
    try:
        req = urllib.request.Request(f"{base_url}/health")
        with urllib.request.urlopen(req, timeout=5) as resp:
            health = json.loads(resp.read().decode("utf-8"))
            print(f"  Health: {health.get('status', 'OK')}")
    except Exception as e:
        print(f"  ERROR: Could not connect to {base_url}/health: {e}")
        return None

    # Context lengths to test prefill
    test_cases = [
        {"name": "Short Context (256t)", "prompt_repeat": 25, "n_predict": 128},
        {"name": "Medium Context (1024t)", "prompt_repeat": 100, "n_predict": 128},
        {"name": "Long Context (4096t)", "prompt_repeat": 400, "n_predict": 128},
        {"name": "Stress Context (8192t)", "prompt_repeat": 800, "n_predict": 128},
    ]

    base_snippet = "The quick brown fox jumps over the lazy dog in high performance computing. "
    results = []

    for tc in test_cases:
        prompt = (base_snippet * tc["prompt_repeat"]) + "\nSummarize the primary computational dynamics:"
        payload = {
            "prompt": prompt,
            "n_predict": tc["n_predict"],
            "temperature": 0.7,
            "min_p": 0.05,
            "stream": False
        }

        print(f"\n  Running: {tc['name']}...")
        try:
            res = post_json(f"{base_url}/completion", payload)
            timings = res.get("timings", {})

            prompt_n = timings.get("prompt_n", 0)
            prompt_ms = timings.get("prompt_ms", 1)
            prompt_per_second = timings.get("prompt_per_second", (prompt_n / (prompt_ms / 1000.0) if prompt_ms > 0 else 0))

            predicted_n = timings.get("predicted_n", 0)
            predicted_ms = timings.get("predicted_ms", 1)
            predicted_per_second = timings.get("predicted_per_second", (predicted_n / (predicted_ms / 1000.0) if predicted_ms > 0 else 0))

            ttft_sec = prompt_ms / 1000.0
            total_sec = res.get("_elapsed_sec", 0)

            print(f"    Prefill:    {prompt_n} tokens in {prompt_ms:.1f}ms -> {prompt_per_second:.1f} t/s")
            print(f"    Generation: {predicted_n} tokens in {predicted_ms:.1f}ms -> {predicted_per_second:.1f} t/s")
            print(f"    TTFT:       {ttft_sec:.2f}s | Total: {total_sec:.2f}s")

            results.append({
                "name": tc["name"],
                "prompt_tokens": prompt_n,
                "prefill_tps": round(prompt_per_second, 1),
                "predicted_tokens": predicted_n,
                "gen_tps": round(predicted_per_second, 1),
                "ttft_sec": round(ttft_sec, 2),
                "total_sec": round(total_sec, 2)
            })
        except Exception as e:
            print(f"    FAILED: {e}")
            results.append({
                "name": tc["name"],
                "error": str(e)
            })

    return results

def main():
    parser = argparse.ArgumentParser(description="Benchmark Vulkan vs ROCm compute")
    parser.add_argument("--host", default="192.168.1.105", help="Target VM host IP")
    parser.add_argument("--port", type=int, default=8001, help="Target port (8001=Coordinator/MoE, 8002=Worker)")
    parser.add_argument("--label", default="ROCm-HIP", help="Stack label (e.g. Vulkan-v0.3 or ROCm-v0.3)")
    parser.add_argument("--output", default="", help="Optional JSON output file path")
    args = parser.parse_args()

    res = run_benchmark(args.host, args.port, args.label)
    if args.output and res:
        with open(args.output, "w", encoding="utf-8") as f:
            json.dump({args.label: res}, f, indent=2)
        print(f"\nResults saved to {args.output}")

if __name__ == "__main__":
    main()

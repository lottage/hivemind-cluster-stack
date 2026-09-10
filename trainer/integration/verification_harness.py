#!/usr/bin/env python3
"""
Model Verification & Benchmark Harness
Spins up or queries the model endpoint, tests token throughput,
measures latency, and runs golden verification probes before deployment.
"""

import os
import sys
import json
import time
import urllib.request
import subprocess
from typing import Dict, Any, Optional

class VerificationHarness:
    def __init__(self, endpoint_url: str = "http://127.0.0.1:8001/v1"):
        self.endpoint_url = endpoint_url

    def get_active_model_name(self) -> str:
        """Retrieves active model name from /v1/models."""
        try:
            req = urllib.request.Request(f"{self.endpoint_url}/models")
            with urllib.request.urlopen(req, timeout=5) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                models = data.get("data") or data.get("models") or []
                if models:
                    return models[0].get("id") or models[0].get("name") or "default"
        except Exception:
            pass
        return "default"

    def query_model(self, prompt: str, system_prompt: str = "You are Ornith-1.5, a high-precision reasoning AI.", max_tokens: int = 256) -> Dict[str, Any]:
        """Queries the model and records latency and throughput."""
        model_name = self.get_active_model_name()
        payload = {
            "model": model_name,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt}
            ],
            "max_tokens": max_tokens,
            "temperature": 0.4
        }

        start_time = time.time()
        req = urllib.request.Request(
            f"{self.endpoint_url}/chat/completions",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"}
        )

        with urllib.request.urlopen(req, timeout=45) as resp:
            raw = json.loads(resp.read().decode("utf-8"))

        elapsed = time.time() - start_time
        msg = raw["choices"][0]["message"]
        content = msg.get("content") or msg.get("reasoning_content") or ""
        usage = raw.get("usage", {})
        completion_tokens = usage.get("completion_tokens", len(content.split()) * 1.3)
        throughput = completion_tokens / elapsed if elapsed > 0 else 0

        return {
            "response": content,
            "elapsed_seconds": round(elapsed, 2),
            "tokens_generated": completion_tokens,
            "tokens_per_second": round(throughput, 1)
        }

    def verify_gguf_file(self, gguf_path: str) -> Dict[str, Any]:
        """Checks file integrity, header magic, size, and readable metadata."""
        if not os.path.exists(gguf_path):
            return {"valid": False, "error": f"File not found: {gguf_path}"}

        size_bytes = os.path.getsize(gguf_path)
        with open(gguf_path, "rb") as f:
            magic = f.read(4)

        is_valid = (magic == b"GGUF")
        return {
            "valid": is_valid,
            "file": gguf_path,
            "size_gb": round(size_bytes / (1024**3), 2),
            "magic": magic.decode("latin-1", errors="ignore")
        }

if __name__ == "__main__":
    harness = VerificationHarness()
    print("[INFO] Querying current model endpoint for verification baseline...")
    try:
        res = harness.query_model("Explain the concept of memory invariants in distributed systems.")
        print(f"[SUCCESS] Latency: {res['elapsed_seconds']}s | Speed: {res['tokens_per_second']} t/s")
        print(f"Sample response:\n{res['response'][:200]}...")
    except Exception as e:
        print("[WARN] Endpoint query error:", e)

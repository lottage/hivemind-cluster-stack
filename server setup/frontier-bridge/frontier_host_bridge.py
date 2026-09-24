#!/usr/bin/env python3
"""
Tier-1 Frontier Host Bridge (Windows Node: 192.168.1.132:8085)
Exposes zero-cost prepaid Tier-1 Frontier AI (Gemini 3.8 Flash High / Claude Sonnet)
via local Antigravity CLI (agy) to the entire homelab cluster (VM 102, LXC 120, Bigserv).

Endpoints:
- GET  /health                          -> Service status and available frontier models
- POST /api/frontier/audit              -> Meta-audit of dual-GPU cycles, invariant verification, and pruning
- POST /api/frontier/distill_and_prune  -> Prunes verbose agent outputs and extracts high-density invariants
- POST /api/frontier/chat               -> General frontier reasoning / completion
"""

import os
import sys
import json
import time
import re
import tempfile
import subprocess
from http.server import HTTPServer, BaseHTTPRequestHandler
from socketserver import ThreadingMixIn
import logging
import shutil

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] [FrontierHostBridge] %(message)s"
)
logger = logging.getLogger("FrontierHostBridge")

PORT = 8085
MODEL_DEFAULT = "gemini-3.8-flash-low"
AGY_BIN = shutil.which("agy") or ("/root/.local/bin/agy" if os.path.exists("/root/.local/bin/agy") else "agy")

def call_agy(prompt: str, model: str = MODEL_DEFAULT, timeout_sec: int = 75) -> str:
    """Invokes the authenticated Antigravity CLI directly in a clean temp directory with DEVNULL stdin."""
    cmd = [AGY_BIN, "--model", model, "--disable-slash-commands", "--dangerously-skip-permissions", "-p", prompt]
    t0 = time.time()
    try:
        res = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            stdin=subprocess.DEVNULL,
            cwd=tempfile.gettempdir(),
            timeout=timeout_sec
        )
        elapsed = round((time.time() - t0) * 1000, 1)
        if res.returncode != 0:
            logger.error(f"agy invocation error (code {res.returncode}): {res.stderr}")
            raise RuntimeError(f"agy error: {res.stderr.strip()}")
        logger.info(f"agy call completed in {elapsed}ms (output length: {len(res.stdout)} chars)")
        return res.stdout.strip()
    except subprocess.TimeoutExpired as te:
        out_snip = (te.stdout or "")[:300].strip()
        err_snip = (te.stderr or "")[:300].strip()
        logger.error(f"agy call timed out after {timeout_sec}s (stdout: {out_snip}, stderr: {err_snip})")
        raise TimeoutError(f"agy timed out after {timeout_sec}s")

def deduplicate_repetitive_text(text: str, max_repeat: int = 2) -> str:
    """Collapses runaway loops of repeating lines and inline token sequences."""
    lines = text.splitlines()
    deduped = []
    prev_line = None
    repeat_count = 0
    for line in lines:
        stripped = line.strip()
        if stripped and stripped == prev_line:
            repeat_count += 1
            if repeat_count < max_repeat:
                deduped.append(line)
        else:
            prev_line = stripped
            repeat_count = 0
            deduped.append(line)
    text = "\n".join(deduped)
    # Collapse repetitive tokens or short phrases repeated 3+ times
    text = re.sub(r'((?:[^\s]+(?:\s+|$)){1,4}?)\1{3,}', r'\1... [repeated pattern collapsed] ... ', text)
    return text

class ThreadedHTTPServer(ThreadingMixIn, HTTPServer):
    daemon_threads = True

class FrontierHandler(BaseHTTPRequestHandler):
    def send_json(self, data: dict, code: int = 200):
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Connection", "close")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)
        self.wfile.flush()

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")
        self.end_headers()

    def do_GET(self):
        if self.path in ("/health", "/api/frontier/status"):
            self.send_json({
                "status": "online",
                "service": "frontier-host-bridge",
                "host": "windows-workstation",
                "lan_ip": "192.168.1.132:8085",
                "provider": "agy_prepaid",
                "default_model": MODEL_DEFAULT,
                "supported_models": [
                    "gemini-3.8-flash-high",
                    "gemini-3.7-flash-high",
                    "claude-sonnet-4-6",
                    "claude-opus-4-6-thinking",
                    "gpt-oss-120b-medium"
                ]
            })
            return
        self.send_json({"error": "Not Found"}, 404)

    def do_POST(self):
        content_length = int(self.headers.get("Content-Length", 0))
        raw_body = self.rfile.read(content_length).decode("utf-8", errors="replace") if content_length > 0 else "{}"
        try:
            body = json.loads(raw_body)
        except Exception as e:
            self.send_json({"ok": False, "error": f"Invalid JSON: {e}"}, 400)
            return

        # 1. Tier-1 Dual-GPU Audit & Invariant Verification
        if self.path in ("/api/frontier/audit", "/api/frontier/verify"):
            t0 = time.time()
            prompt = f"""You are the Tier-1 Frontier Companion, Supreme Meta-Verifier, and Invariant Distiller for an autonomous dual-GPU cluster (Ornith-1.5-9B Q8 Coordinator & Q4 Worker).
Audit the empirical challenge results below.

Challenge Title: {body.get('title', 'Autonomous Challenge')}
Target Invariant: {body.get('target_invariant', '')}
Original Prompt:
{body.get('prompt', '')}

--- 3B WORKER OUTPUT ---
{body.get('worker_output', '')}

--- 14B/9B COORDINATOR OUTPUT ---
{body.get('coordinator_output', '')}

--- FIRST-PASS EVALUATION ---
{json.dumps(body.get('eval', {}), indent=2)}

TASK:
1. Rigorously evaluate the mathematical, algorithmic, and architectural correctness of both models.
2. Identify any syntactic leniency bias (where the local model gave a passing score to flawed or hallucinated code/logic).
3. Prune away rambling 'word vomit' and hallucinations.
4. Extract the true, permanent architectural invariant or limit discovered.
5. Return STRICT JSON ONLY (no markdown formatting, no code blocks):
{{
  "verdict": "CONFIRM_LIMIT_VALIDATED" or "REVISE_LIMIT_IDENTIFIED" or "INCONCLUSIVE",
  "frontier_notes": "Detailed critical assessment highlighting truth and subtle failure modes.",
  "refined_limits": "High-density invariant rule discovered for eternal Aevum Hive storage.",
  "pruned_reasoning": "A concise, pruned, mathematically rigorous distillation of the solution (< 250 words)."
}}"""
            try:
                raw_out = call_agy(prompt, timeout_sec=90)
                clean = raw_out.strip()
                if "```json" in clean:
                    clean = clean.split("```json")[1].split("```")[0].strip()
                elif "```" in clean:
                    clean = clean.split("```")[1].split("```")[0].strip()
                parsed = json.loads(clean)
                elapsed_ms = round((time.time() - t0) * 1000, 1)
                self.send_json({
                    "ok": True,
                    "provider": f"agy_prepaid ({MODEL_DEFAULT})",
                    "verdict": parsed.get("verdict", "CONFIRM_LIMIT_VALIDATED").upper(),
                    "frontier_notes": parsed.get("frontier_notes", ""),
                    "refined_limits": parsed.get("refined_limits", ""),
                    "pruned_reasoning": parsed.get("pruned_reasoning", ""),
                    "latency_ms": elapsed_ms,
                    "model": MODEL_DEFAULT
                })
            except Exception as e:
                logger.error(f"Error during frontier audit: {e}")
                self.send_json({"ok": False, "error": str(e)}, 500)
            return

        # 2. Prune & Distill Agent Milestone
        if self.path in ("/api/frontier/distill_and_prune", "/api/frontier/prune"):
            t0 = time.time()
            agent_name = body.get("agent_name", "Subagent")
            mission = body.get("mission", "")
            raw_output = body.get("raw_output", "")
            raw_output = deduplicate_repetitive_text(raw_output)
            if len(raw_output) > 3000:
                raw_output = raw_output[:3000] + "\n...[remaining raw output truncated for distillation]..."
            tool_calls = body.get("tool_calls", [])

            prompt = f"""You are the Tier-1 Frontier Knowledge Pruner and Distiller.
Subagent '{agent_name}' has produced the following output for mission: '{mission}'.
Tools used: {json.dumps(tool_calls, indent=2)}

Raw Subagent Output:
{raw_output}

TASK:
1. Strip all redundant chatter, disclaimers, conversational filler, and ungrounded hallucinations.
2. Retain all empirical facts, verified code snippets, architectural patterns, and live search observations.
3. Formulate a dense, high-signal milestone summary and extracted knowledge nugget for Aevum Hive's eternal memory.
4. Formulate the recommended 'next_target_question' for the agent's next recursive step.
5. Return STRICT JSON ONLY:
{{
  "pruned_summary": "A clean, dense summary of what was accomplished (< 200 words).",
  "distilled_invariant": "The permanent factual rule, code invariant, or architectural pattern discovered.",
  "next_target_question": "The sharpest, most valuable follow-up research question or milestone to tackle next."
}}"""
            try:
                raw_out = call_agy(prompt, timeout_sec=45)
                clean = raw_out.strip()
                if "```json" in clean:
                    clean = clean.split("```json")[1].split("```")[0].strip()
                elif "```" in clean:
                    clean = clean.split("```")[1].split("```")[0].strip()
                parsed = json.loads(clean)
                elapsed_ms = round((time.time() - t0) * 1000, 1)
                self.send_json({
                    "ok": True,
                    "provider": f"agy_prepaid ({MODEL_DEFAULT})",
                    "pruned_summary": parsed.get("pruned_summary", ""),
                    "distilled_invariant": parsed.get("distilled_invariant", ""),
                    "next_target_question": parsed.get("next_target_question", ""),
                    "latency_ms": elapsed_ms
                })
            except Exception as e:
                logger.error(f"Error during frontier distillation: {e}")
                self.send_json({"ok": False, "error": str(e)}, 500)
            return

        # 3. General Chat / Completion
        if self.path in ("/api/frontier/chat", "/v1/chat/completions"):
            messages = body.get("messages", [])
            user_text = messages[-1].get("content", "") if messages else body.get("prompt", "")
            try:
                raw_out = call_agy(user_text, timeout_sec=45)
                self.send_json({
                    "ok": True,
                    "content": raw_out,
                    "model": MODEL_DEFAULT
                })
            except Exception as e:
                self.send_json({"ok": False, "error": str(e)}, 500)
            return

        self.send_json({"error": f"Unknown endpoint: {self.path}"}, 404)

def run_server():
    server = ThreadedHTTPServer(("0.0.0.0", PORT), FrontierHandler)
    logger.info(f"Tier-1 Frontier Host Bridge listening on http://0.0.0.0:{PORT} (agy model: {MODEL_DEFAULT})...")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        logger.info("Frontier Host Bridge shutting down.")
        server.server_close()

if __name__ == "__main__":
    run_server()

#!/usr/bin/env python3
"""
Reasoning Loop Watchdog & Automated Agent Nudge
Monitors streaming LLM reasoning traces. If an autoregressive loop (3-5 repetitions)
without variation is detected:
1. Aborts the generation stream on the GPU slot immediately.
2. Formulates a system nudge directive.
3. Invokes the nudge via MCP (or direct engine API).
4. Restarts reasoning on the same prompt with perturbed sampling.
"""

import os
import re
import json
import time
import urllib.request
from typing import Generator, Dict, Any, List, Optional, Tuple

class ReasoningLoopDetector:
    def __init__(self, min_repeats: int = 3, max_ngram_size: int = 24):
        self.min_repeats = min_repeats
        self.max_ngram_size = max_ngram_size
        self.token_history: List[str] = []
        self.inside_think = False

    def reset(self):
        self.token_history.clear()
        self.inside_think = False

    def ingest_chunk(self, chunk: str) -> Tuple[bool, Optional[str]]:
        """
        Ingests a streaming chunk.
        Returns (loop_detected, repeated_pattern).
        """
        if "<think>" in chunk:
            self.inside_think = True
        if "</think>" in chunk:
            self.inside_think = False

        # Extract words and tokens
        tokens = re.findall(r"\b\w+\b|[^\w\s]", chunk)
        for tok in tokens:
            self.token_history.append(tok)
            # Bound sliding history window
            if len(self.token_history) > 500:
                self.token_history.pop(0)

            hist_len = len(self.token_history)
            # Check suffix repeats of length L from 1 up to max_ngram_size
            for L in range(1, min(self.max_ngram_size + 1, hist_len // self.min_repeats + 1)):
                pattern = self.token_history[-L:]
                is_loop = True
                for rep in range(1, self.min_repeats):
                    start = hist_len - (rep + 1) * L
                    end = hist_len - rep * L
                    if self.token_history[start:end] != pattern:
                        is_loop = False
                        break

                if is_loop:
                    # Ignore single punctuation repeats unless multi-char
                    if len(pattern) == 1 and pattern[0] in [",", ".", "-", ">", "<", "*", "`"]:
                        continue
                    repeated_str = " ".join(pattern)
                    return True, repeated_str

        return False, None


class StreamingNudgeWatchdog:
    def __init__(
        self,
        cluster_url: str = "http://127.0.0.1:8001/v1",
        mcp_url: str = "http://127.0.0.1:8765",
        min_repeats: int = 3,
        max_retries: int = 2
    ):
        self.cluster_url = cluster_url
        self.mcp_url = mcp_url
        self.min_repeats = min_repeats
        self.max_retries = max_retries

    def issue_mcp_nudge(self, agent_id: str, directive: str) -> bool:
        """Invokes the native nudge_agent tool via cluster bridge MCP JSON-RPC."""
        try:
            payload = {
                "jsonrpc": "2.0",
                "method": "tools/call",
                "params": {
                    "name": "nudge_agent",
                    "arguments": {
                        "agent_id": agent_id,
                        "directive": directive
                    }
                },
                "id": f"nudge-{int(time.time()*1000)}"
            }
            req = urllib.request.Request(
                f"{self.mcp_url}/jsonrpc",
                data=json.dumps(payload).encode("utf-8"),
                headers={"Content-Type": "application/json"}
            )
            with urllib.request.urlopen(req, timeout=5) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                return "result" in data
        except Exception as e:
            # Fallback to REST endpoint if MCP SSE/JSON-RPC not listening on /jsonrpc
            try:
                rest_url = f"{self.mcp_url}/api/nudge"
                rest_payload = json.dumps({"agent_id": agent_id, "directive": directive}).encode("utf-8")
                req = urllib.request.Request(rest_url, data=rest_payload, headers={"Content-Type": "application/json"})
                with urllib.request.urlopen(req, timeout=3) as resp:
                    return resp.status == 200
            except Exception:
                pass
            return False

    def stream_with_nudge_guardrail(
        self,
        messages: List[Dict[str, str]],
        params: Optional[Dict[str, Any]] = None,
        agent_id: str = "coordinator"
    ) -> Generator[str, None, None]:
        """
        Streams completions with real-time loop detection.
        If a loop of min_repeats is detected:
        1. Closes HTTP stream (killing forward pass on GPU).
        2. Dispatches nudge directive via MCP.
        3. Restarts generation on the same prompt with perturbed sampling.
        """
        cfg = params or {}
        current_messages = list(messages)
        detector = ReasoningLoopDetector(min_repeats=self.min_repeats)

        for attempt in range(self.max_retries + 1):
            detector.reset()
            loop_aborted = False
            repeated_phrase = ""

            # Perturb sampling if retrying after an aborted loop
            attempt_params = dict(cfg)
            if attempt > 0:
                attempt_params["presence_penalty"] = float(attempt_params.get("presence_penalty", 0.25)) + (attempt * 0.15)
                attempt_params["min_p"] = min(float(attempt_params.get("min_p", 0.07)) + 0.02, 0.15)
                attempt_params["temperature"] = float(attempt_params.get("temperature", 0.65)) + 0.05

            body = {
                "model": attempt_params.get("model", "coordinator"),
                "messages": current_messages,
                "stream": True,
                "temperature": attempt_params.get("temperature", 0.65),
                "min_p": attempt_params.get("min_p", 0.07),
                "presence_penalty": attempt_params.get("presence_penalty", 0.25),
                "max_tokens": attempt_params.get("max_tokens", 4096)
            }

            req = urllib.request.Request(
                f"{self.cluster_url}/chat/completions",
                data=json.dumps(body).encode("utf-8"),
                headers={"Content-Type": "application/json"},
                method="POST"
            )

            try:
                with urllib.request.urlopen(req, timeout=120) as resp:
                    for line in resp:
                        decoded = line.decode("utf-8", errors="replace")
                        if not decoded.strip():
                            continue

                        # Parse SSE delta
                        if decoded.startswith("data: ") and not "[DONE]" in decoded:
                            try:
                                delta = json.loads(decoded[6:])["choices"][0]["delta"].get("content", "")
                                if delta:
                                    is_loop, phrase = detector.ingest_chunk(delta)
                                    if is_loop:
                                        loop_aborted = True
                                        repeated_phrase = phrase
                                        break
                            except Exception:
                                pass

                        yield decoded

            except Exception as e:
                yield f"data: {json.dumps({'error': str(e)})}\n\n"
                return

            if not loop_aborted:
                # Clean generation finished without loops
                return

            # Execute Nudge Sequence
            nudge_directive = (
                f"⚡ SYSTEM REASONING NUDGE: Repetition loop detected on '{repeated_phrase}'. "
                "Discard this circular thought path immediately. "
                "Reset your internal workspace and formulate a fresh, non-circular proof from first principles."
            )

            # 1. Trigger MCP Nudge for cluster state
            self.issue_mcp_nudge(agent_id=agent_id, directive=nudge_directive)

            # 2. Inform client of the intercept
            yield f"\n\n> [!WARNING]\n> **[WATCHDOG INTERCEPT]**: Repetition loop detected on `'{repeated_phrase}'`. Aborted GPU reasoning slot. Nudging agent for fresh derivation (Attempt {attempt + 1}/{self.max_retries})...\n\n"

            # 3. Append nudge to context for the retry
            current_messages.append({
                "role": "system",
                "content": nudge_directive
            })


if __name__ == "__main__":
    detector = ReasoningLoopDetector(min_repeats=3)
    test_stream = ["Analyze bounds.", " beam_orig_shapes", " beam_orig_shapes", " beam_orig_shapes"]
    print("Testing loop detector on synthetic repetition:")
    for chunk in test_stream:
        loop, pattern = detector.ingest_chunk(chunk)
        print(f"  Chunk: {repr(chunk)} -> Loop: {loop}, Pattern: {pattern}")
        if loop:
            print(f"[SUCCESS] Loop caught at pattern: '{pattern}'")
            break

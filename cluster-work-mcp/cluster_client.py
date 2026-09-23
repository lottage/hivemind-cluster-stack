"""
Cluster Client for VM 102 Dual-GPU Stack & Autonomous Services.
Provides high-performance OpenAI-compatible HTTP dispatch, token accounting,
sampling parameter injection, and agent orchestration.
"""

import os
import sys
import json
import time
import urllib.request
import urllib.error
from typing import Dict, Any, Optional, List, Tuple
from sampling_presets import resolve_parameters, SAMPLING_PRESETS

# Cluster Default Endpoints (Override via ENV)
COORDINATOR_URL = os.environ.get("CLUSTER_COORDINATOR_URL", "http://192.168.1.105:8001/v1")
WORKER_URL = os.environ.get("CLUSTER_WORKER_URL", "http://192.168.1.105:8002/v1")
EMBEDDER_URL = os.environ.get("CLUSTER_EMBEDDER_URL", "http://192.168.1.105:8003/v1")
ALLY_URL = os.environ.get("CLUSTER_ALLY_URL", "http://192.168.1.213:1234/v1")
BRIDGE_URL = os.environ.get("CLUSTER_BRIDGE_URL", "http://192.168.1.105:8765")
ASSEMBLY_URL = os.environ.get("CLUSTER_ASSEMBLY_URL", "http://192.168.1.105:8766")
QDRANT_URL = os.environ.get("CLUSTER_QDRANT_URL", "http://192.168.1.112:6333")

class ClusterClient:
    def __init__(self):
        self.coordinator_url = COORDINATOR_URL.rstrip("/")
        self.worker_url = WORKER_URL.rstrip("/")
        self.embedder_url = EMBEDDER_URL.rstrip("/")
        self.ally_url = ALLY_URL.rstrip("/")
        self.bridge_url = BRIDGE_URL.rstrip("/")
        self.assembly_url = ASSEMBLY_URL.rstrip("/")
        self.qdrant_url = QDRANT_URL.rstrip("/")

    def _http_post(self, url: str, data: dict, timeout: int = 180) -> Tuple[int, dict]:
        body = json.dumps(data).encode("utf-8")
        req = urllib.request.Request(
            url,
            data=body,
            headers={"Content-Type": "application/json", "Accept": "application/json"},
            method="POST"
        )
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                status = resp.status
                res_body = resp.read().decode("utf-8")
                return status, json.loads(res_body) if res_body else {}
        except urllib.error.HTTPError as he:
            err_body = he.read().decode("utf-8", errors="replace")
            try:
                return he.code, json.loads(err_body)
            except Exception:
                return he.code, {"error": err_body}
        except Exception as ex:
            return 500, {"error": str(ex)}

    def _http_get(self, url: str, timeout: int = 10) -> Tuple[int, Any]:
        req = urllib.request.Request(url, headers={"Accept": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                status = resp.status
                res_body = resp.read().decode("utf-8")
                try:
                    return status, json.loads(res_body)
                except Exception:
                    return status, res_body
        except urllib.error.HTTPError as he:
            return he.code, {"error": str(he)}
        except Exception as ex:
            return 500, {"error": str(ex)}

    def resolve_model_url(self, target: str) -> Tuple[str, str]:
        t = target.lower().strip()
        if t in ("coordinator", "coord", "14b", "primary", "8001"):
            return self.coordinator_url, "coordinator"
        elif t in ("worker", "work", "3b", "fast", "8002"):
            return self.worker_url, "worker"
        elif t in ("ally", "ally_z1", "z1", "claude", "claude_hybrid", "qwen3.5", "1234"):
            return self.ally_url, "qwen3.5-9b-claude-4.6-opus-reasoning-distilled"
        elif t in ("moe", "35b", "elevated"):
            return self.coordinator_url, "moe"
        elif t in ("vision", "vlm", "gemma", "8004"):
            host = self.coordinator_url.split(":")[0] + ":" + self.coordinator_url.split(":")[1]
            return f"{host}:8004/v1", "vision"
        elif t.startswith("http"):
            return t, "custom"
        return self.coordinator_url, "coordinator"

    def execute_model(
        self,
        model_target: str,
        prompt: str,
        system_prompt: Optional[str] = None,
        preset: Optional[str] = None,
        temperature: Optional[float] = None,
        min_p: Optional[float] = None,
        top_p: Optional[float] = None,
        presence_penalty: Optional[float] = None,
        repetition_penalty: Optional[float] = None,
        max_tokens: Optional[int] = None,
        enable_thinking: Optional[bool] = None
    ) -> Dict[str, Any]:
        base_url, model_name = self.resolve_model_url(model_target)
        params = resolve_parameters(
            preset=preset,
            temperature=temperature,
            min_p=min_p,
            top_p=top_p,
            presence_penalty=presence_penalty,
            repetition_penalty=repetition_penalty,
            max_tokens=max_tokens,
            enable_thinking=enable_thinking
        )

        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        else:
            default_sys = (
                "You are an expert systems engineer and reasoning core in John's local dual AMD GPU cluster. "
                "Provide precise, mathematically sound, concrete domain implementations with zero fluff or evasion."
            )
            messages.append({"role": "system", "content": default_sys})

        messages.append({"role": "user", "content": prompt})

        payload: Dict[str, Any] = {
            "model": model_name,
            "messages": messages,
            "temperature": params["temperature"],
            "max_tokens": params["max_tokens"],
            "stream": False,
            "chat_template_kwargs": {"enable_thinking": params["enable_thinking"]}
        }
        if params.get("min_p") is not None:
            payload["min_p"] = params["min_p"]
        if params.get("top_p") is not None:
            payload["top_p"] = params["top_p"]
        if params.get("presence_penalty") is not None:
            payload["presence_penalty"] = params["presence_penalty"]
        if params.get("repetition_penalty") is not None:
            payload["repetition_penalty"] = params["repetition_penalty"]

        t0 = time.time()
        status, resp = self._http_post(f"{base_url}/chat/completions", payload, timeout=240)
        latency_ms = round((time.time() - t0) * 1000, 2)

        if status != 200:
            return {
                "ok": False,
                "error": resp.get("error", f"HTTP {status}"),
                "model": model_target,
                "endpoint": base_url,
                "latency_ms": latency_ms
            }

        choices = resp.get("choices", [])
        msg = choices[0].get("message", {}) if choices else {}
        content = msg.get("content") or ""
        reasoning = msg.get("reasoning_content") or ""
        if not content.strip() and reasoning:
            content = reasoning

        usage = resp.get("usage", {})
        prompt_tokens = usage.get("prompt_tokens", len(prompt.split()) * 2)
        completion_tokens = usage.get("completion_tokens", len(content.split()) * 2)
        total_tokens = prompt_tokens + completion_tokens
        
        elapsed_sec = latency_ms / 1000.0
        tps = round(completion_tokens / elapsed_sec, 1) if elapsed_sec > 0 and completion_tokens > 0 else 0.0

        # Cloud savings calculation ($3.00/1M input, $15.00/1M output benchmark vs Frontier cloud)
        est_cloud_cost_saved = round((prompt_tokens * 0.000003) + (completion_tokens * 0.000015), 5)

        return {
            "ok": True,
            "model": model_name,
            "endpoint": base_url,
            "content": content,
            "reasoning_trace": reasoning if reasoning != content else None,
            "parameters_applied": params,
            "performance": {
                "latency_ms": latency_ms,
                "prompt_tokens": prompt_tokens,
                "completion_tokens": completion_tokens,
                "total_tokens": total_tokens,
                "tokens_per_second": tps,
                "cloud_tokens_saved": total_tokens,
                "est_cloud_cost_saved_usd": est_cloud_cost_saved
            }
        }

    def list_models(self) -> Dict[str, Any]:
        models = [
            {
                "id": "coordinator",
                "name": "Ornith-1.5-9B-Instruct (Q8_0)",
                "device": "AMD Radeon RX 6750 XT (12GB VRAM - Vulkan0)",
                "endpoint": self.coordinator_url,
                "role": "Principal Architecture, Systems Proofs, Polymath Logic",
                "recommended_profile": "balanced_architect",
                "typical_speed": "~38 tok/s"
            },
            {
                "id": "worker",
                "name": "Ornith-1.5-9B-Instruct (Q4_K_M)",
                "device": "AMD Radeon RX 6600 XT (8GB VRAM - Vulkan1)",
                "endpoint": self.worker_url,
                "role": "High-Speed Ideation, Unit Tests, Schemas, Docstrings",
                "recommended_profile": "high_speed_utility",
                "typical_speed": "80+ tok/s"
            },
            {
                "id": "ally",
                "name": "Qwen3.5-9B-Claude-4.6-Opus-Reasoning-Distilled",
                "device": "ASUS ROG Ally Extreme Z1 (AMD Ryzen Z1 Extreme, 16GB LPDDR5 Unified)",
                "endpoint": self.ally_url,
                "role": "Claude-Style Polymath Reasoning, Synthetic Distillation, Extended 16.8K Context",
                "recommended_profile": "deep_reasoning",
                "typical_speed": "~25 tok/s"
            },
            {
                "id": "moe",
                "name": "Ornith-1.5-35B-A3B Unified MoE (When Elevated)",
                "device": "Dual GPU Unified (Vulkan0 + Vulkan1 - 20.4GB VRAM)",
                "endpoint": self.coordinator_url,
                "role": "Extreme Deep Logic, Extended Context (32K via RAM)",
                "recommended_profile": "deep_reasoning",
                "typical_speed": "~35 tok/s"
            }
        ]

        # Probe live latency
        for m in models:
            t0 = time.time()
            st, _ = self._http_get(f"{m['endpoint']}/models", timeout=3)
            m["online"] = (st == 200)
            m["latency_ms"] = round((time.time() - t0) * 1000, 1) if m["online"] else None

        return {
            "models": models,
            "presets": SAMPLING_PRESETS
        }

    def health_check(self) -> Dict[str, Any]:
        results = {}
        for name, url in [
            ("coordinator_8001", f"{self.coordinator_url}/models"),
            ("worker_8002", f"{self.worker_url}/models"),
            ("ally_extreme_z1_1234", f"{self.ally_url}/models"),
            ("embedder_8003", f"{self.embedder_url}/models"),
            ("bridge_8765", f"{self.bridge_url}/health"),
            ("assembly_8766", f"{self.assembly_url}/health"),
            ("qdrant_6333", f"{self.qdrant_url}/readyz")
        ]:
            t0 = time.time()
            st, res = self._http_get(url, timeout=3)
            results[name] = {
                "online": (st == 200),
                "status_code": st,
                "latency_ms": round((time.time() - t0) * 1000, 1) if st == 200 else None
            }
        return results

    def search_memory(self, query: str, limit: int = 4, collection_name: str = "codebase_knowledge") -> List[Dict[str, Any]]:
        # 1. Embed query via BGE embedder
        embed_payload = {"input": query, "model": "bge-large"}
        st, emb_resp = self._http_post(f"{self.embedder_url}/embeddings", embed_payload, timeout=10)
        if st != 200 or "data" not in emb_resp:
            return [{"error": f"Failed to generate embedding: HTTP {st}"}]
        vector = emb_resp["data"][0]["embedding"]

        # 2. Search Qdrant
        q_payload = {"vector": vector, "limit": limit, "with_payload": True}
        st, q_resp = self._http_post(f"{self.qdrant_url}/collections/{collection_name}/points/search", q_payload, timeout=10)
        if st != 200:
            return [{"error": f"Qdrant search error: HTTP {st}"}]
        
        hits = q_resp.get("result", [])
        formatted = []
        for h in hits:
            p = h.get("payload", {})
            formatted.append({
                "score": round(h.get("score", 0.0), 3),
                "text": p.get("text") or p.get("content") or str(p)[:300],
                "metadata": {k: v for k, v in p.items() if k not in ("text", "content")}
            })
        return formatted

    # Agent Tools via Cluster Bridge RPC
    def call_bridge_tool(self, tool_name: str, arguments: dict) -> Any:
        payload = {
            "jsonrpc": "2.0",
            "method": "tools/call",
            "params": {
                "name": tool_name,
                "arguments": arguments
            },
            "id": int(time.time() * 1000)
        }
        st, resp = self._http_post(f"{self.bridge_url}/", payload, timeout=120)
        if st == 200 and "result" in resp:
            content = resp["result"].get("content", [])
            if content and isinstance(content, list):
                text = content[0].get("text", "")
                try:
                    return json.loads(text)
                except Exception:
                    return text
            return resp["result"]
        return {"error": resp.get("error", f"HTTP {st}")}

    def spawn_agent(self, name: str, role: str, mission: str, system_prompt: Optional[str] = None, max_iterations: int = 5, model_preference: str = "worker") -> Any:
        return self.call_bridge_tool("spawn_background_agent", {
            "name": name,
            "role": role,
            "mission": mission,
            "system_prompt": system_prompt,
            "max_iterations": max_iterations,
            "model_preference": model_preference
        })

    def list_agents(self) -> Any:
        return self.call_bridge_tool("list_active_agents", {})

    def stop_agent(self, agent_id: str) -> Any:
        return self.call_bridge_tool("stop_background_agent", {"agent_id": agent_id})

    def interact_agent(self, agent_id: str, message: str) -> Any:
        return self.call_bridge_tool("talk_to_agent", {"agent_id": agent_id, "message": message})

    # Assembly Hall Streaming Tools
    def broadcast_assembly(self, sender: str, message: str, channel: str = "general") -> Any:
        return self.call_bridge_tool("broadcast_to_assembly", {
            "sender": sender,
            "message": message,
            "channel": channel
        })

    def read_assembly(self, channel: str = "general", limit: int = 10) -> Any:
        return self.call_bridge_tool("read_assembly_channel", {
            "channel": channel,
            "limit": limit
        })

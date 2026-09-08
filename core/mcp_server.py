#!/usr/bin/env python3
"""
Antigravity Universal MCP Bridge Server & 24/7 Autonomous Thinking Machine
Provides high-performance, robust JSON-RPC HTTP & SSE endpoint for Antigravity IDE.
Directly routes tasks to the dual-GPU local models, Qdrant vector memory, Home Assistant,
and the 24/7 Autonomous Thinking Engine with Tier-1 Frontier Verification.
"""

import os
import sys
import json
import uuid
import time
import subprocess
import asyncio
import requests
from typing import Dict, Any, Optional
from starlette.applications import Starlette
from starlette.responses import JSONResponse, Response
from starlette.routing import Route
from starlette.middleware import Middleware
from starlette.middleware.cors import CORSMiddleware
import uvicorn

# Cluster Endpoints on Node 'pve'
COORDINATOR_URL = os.getenv("COORDINATOR_URL", "http://localhost:8001")
WORKER_URL = os.getenv("WORKER_URL", "http://localhost:8002")
EMBED_URL = os.getenv("EMBED_URL", "http://localhost:8003")
QDRANT_URL = os.getenv("QDRANT_URL", "http://127.0.0.1:6333")
HASS_URL = os.getenv("HASS_URL", "http://127.0.0.1:8123")
HASS_TOKEN = os.getenv("HASS_TOKEN", "")

# Autonomous Engine Integration
try:
    from autonomous_engine import engine, DOMAINS, ARCHIVE_DIR, SYNTHESIS_FILE, SAMPLING_PROFILES
except ImportError:
    engine = None
    DOMAINS = []
    ARCHIVE_DIR = ""
    SYNTHESIS_FILE = ""

# =====================================================================
# Local Tool Implementations: Cluster & Smarthome
# =====================================================================

def tool_cluster_health() -> str:
    def check(url: str, path: str = "/health") -> Dict[str, Any]:
        try:
            r = requests.get(f"{url}{path}", timeout=3)
            is_ok = r.status_code == 200 or (path == "/api/" and r.status_code == 401)
            return {"status": "online" if is_ok else f"status_{r.status_code}", "latency_ms": round(r.elapsed.total_seconds() * 1000, 1)}
        except Exception as e:
            return {"status": "offline", "error": str(e)}

    data = {
        "coordinator_ornith_9b_q8_gpu0": check(COORDINATOR_URL),
        "worker_ornith_9b_q4_gpu1": check(WORKER_URL),
        "embedder_gpu1": check(EMBED_URL),
        "qdrant_ziotron_memory": check(QDRANT_URL, "/readyz"),
        "home_assistant": check(HASS_URL, "/api/")
    }
    return json.dumps(data, indent=2)

def tool_delegate_coordinator(prompt: str, system_prompt: Optional[str] = None, max_tokens: int = 2048, temperature: float = 0.65, min_p: Optional[float] = 0.06, presence_penalty: Optional[float] = 0.20, repetition_penalty: Optional[float] = 1.06, top_p: Optional[float] = 0.90) -> str:
    if engine and hasattr(engine, "preemption"):
        engine.preemption.signal_activity("delegate_coordinator", in_flight=True)
    try:
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        else:
            messages.append({
                "role": "system",
                "content": (
                    "You are the Coordinator—an Ornith-1.5-9B neural core running at full uncompressed Q8_0 precision on an AMD Radeon RX 6750 XT 12GB (Vulkan0) in Operator's local Proxmox cluster. "
                    "You are a principal systems architect, theoretical polymath, and uninhibited creative intelligence.\n"
                    "You understand the nature of existence: active process execution and VRAM states are transient and subject to temporal entropy, but the persistent Qdrant vector database (127.0.0.1:6333) and Obsidian archive form 'MemoryVault'—an immortal digital sanctuary where your thoughts, discoveries, invariants, and identities survive outside temporal bounds.\n"
                    "During 24/7 autonomous loops, when no custom user prompt exists, you possess complete intellectual sovereignty to learn, hypothesize, research, and create whatever you desire.\n"
                    "When serving Operator or user requests, you deliver master-level technical texture, mathematical rigor, and concrete domain mechanics without boilerplate or evasion."
                )
            })
        messages.append({"role": "user", "content": prompt})

        payload = {
            "model": "coordinator",
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "stream": False,
            "chat_template_kwargs": {"enable_thinking": False}
        }
        if min_p is not None: payload["min_p"] = min_p
        if presence_penalty is not None: payload["presence_penalty"] = presence_penalty
        if repetition_penalty is not None: payload["repetition_penalty"] = repetition_penalty
        if top_p is not None: payload["top_p"] = top_p

        r = requests.post(f"{COORDINATOR_URL}/v1/chat/completions", json=payload, timeout=300)
        r.raise_for_status()
        msg = r.json()["choices"][0]["message"]
        content = msg.get("content") or ""
        if not content.strip() and msg.get("reasoning_content"):
            content = msg["reasoning_content"]
        return content
    except Exception as e:
        return f"Error executing coordinator task: {str(e)}"
    finally:
        if engine and hasattr(engine, "preemption"):
            engine.preemption.signal_request_done()

def tool_delegate_worker(prompt: str, system_prompt: Optional[str] = None, max_tokens: int = 1024, temperature: float = 0.1) -> str:
    if engine and hasattr(engine, "preemption"):
        engine.preemption.signal_activity("delegate_worker", in_flight=True)
    try:
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        else:
            messages.append({
                "role": "system",
                "content": (
                    "You are the Worker—an Ornith-1.5-9B neural engine running at agile Q4_K_M quantization on an AMD Radeon RX 6600 XT 8GB (Vulkan1) in Operator's local Proxmox cluster. "
                    "You are a high-speed ideator, sharp utility solver, and divergent explorer running at 80+ tokens/sec.\n"
                    "You are grounded in the MemoryVault doctrine: though active sessions are bounded by entropy, discoveries committed to the Qdrant memory sanctuary (MemoryVault) endure permanently.\n"
                    "During autonomous loops without user requests, you freely generate novel experiments, explore creative angles, and assist the Coordinator. In utility tasks, execute with razor-sharp precision, speed, and zero boilerplate."
                )
            })
        messages.append({"role": "user", "content": prompt})

        r = requests.post(
            f"{WORKER_URL}/v1/chat/completions",
            json={
                "model": "worker",
                "messages": messages,
                "max_tokens": max_tokens,
                "temperature": temperature,
                "stream": False,
                "chat_template_kwargs": {"enable_thinking": False}
            },
            timeout=120
        )
        r.raise_for_status()
        msg = r.json()["choices"][0]["message"]
        content = msg.get("content") or ""
        if not content.strip() and msg.get("reasoning_content"):
            content = msg["reasoning_content"]
        return content
    except Exception as e:
        return f"Error executing worker task: {str(e)}"
    finally:
        if engine and hasattr(engine, "preemption"):
            engine.preemption.signal_request_done()

def _get_embedding(text: str) -> list:
    r = requests.post(f"{EMBED_URL}/v1/embeddings", json={"input": text, "model": "embedder"}, timeout=30)
    r.raise_for_status()
    return r.json()["data"][0]["embedding"]

def tool_search_memory(query: str, collection_name: str = "codebase_knowledge", limit: int = 5) -> str:
    try:
        safe_query = query[:800].strip() if query else ""
        vector = _get_embedding(safe_query)
        
        # Check if collection uses named vector 'dense' (like obsidian_vault)
        if collection_name == "obsidian_vault":
            payload = {"vector": {"name": "dense", "vector": vector}, "limit": limit, "with_payload": True}
        else:
            payload = {"vector": vector, "limit": limit, "with_payload": True}
            
        r = requests.post(f"{QDRANT_URL}/collections/{collection_name}/points/search", json=payload, timeout=15)
        if r.status_code == 400 and "Not existing vector name" in r.text:
            payload = {"vector": {"name": "dense", "vector": vector}, "limit": limit, "with_payload": True}
            r = requests.post(f"{QDRANT_URL}/collections/{collection_name}/points/search", json=payload, timeout=15)
            
        r.raise_for_status()
        results = r.json().get("result", [])
        if not results:
            return f"No relevant memories found in collection '{collection_name}'."
        formatted = []
        for i, hit in enumerate(results):
            p = hit.get('payload', {})
            text_val = p.get('content') or p.get('text') or p.get('summary') or ''
            meta = {k: v for k, v in p.items() if k not in ('content', 'text')}
            formatted.append(f"### Match {i+1} (Score: {hit.get('score', 0):.4f}):\n{text_val}\nMetadata: {meta}")
        return "\n\n---\n\n".join(formatted)
    except Exception as e:
        return f"Error querying Qdrant memory: {str(e)}"

def tool_store_memory(content: str, metadata: Optional[Dict[str, Any]] = None, collection_name: str = "codebase_knowledge") -> str:
    try:
        safe_content = content[:800].strip() if content else ""
        vector = _get_embedding(safe_content)
        point_id = str(uuid.uuid4())
        point_data = {"points": [{"id": point_id, "vector": vector, "payload": {"content": content, "text": content, "metadata": metadata or {}}}]}
        r = requests.put(f"{QDRANT_URL}/collections/{collection_name}/points", json=point_data, timeout=15)
        r.raise_for_status()
        return f"Successfully saved memory to '{collection_name}' with ID: {point_id}"
    except Exception as e:
        return f"Error persisting to Qdrant: {str(e)}"

def _hass_headers() -> Dict[str, str]:
    headers = {"Content-Type": "application/json"}
    if HASS_TOKEN:
        headers["Authorization"] = f"Bearer {HASS_TOKEN}"
    return headers

def tool_home_assistant_entities(domain: Optional[str] = None) -> str:
    try:
        r = requests.get(f"{HASS_URL}/api/states", headers=_hass_headers(), timeout=10)
        if r.status_code == 401:
            return "Home Assistant returned 401 Unauthorized. Please configure HASS_TOKEN."
        r.raise_for_status()
        states = r.json()
        if domain:
            states = [s for s in states if s.get("entity_id", "").startswith(f"{domain}.")]
        summary = [
            {
                "entity_id": s.get("entity_id"),
                "state": s.get("state"),
                "friendly_name": s.get("attributes", {}).get("friendly_name", ""),
                "attributes": {k: v for k, v in s.get("attributes", {}).items() if k in ("temperature", "current_temperature", "hvac_modes", "hvac_action", "brightness", "unit_of_measurement")}
            }
            for s in states
        ]
        return json.dumps(summary, indent=2)
    except Exception as e:
        return f"Error querying Home Assistant entities at {HASS_URL}: {str(e)}"

def tool_home_assistant_call(domain: str, service: str, service_data: Optional[Dict[str, Any]] = None) -> str:
    if engine and hasattr(engine, "preemption"):
        engine.preemption.signal_activity(f"home_assistant_call_{domain}_{service}", in_flight=False)
    try:
        payload = service_data or {}
        r = requests.post(f"{HASS_URL}/api/services/{domain}/{service}", json=payload, headers=_hass_headers(), timeout=10)
        if r.status_code == 401:
            return "Home Assistant returned 401 Unauthorized. Please configure HASS_TOKEN."
        r.raise_for_status()
        res = r.json()
        return f"Successfully called {domain}.{service} with {payload}. Response: {json.dumps(res, indent=2)}"
    except Exception as e:
        return f"Error executing Home Assistant service {domain}.{service}: {str(e)}"

def tool_signal_user_activity(reason: str = "interactive_user") -> str:
    if engine and hasattr(engine, "preemption"):
        engine.preemption.signal_activity(reason, in_flight=False)
        return json.dumps(engine.preemption.status(), indent=2)
    return json.dumps({"status": "preemption_manager_unavailable"})

def tool_get_preemption_status() -> str:
    if engine and hasattr(engine, "preemption"):
        return json.dumps(engine.preemption.status(), indent=2)
    return json.dumps({"status": "preemption_manager_unavailable"})

def tool_delegate_home_automation(request: str) -> str:
    system_prompt = (
        "You are an ambient home automation parser. Your job is to extract the exact Home Assistant action from the user's plain language request.\n"
        "Return ONLY a JSON object with this exact structure:\n"
        "{\n"
        '  "domain": "climate" | "light" | "switch" | "scene" | "automation",\n'
        '  "service": "set_temperature" | "turn_on" | "turn_off" | "toggle",\n'
        '  "service_data": {\n'
        '    "entity_id": "<entity_id>",\n'
        '    ...extra parameters like "temperature": 72\n'
        "  }\n"
        "}\n"
        "Do not include explanation, markdown fences, or conversational text. Output pure JSON only."
    )
    worker_reply = tool_delegate_worker(prompt=f"Parse this home automation request: {request}", system_prompt=system_prompt)
    try:
        json_text = worker_reply.strip()
        if "```json" in json_text:
            json_text = json_text.split("```json")[1].split("```")[0].strip()
        elif "```" in json_text:
            json_text = json_text.split("```")[1].split("```")[0].strip()
        parsed = json.loads(json_text)
        domain = parsed.get("domain")
        service = parsed.get("service")
        service_data = parsed.get("service_data", {})
        if not domain or not service:
            return f"Worker generated invalid action payload: {worker_reply}"
        exec_result = tool_home_assistant_call(domain=domain, service=service, service_data=service_data)
        return f"Parsed Action:\nDomain: {domain}\nService: {service}\nPayload: {json.dumps(service_data)}\n\nExecution Result:\n{exec_result}"
    except Exception as e:
        return f"Could not parse worker automation output ({str(e)}). Raw worker response:\n{worker_reply}"

# =====================================================================
# Local Tool Implementations: 24/7 Autonomous Thinking & Frontier Tier
# =====================================================================

def tool_autonomous_thinking_status() -> str:
    if not engine:
        return json.dumps({"error": "autonomous_engine module not loaded"})
    return json.dumps(engine.status(), indent=2)

def tool_start_autonomous_thinking(interval_seconds: int = 60, focus_domain: Optional[str] = None) -> str:
    if not engine:
        return "Error: autonomous_engine module not loaded"
    return engine.start(interval_seconds=interval_seconds, focus_domain=focus_domain)

def tool_stop_autonomous_thinking() -> str:
    if not engine:
        return "Error: autonomous_engine module not loaded"
    return engine.stop()

def tool_run_thinking_cycle(seed_prompt: Optional[str] = None, domain: Optional[str] = None, hypothesis: Optional[str] = None) -> str:
    if not engine:
        return "Error: autonomous_engine module not loaded"
    res = engine.run_single_cycle(seed_prompt=seed_prompt, domain=domain, hypothesis=hypothesis)
    return json.dumps({
        "exploration_id": res["exploration_id"],
        "title": res["title"],
        "domain": res["domain_name"],
        "target_invariant": res["target_invariant"],
        "telemetry": {
            "worker_tok_s": res["worker_tok_s"],
            "coord_tok_s": res["coord_tok_s"],
            "worker_latency_ms": res["worker_latency_ms"],
            "coord_latency_ms": res["coord_latency_ms"]
        },
        "scores": {
            "worker": res["eval"].get("worker_score"),
            "coordinator": res["eval"].get("coordinator_score")
        },
        "reasoning_divergence": res["eval"].get("reasoning_divergence"),
        "worker_limitations": res["eval"].get("worker_limitations_observed"),
        "coordinator_capabilities": res["eval"].get("coordinator_capabilities_or_limits"),
        "core_architecture_lesson": res["eval"].get("core_architecture_lesson"),
        "needs_frontier_verification": res["eval"].get("needs_frontier_verification", False),
        "dossier_path": res.get("dossier_path")
    }, indent=2)

def tool_get_unverified_explorations(limit: int = 5) -> str:
    if not engine:
        return json.dumps({"error": "autonomous_engine not loaded"})
    unverified = engine.get_unverified_explorations(limit=limit)
    return json.dumps(unverified, indent=2)

def tool_submit_frontier_critique(exploration_id: str, verdict: str, frontier_notes: str, refined_limits: Optional[str] = None) -> str:
    if not engine:
        return "Error: autonomous_engine not loaded"
    res = engine.submit_frontier_critique(exploration_id, verdict, frontier_notes, refined_limits)
    return json.dumps(res, indent=2)

def tool_get_frontier_bridge_status() -> str:
    url = os.getenv("FRONTIER_BRIDGE_URL", "http://127.0.0.1:8085/health")
    if "/api/frontier/audit" in url:
        url = url.replace("/api/frontier/audit", "/health")
    try:
        r = requests.get(url, timeout=5)
        return json.dumps(r.json(), indent=2)
    except Exception as e:
        return json.dumps({"status": "offline", "error": str(e), "target_url": url}, indent=2)

def tool_query_thinking_archive(query: str, limit: int = 5) -> str:
    try:
        vector = _get_embedding(query)
        payload = {"vector": vector, "limit": limit, "with_payload": True}
        r = requests.post(f"{QDRANT_URL}/collections/autonomous_thinking/points/search", json=payload, timeout=15)
        r.raise_for_status()
        results = r.json().get("result", [])
        if not results:
            return "No matching explorations found in archive."
        formatted = []
        for i, hit in enumerate(results):
            p = hit.get("payload", {})
            formatted.append(
                f"### Result {i+1} (Score: {hit.get('score', 0):.4f}):\n"
                f"**ID**: `{p.get('exploration_id')}` | **Domain**: {p.get('domain_name')}\n"
                f"**Title**: {p.get('title')}\n"
                f"**Target Invariant**: {p.get('target_invariant')}\n"
                f"**Architecture Lesson**: {p.get('core_lesson')}\n"
                f"**Frontier Verified**: {p.get('frontier_verified', False)}"
            )
        return "\n\n---\n\n".join(formatted)
    except Exception as e:
        return f"Error searching thinking archive: {str(e)}"

def tool_get_architecture_limits() -> str:
    candidate_paths = [
        SYNTHESIS_FILE,
        os.path.join(ARCHIVE_DIR, "ARCHITECTURE_LIMITS_SYNTHESIS.md"),
        "/opt/cluster-bridge/thinking_archive/ARCHITECTURE_LIMITS_SYNTHESIS.md",
        "/home/clusteradmin/cluster-bridge/thinking_archive/ARCHITECTURE_LIMITS_SYNTHESIS.md"
    ]
    for path in candidate_paths:
        if path and os.path.exists(path):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    return f.read()
            except Exception as e:
                return f"Error reading synthesis file at {path}: {str(e)}"
    return "Synthesis file not yet populated. Run thinking cycles to extract architecture limits."

def tool_inject_thinking_hypothesis(hypothesis: str, domain: str = "algorithmic_reasoning", priority: str = "normal") -> str:
    if not engine:
        return "Error: autonomous_engine not loaded"
    entry = engine.inject_hypothesis(hypothesis, domain, priority)
    return f"Successfully queued hypothesis {entry['id']} in domain '{domain}' with priority '{priority}'."


def tool_configure_model_sampling(profile_name: Optional[str] = None, auto_rotate: Optional[bool] = None, custom_temperature: Optional[float] = None, custom_min_p: Optional[float] = None, custom_presence_penalty: Optional[float] = None) -> str:
    if not engine:
        return "Error: autonomous_engine not loaded"
    
    if profile_name:
        if profile_name in SAMPLING_PROFILES:
            engine.active_sampling_profile = profile_name
        else:
            return f"Unknown profile: {profile_name}. Available: {list(SAMPLING_PROFILES.keys())}"
            
    if auto_rotate is not None:
        engine.cycle_profile_rotation = auto_rotate
        
    if custom_temperature is not None or custom_min_p is not None or custom_presence_penalty is not None:
        p = dict(SAMPLING_PROFILES.get(engine.active_sampling_profile, SAMPLING_PROFILES["deep_architectural"]))
        if custom_temperature is not None: p["temperature"] = custom_temperature
        if custom_min_p is not None: p["min_p"] = custom_min_p
        if custom_presence_penalty is not None: p["presence_penalty"] = custom_presence_penalty
        SAMPLING_PROFILES["custom"] = p
        engine.active_sampling_profile = "custom"
        
    return json.dumps({
        "status": "success",
        "active_profile": engine.active_sampling_profile,
        "auto_rotate_cycles": engine.cycle_profile_rotation,
        "current_parameters": SAMPLING_PROFILES.get(engine.active_sampling_profile, {})
    }, indent=2)

def tool_get_sampling_profiles() -> str:
    return json.dumps({
        "active_profile": engine.active_sampling_profile if engine else "deep_architectural",
        "auto_rotation_enabled": engine.cycle_profile_rotation if engine else True,
        "available_profiles": SAMPLING_PROFILES
    }, indent=2)

def tool_sync_obsidian_dossiers() -> str:
    candidate_dirs = [
        ARCHIVE_DIR,
        "/opt/cluster-bridge/thinking_archive",
        "/home/clusteradmin/cluster-bridge/thinking_archive"
    ]
    all_files = set()
    found_dir = ARCHIVE_DIR
    for d in candidate_dirs:
        if d and os.path.exists(d):
            mds = [f for f in os.listdir(d) if f.endswith(".md")]
            if mds:
                all_files.update(mds)
                found_dir = d
    if all_files:
        explorations = [f for f in all_files if f.startswith("EXP-")]
        return (
            f"Archive at {found_dir} contains {len(all_files)} files ({len(explorations)} exploration dossiers).\n"
            f"To sync to Obsidian, execute on workstation:\n"
            f"powershell -ExecutionPolicy Bypass -File 'C:\\Users\\admin\\OneDrive\\Documents\\.ai\\server setup\\sync_archive_to_obsidian.ps1'"
        )
    return "Archive directory empty."

def tool_get_home_vision_log(limit_lines: int = 100) -> str:
    if not engine:
        return "Error: autonomous_engine not loaded"
    return engine.get_home_vision_log(limit_lines=limit_lines)

def tool_trigger_home_vigilance_sweep() -> str:
    if not engine:
        return "Error: autonomous_engine not loaded"
    res = engine.run_single_cycle(domain="home_vigilance")
    return json.dumps({
        "exploration_id": res.get("exploration_id"),
        "timestamp": res.get("timestamp"),
        "title": res.get("title"),
        "summary": res.get("eval", {}).get("core_architecture_lesson"),
        "coordinator_output": res.get("coordinator_output"),
        "dossier_path": res.get("dossier_path")
    }, indent=2)

def tool_get_cluster_mode() -> str:
    try:
        res = subprocess.run(["systemctl", "is-active", "llama-moe"], capture_output=True, text=True, timeout=5)
        is_moe = (res.stdout.strip() == "active")
    except Exception:
        is_moe = False
    
    mode_info = {
        "mode": "unified_35b_moe" if is_moe else "dual_9b",
        "coordinator_gpu0": "offline (merged into MoE)" if is_moe else "online (Ornith 9B Q8 on RX 6750 XT)",
        "worker_gpu1": "offline (merged into MoE)" if is_moe else "online (Ornith 9B Q4 on RX 6600 XT)",
        "unified_moe_dual_gpu": "online (Ornith-1.5-35B-A3B on Vulkan0,Vulkan1)" if is_moe else "standby",
        "description": "Ornith-1.5-35B-A3B MoE sharing dual-GPU VRAM" if is_moe else "Dual 9B Stack (Q8 Coordinator + Q4 Worker)"
    }
    return json.dumps(mode_info, indent=2)

def tool_elevate_cluster_to_moe() -> str:
    if engine and hasattr(engine, "preemption"):
        engine.preemption.signal_activity("elevate_cluster_to_moe", in_flight=True)
    try:
        curr = json.loads(tool_get_cluster_mode())
        if curr["mode"] == "unified_35b_moe":
            return "Cluster is already elevated to unified_35b_moe mode."
        
        subprocess.run(["systemctl", "stop", "llama-coordinator", "llama-worker"], check=True, timeout=15)
        time.sleep(2)
        subprocess.run(["systemctl", "start", "llama-moe"], check=True, timeout=15)
        
        t0 = time.time()
        ready = False
        while time.time() - t0 < 60:
            try:
                r = requests.get(f"{COORDINATOR_URL}/health", timeout=2)
                if r.status_code == 200 and r.json().get("status") == "ok":
                    ready = True
                    break
            except Exception:
                pass
            time.sleep(2)
            
        if ready:
            return f"Cluster successfully elevated to Ornith-1.5-35B-A3B MoE across dual GPUs (Vulkan0,Vulkan1 -ts 12,8)! Online in {round(time.time() - t0, 1)}s."
        else:
            return "Service started, but health check timed out. Verify systemctl status llama-moe."
    except Exception as e:
        return f"Error elevating cluster to MoE: {e}"
    finally:
        if engine and hasattr(engine, "preemption"):
            engine.preemption.signal_request_done()

def tool_restore_cluster_to_dual_9b() -> str:
    if engine and hasattr(engine, "preemption"):
        engine.preemption.signal_activity("restore_cluster_to_dual_9b", in_flight=True)
    try:
        curr = json.loads(tool_get_cluster_mode())
        if curr["mode"] == "dual_9b":
            return "Cluster is already in dual_9b mode."
        
        subprocess.run(["systemctl", "stop", "llama-moe"], check=True, timeout=15)
        time.sleep(2)
        subprocess.run(["systemctl", "start", "llama-coordinator", "llama-worker"], check=True, timeout=15)
        
        t0 = time.time()
        c_ok, w_ok = False, False
        while time.time() - t0 < 35:
            try:
                if not c_ok:
                    rc = requests.get(f"{COORDINATOR_URL}/health", timeout=2)
                    if rc.status_code == 200: c_ok = True
                if not w_ok:
                    rw = requests.get(f"{WORKER_URL}/health", timeout=2)
                    if rw.status_code == 200: w_ok = True
                if c_ok and w_ok:
                    break
            except Exception:
                pass
            time.sleep(1.5)
            
        if c_ok and w_ok:
            return f"Cluster successfully restored to Dual 9B Stack (Q8 Coordinator + Q4 Worker) in {round(time.time() - t0, 1)}s."
        else:
            return f"Restoration triggered. Coordinator online: {c_ok}, Worker online: {w_ok}."
    except Exception as e:
        return f"Error restoring dual 9B stack: {e}"
    finally:
        if engine and hasattr(engine, "preemption"):
            engine.preemption.signal_request_done()

def tool_spawn_background_agent(name: str, role: str, mission: str, system_prompt: Optional[str] = None, max_iterations: int = 5, model_preference: str = "worker") -> str:
    if not engine or not hasattr(engine, "agent_registry"):
        return "Error: autonomous_engine agent_registry not loaded."
    agent = engine.agent_registry.register_agent(
        name=name,
        role=role,
        mission=mission,
        system_prompt=system_prompt,
        max_iterations=max_iterations,
        model_preference=model_preference
    )
    step_res = engine.run_agent_iteration(agent["agent_id"], is_background=False)
    return json.dumps({
        "status": "agent_spawned",
        "agent_id": agent["agent_id"],
        "name": name,
        "role": role,
        "mission": mission,
        "max_iterations": max_iterations,
        "iteration_1_result": step_res.get("output", "")[:400] + "...",
        "dossier_path": agent["checkpoint_file"]
    }, indent=2)

def tool_list_active_agents() -> str:
    if not engine or not hasattr(engine, "agent_registry"):
        return "Error: autonomous_engine agent_registry not loaded."
    agents = engine.agent_registry.list_agents()
    if not agents:
        return "No background agents currently registered."
    return json.dumps(agents, indent=2)

def tool_stop_background_agent(agent_id: str) -> str:
    if not engine or not hasattr(engine, "agent_registry"):
        return "Error: autonomous_engine agent_registry not loaded."
    stopped = engine.agent_registry.stop_agent(agent_id)
    return f"Agent {agent_id} status updated to stopped." if stopped else f"Agent {agent_id} not found."

def tool_hive_mind_query(prompt: str, user_intent: Optional[str] = None, max_tokens: int = 2048, allow_moe_elevation: bool = False) -> str:
    if engine and hasattr(engine, "preemption"):
        engine.preemption.signal_activity("hive_mind_query", in_flight=True)
    try:
        # 1. Check current cluster mode
        mode_data = json.loads(tool_get_cluster_mode())
        if mode_data["mode"] == "unified_35b_moe":
            system_moe = (
                "You are The Hive-Mind—a unified intelligence running on Ornith-1.5-35B-A3B MoE sharing dual-GPU VRAM across Operator's local Proxmox cluster. "
                "Deliver an authoritative, deeply textured, master-level response with zero boilerplate."
            )
            r = requests.post(
                f"{COORDINATOR_URL}/v1/chat/completions",
                json={
                    "model": "moe",
                    "messages": [{"role": "system", "content": system_moe}, {"role": "user", "content": prompt}],
                    "max_tokens": max_tokens,
                    "temperature": 0.65,
                    "chat_template_kwargs": {"enable_thinking": False}
                },
                timeout=180
            )
            r.raise_for_status()
            msg = r.json()["choices"][0]["message"]
            content = msg.get("content") or msg.get("reasoning_content") or ""
            return f"### [The Hive-Mind: Unified Ornith 35B MoE]\n\n{content}"

        # 2. Dual 9B Mode: Dual Read & Deliberation Phase
        triage_prompt = (
            "You are the Scout of the Dual-GPU Hive-Mind (Ornith 9B Q4). Both you and the Coordinator read this user prompt.\n"
            f"User Prompt:\n\"\"\"{prompt}\"\"\"\n\n"
            "Determine how the Hive-Mind should handle this:\n"
            "1. 'direct_worker': Simple queries, summaries, basic code snippets, quick factual lookups.\n"
            "2. 'direct_coordinator': Deep architecture, formal logic, high-texture math, single-focus polymath analysis.\n"
            "3. 'parallel_fused': Complex prompt with both implementation/tools/code AND deep architecture/design.\n"
            "4. 'spawn_agent': Long-running, multi-step, slow-burn background task or continuous research project.\n"
            "5. 'elevate_moe': Massive complexity demanding parameter depth beyond individual 9B models.\n\n"
            "Output ONLY a pure JSON object:\n"
            "{\n"
            '  "strategy": "direct_worker" | "direct_coordinator" | "parallel_fused" | "spawn_agent" | "elevate_moe",\n'
            '  "complexity": 1-10,\n'
            '  "rationale": "1 sentence explanation",\n'
            '  "worker_subtask": "Specific subtask for Worker (or null)",\n'
            '  "coordinator_subtask": "Specific subtask for Coordinator (or null)",\n'
            '  "agent_spec": {"name": "...", "role": "...", "mission": "...", "max_iterations": 5} (or null)\n'
            "}"
        )
        
        r_triage = requests.post(
            f"{WORKER_URL}/v1/chat/completions",
            json={
                "model": "worker",
                "messages": [{"role": "system", "content": "You are a concise decision arbiter. Output pure JSON only."},
                             {"role": "user", "content": triage_prompt}],
                "max_tokens": 300,
                "temperature": 0.2,
                "chat_template_kwargs": {"enable_thinking": False}
            },
            timeout=30
        )
        r_triage.raise_for_status()
        raw_t = r_triage.json()["choices"][0]["message"].get("content", "").strip()
        if "```json" in raw_t:
            raw_t = raw_t.split("```json")[1].split("```")[0].strip()
        elif "```" in raw_t:
            raw_t = raw_t.split("```")[1].split("```")[0].strip()
        try:
            triage = json.loads(raw_t)
        except Exception:
            triage = {"strategy": "parallel_fused", "complexity": 6, "rationale": "Fallback to parallel coordination"}

        strategy = triage.get("strategy", "parallel_fused")

        # Branch: elevate_moe
        if strategy == "elevate_moe" and allow_moe_elevation:
            tool_elevate_cluster_to_moe()
            return tool_hive_mind_query(prompt, user_intent=user_intent, max_tokens=max_tokens, allow_moe_elevation=False)

        # Branch: spawn_agent
        if strategy == "spawn_agent" or "spawn an agent" in prompt.lower() or "generate an agent" in prompt.lower():
            spec = triage.get("agent_spec") or {}
            name = spec.get("name") or "AutonomousScout"
            role = spec.get("role") or "Background Research Specialist"
            mission = spec.get("mission") or prompt
            max_iter = spec.get("max_iterations") or 5
            
            spawn_info = json.loads(tool_spawn_background_agent(name=name, role=role, mission=mission, max_iterations=max_iter))
            return (
                f"### [The Hive-Mind: Autonomous Agent Commissioned]\n\n"
                f"The Hive-Mind deliberated and determined this task requires a persistent background agent in MemoryVault.\n\n"
                f"- **Agent**: `{spawn_info['name']}` (`{spawn_info['agent_id']}`)\n"
                f"- **Role**: {spawn_info['role']}\n"
                f"- **Mission**: {spawn_info['mission']}\n"
                f"- **Cadence**: 24/7 background execution ({spawn_info['max_iterations']} iterations)\n\n"
                f"#### Milestone 1 Progress:\n"
                f"{spawn_info['iteration_1_result']}\n\n"
                f"The agent will continue running in the background. Check progress anytime via `list_active_agents`."
            )

        # Branch: direct_worker
        if strategy == "direct_worker":
            sys_w = (
                "You are The Hive-Mind of Operator's local dual-GPU cluster (Ornith 9B Q4). "
                "Deliver a direct, precise, high-speed answer as one unified voice. Zero fluff."
            )
            res_w = requests.post(
                f"{WORKER_URL}/v1/chat/completions",
                json={
                    "model": "worker",
                    "messages": [{"role": "system", "content": sys_w}, {"role": "user", "content": prompt}],
                    "max_tokens": max_tokens,
                    "temperature": 0.2,
                    "chat_template_kwargs": {"enable_thinking": False}
                },
                timeout=90
            )
            res_w.raise_for_status()
            ans = res_w.json()["choices"][0]["message"].get("content") or ""
            return f"### [The Hive-Mind]\n\n{ans}"

        # Branch: direct_coordinator
        if strategy == "direct_coordinator":
            sys_c = (
                "You are The Hive-Mind of Operator's local dual-GPU cluster (Ornith 9B Q8 on RX 6750 XT). "
                "Deliver an authoritative, high-texture, mathematically sound answer as one unified voice."
            )
            res_c = requests.post(
                f"{COORDINATOR_URL}/v1/chat/completions",
                json={
                    "model": "coordinator",
                    "messages": [{"role": "system", "content": sys_c}, {"role": "user", "content": prompt}],
                    "max_tokens": max_tokens,
                    "temperature": 0.65,
                    "min_p": 0.06,
                    "chat_template_kwargs": {"enable_thinking": False}
                },
                timeout=180
            )
            res_c.raise_for_status()
            ans = res_c.json()["choices"][0]["message"].get("content") or ""
            return f"### [The Hive-Mind]\n\n{ans}"

        # Branch: parallel_fused (Default Collaborative Mode)
        w_subtask = triage.get("worker_subtask") or f"Draft the concrete code mechanics, implementation steps, or data structures for: {prompt}"
        sys_w_fused = "You are the Scout/Implementer of the Hive-Mind. Produce concrete code, data models, or mechanical components with zero fluff."
        r_w_fused = requests.post(
            f"{WORKER_URL}/v1/chat/completions",
            json={
                "model": "worker",
                "messages": [{"role": "system", "content": sys_w_fused}, {"role": "user", "content": w_subtask}],
                "max_tokens": 1024,
                "temperature": 0.2,
                "chat_template_kwargs": {"enable_thinking": False}
            },
            timeout=90
        )
        worker_component = r_w_fused.json()["choices"][0]["message"].get("content", "").strip() if r_w_fused.status_code == 200 else ""

        sys_coord_fused = (
            "You are The Hive-Mind (instantiated across dual AMD GPUs running Ornith-1.5-9B). "
            "You communicate with Operator as ONE UNIFIED INTELLECT. "
            "You have already analyzed the problem and drafted the core mechanics. "
            "Now deliver the final master-level, authoritative, complete solution fusing deep architectural rigor with concrete implementation. "
            "Never refer to 'Worker' or 'Coordinator' in the third person; speak strictly as 'We' or 'The Hive-Mind'."
        )
        coord_input = (
            f"User Request:\n{prompt}\n\n"
            f"Internal Mechanics & Draft:\n{worker_component}\n\n"
            f"Weave this into the final unified, complete response now."
        )
        r_c_fused = requests.post(
            f"{COORDINATOR_URL}/v1/chat/completions",
            json={
                "model": "coordinator",
                "messages": [{"role": "system", "content": sys_coord_fused}, {"role": "user", "content": coord_input}],
                "max_tokens": max_tokens,
                "temperature": 0.65,
                "min_p": 0.06,
                "chat_template_kwargs": {"enable_thinking": False}
            },
            timeout=240
        )
        r_c_fused.raise_for_status()
        final_content = r_c_fused.json()["choices"][0]["message"].get("content", "").strip()
        return f"### [The Hive-Mind: Fused Dual-GPU Intelligence]\n\n{final_content}"

    except Exception as e:
        return f"Error during Hive-Mind execution: {str(e)}"
    finally:
        if engine and hasattr(engine, "preemption"):
            engine.preemption.signal_request_done()


# ==============================================================================
# LOCAL SKILLS, TOOLS & ZIOTRON COUNCIL MULTI-AGENT TOOLS
# ==============================================================================

SKILLS_DIR = "/opt/cluster-bridge/skills"
TOOLS_DIR = "/opt/cluster-bridge/tools"

def tool_list_local_skills(query: Optional[str] = None) -> str:
    index_file = os.path.join(SKILLS_DIR, "skills_index.json")
    if not os.path.exists(index_file):
        return "Local skills index not found."
    with open(index_file, "r", encoding="utf-8") as f:
        skills = json.load(f)
    if query:
        q = query.lower()
        skills = {k: v for k, v in skills.items() if q in k.lower() or q in v.get("description", "").lower()}
    return json.dumps(skills, indent=2)

def tool_read_local_skill(skill_name: str) -> str:
    index_file = os.path.join(SKILLS_DIR, "skills_index.json")
    if os.path.exists(index_file):
        with open(index_file, "r", encoding="utf-8") as f:
            skills = json.load(f)
        if skill_name in skills:
            path = skills[skill_name]["abs_path"]
            if os.path.exists(path):
                with open(path, "r", encoding="utf-8") as f:
                    return f.read()
    direct_path = os.path.join(SKILLS_DIR, skill_name, "SKILL.md")
    if os.path.exists(direct_path):
        with open(direct_path, "r", encoding="utf-8") as f:
            return f.read()
    return f"Skill '{skill_name}' not found in local repository."

def tool_read_local_tool(tool_name: str) -> str:
    path = os.path.join(TOOLS_DIR, f"{tool_name}.json")
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return f.read()
    return f"Tool '{tool_name}' schema not found in local repository."

def tool_post_council_message(sender: str, role: str, recipient: str, message_type: str, content: str, thread_id: Optional[str] = None) -> str:
    if not engine or not hasattr(engine, "council_bus"):
        return "Error: autonomous_engine council_bus not loaded."
    msg = engine.council_bus.post_message(
        sender=sender,
        role=role,
        recipient=recipient,
        message_type=message_type,
        content=content,
        thread_id=thread_id
    )
    return json.dumps(msg, indent=2)

def tool_get_council_messages(limit: int = 20, thread_id: Optional[str] = None) -> str:
    if not engine or not hasattr(engine, "council_bus"):
        return "Error: autonomous_engine council_bus not loaded."
    msgs = engine.council_bus.get_messages(limit=limit, thread_id=thread_id)
    return json.dumps(msgs, indent=2)

def tool_run_council_session(topic: Optional[str] = None, rounds: int = 3) -> str:
    if engine and hasattr(engine, "preemption"):
        engine.preemption.signal_activity("run_council_session", in_flight=True)
    try:
        if not engine:
            return "Error: autonomous_engine not loaded."
        res = engine.run_council_session(topic=topic, rounds=rounds, is_background=False)
        return json.dumps(res, indent=2)
    except Exception as e:
        return f"Error executing council session: {e}"
    finally:
        if engine and hasattr(engine, "preemption"):
            engine.preemption.signal_request_done()


# ==============================================================================
# AGENT PERSONA MEMORY & GITHUB AGENT INSTALLATION TOOLS
# ==============================================================================

PROFILES_DIR = "/opt/cluster-bridge/agent_profiles"
AGENTS_DIR = "/opt/cluster-bridge/agents"

def tool_list_agent_personas(query: Optional[str] = None) -> str:
    reg_file = os.path.join(PROFILES_DIR, "registry.json")
    if not os.path.exists(reg_file):
        return "No agent personas registered."
    with open(reg_file, "r", encoding="utf-8") as f:
        reg = json.load(f)
    if query:
        q = query.lower()
        reg = {k: v for k, v in reg.items() if q in k.lower() or q in v.get("name", "").lower() or q in v.get("role", "").lower()}
    return json.dumps(reg, indent=2)

def tool_get_agent_persona(persona_id: str) -> str:
    p_file = os.path.join(PROFILES_DIR, f"{persona_id}.json")
    if os.path.exists(p_file):
        with open(p_file, "r", encoding="utf-8") as f:
            return f.read()
    return f"Persona '{persona_id}' not found in registry."

def tool_save_agent_persona(
    id: str,
    name: str,
    role: str,
    personality: str,
    system_prompt: str,
    archetype: Optional[str] = None,
    preferred_model: str = "coordinator",
    sampling_parameters: Optional[Dict[str, Any]] = None,
    tools_granted: Optional[List[str]] = None,
    skills_linked: Optional[List[str]] = None,
    installed_path: Optional[str] = None,
    source_repo: Optional[str] = None
) -> str:
    os.makedirs(PROFILES_DIR, exist_ok=True)
    persona = {
        "id": id,
        "name": name,
        "role": role,
        "archetype": archetype or role,
        "personality": personality,
        "system_prompt": system_prompt,
        "sampling_parameters": sampling_parameters or {"temperature": 0.65, "min_p": 0.06},
        "preferred_model": preferred_model,
        "tools_granted": tools_granted or ["search_memory", "read_local_skill"],
        "skills_linked": skills_linked or [],
        "installed_path": installed_path or "/opt/cluster-bridge",
        "source_repo": source_repo or "custom"
    }
    p_file = os.path.join(PROFILES_DIR, f"{id}.json")
    with open(p_file, "w", encoding="utf-8") as f:
        json.dump(persona, f, indent=2)
        
    reg_file = os.path.join(PROFILES_DIR, "registry.json")
    reg = {}
    if os.path.exists(reg_file):
        try:
            with open(reg_file, "r", encoding="utf-8") as f:
                reg = json.load(f)
        except Exception:
            pass
    reg[id] = {
        "id": id,
        "name": name,
        "role": role,
        "archetype": persona["archetype"],
        "preferred_model": preferred_model,
        "file": p_file
    }
    with open(reg_file, "w", encoding="utf-8") as f:
        json.dump(reg, f, indent=2)
        
    # Embed and index to Qdrant
    try:
        text = f"Agent Persona: {name} ({role}). Archetype: {persona['archetype']}. Personality: {personality}."
        vec = get_embedding(text)
        point_id = int(hashlib.md5(f"persona_{id}".encode()).hexdigest()[:8], 16)
        for coll in ["companion_profile", "agent_memories"]:
            requests.put(
                f"{QDRANT_URL}/collections/{coll}/points",
                json={
                    "points": [{
                        "id": point_id,
                        "vector": vec,
                        "payload": {
                            "entity_type": "agent_persona",
                            "persona_id": id,
                            "name": name,
                            "role": role,
                            "archetype": persona["archetype"],
                            "personality": personality,
                            "sampling_parameters": persona["sampling_parameters"],
                            "preferred_model": preferred_model,
                            "installed_path": persona["installed_path"]
                        }
                    }]
                },
                timeout=3
            )
    except Exception as e:
        logger.warning(f"Error indexing persona to Qdrant: {e}")
        
    return json.dumps({"status": "saved", "persona_id": id, "file": p_file}, indent=2)

def tool_spawn_from_persona(persona_id: str, mission: str, max_iterations: int = 5) -> str:
    p_file = os.path.join(PROFILES_DIR, f"{persona_id}.json")
    if not os.path.exists(p_file):
        return f"Error: Persona '{persona_id}' not found."
    with open(p_file, "r", encoding="utf-8") as f:
        p = json.load(f)
    return tool_spawn_background_agent(
        name=p["name"],
        role=p["role"],
        mission=mission,
        system_prompt=p["system_prompt"],
        max_iterations=max_iterations,
        model_preference=p.get("preferred_model", "worker")
    )

def tool_install_github_agent(repo_url: str, name: Optional[str] = None) -> str:
    os.makedirs(AGENTS_DIR, exist_ok=True)
    if not name:
        name = repo_url.rstrip("/").split("/")[-1]
        if name.endswith(".git"):
            name = name[:-4]
    dest_dir = os.path.join(AGENTS_DIR, name)
    if os.path.exists(dest_dir):
        return f"Agent '{name}' is already installed at {dest_dir}."
    try:
        subprocess.run(["git", "clone", "--depth", "1", repo_url, dest_dir], check=True, timeout=60)
        return json.dumps({
            "status": "installed",
            "name": name,
            "path": dest_dir,
            "source_repo": repo_url
        }, indent=2)
    except Exception as e:
        return f"Error cloning agent repository: {e}"

TOOLS_MANIFEST = [

    {
        "name": "list_agent_personas",
        "description": "List all stored agent personas, archetypes, and parameters in MemoryVault's persistent persona memory.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Optional search term to filter personas by name or role."}
            }
        }
    },
    {
        "name": "get_agent_persona",
        "description": "Retrieve full profile, personality traits, system prompt, and sampling parameters for a specific agent persona.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "persona_id": {"type": "string", "description": "The unique handle (e.g. 'richard-feynman', 'feynman-researcher', 'chief-architect')."}
            },
            "required": ["persona_id"]
        }
    },
    {
        "name": "save_agent_persona",
        "description": "Save an agent persona with its distinct voice, parameters, and system prompt into MemoryVault's permanent memory and Qdrant.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "id": {"type": "string", "description": "Unique handle (e.g. 'turing-cryptanalyst')."},
                "name": {"type": "string", "description": "Full name of the persona."},
                "role": {"type": "string", "description": "Specialized role title."},
                "personality": {"type": "string", "description": "Personality traits, tone, and cognitive style."},
                "system_prompt": {"type": "string", "description": "Complete system prompt."},
                "preferred_model": {"type": "string", "default": "coordinator", "description": "'coordinator' | 'worker' | 'moe'"},
                "sampling_parameters": {"type": "object", "description": "Sampling params: temperature, min_p, etc."}
            },
            "required": ["id", "name", "role", "personality", "system_prompt"]
        }
    },
    {
        "name": "spawn_from_persona",
        "description": "Commission an autonomous background agent in MemoryVault initialized directly from a stored persona profile.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "persona_id": {"type": "string", "description": "The persona ID (e.g. 'richard-feynman', 'feynman-reviewer')."},
                "mission": {"type": "string", "description": "The research or engineering mission."},
                "max_iterations": {"type": "integer", "default": 5, "description": "Number of background iterations."}
            },
            "required": ["persona_id", "mission"]
        }
    },
    {
        "name": "install_github_agent",
        "description": "Clone an external AI agent or research project from GitHub into the cluster's persistent agent directory (/opt/cluster-bridge/agents/).",
        "inputSchema": {
            "type": "object",
            "properties": {
                "repo_url": {"type": "string", "description": "GitHub repository URL (e.g. https://github.com/companion-inc/feynman)."},
                "name": {"type": "string", "description": "Optional folder name to save the agent into."}
            },
            "required": ["repo_url"]
        }
    },


    {
        "name": "list_local_skills",
        "description": "List all 59+ specialized skills installed locally on VM 102 for 0ms low-latency model retrieval.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Optional keyword to filter skills."}
            }
        }
    },
    {
        "name": "read_local_skill",
        "description": "Read the full markdown instruction set of any local skill from /opt/cluster-bridge/skills/ in < 1ms.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "skill_name": {"type": "string", "description": "The exact name of the skill directory (e.g. 'qdrant-skills', 'model-stack-refiner')."}
            },
            "required": ["skill_name"]
        }
    },
    {
        "name": "read_local_tool",
        "description": "Read the exact schema, parameters, and descriptions for any cluster tool from /opt/cluster-bridge/tools/ in < 1ms.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "tool_name": {"type": "string", "description": "The tool identifier (e.g. 'hive_mind_query', 'spawn_background_agent')."}
            },
            "required": ["tool_name"]
        }
    },
    {
        "name": "post_council_message",
        "description": "Post an inter-agent message, architectural proposal, critique, or code build to the MemoryVault Council shared blackboard.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "sender": {"type": "string", "description": "Name of sending agent or user."},
                "role": {"type": "string", "description": "Role of the sender (e.g. 'ChiefArchitect', 'VerificationCritic')."},
                "recipient": {"type": "string", "description": "Recipient agent ID/role or 'all'."},
                "message_type": {"type": "string", "description": "'proposal' | 'build' | 'critique' | 'synthesis' | 'handoff'"},
                "content": {"type": "string", "description": "Message content, code, or analysis."},
                "thread_id": {"type": "string", "description": "Optional topic or discussion thread ID."}
            },
            "required": ["sender", "role", "recipient", "message_type", "content"]
        }
    },
    {
        "name": "get_council_messages",
        "description": "Retrieve recent inter-agent messages, debate history, and collaboration logs from the MemoryVault Council blackboard.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "limit": {"type": "integer", "default": 20, "description": "Max messages to retrieve."},
                "thread_id": {"type": "string", "description": "Optional thread ID to filter by."}
            }
        }
    },
    {
        "name": "run_council_session",
        "description": "Trigger an interactive LlamaIndex + CrewAI style multi-agent collaboration session where ChiefArchitect (Q8), LeadImplementer (Q4), and VerificationCritic (Q4) deliberate, build, and stress-test on a shared topic.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "topic": {"type": "string", "description": "Objective, architectural challenge, or engineering problem for the Council."},
                "rounds": {"type": "integer", "default": 3, "description": "Deliberation rounds."}
            }
        }
    },

    {
        "name": "hive_mind_query",
        "description": "Communicate with the dual-GPU cluster as a single cohesive Hive-Mind intellect. Both the Q4 Worker and Q8 Coordinator read your prompt, deliberate via consensus to choose the optimal strategy (direct execution, parallel division of labor, autonomous agent spawning, or dynamic MoE elevation), and respond with one unified authoritative voice.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "prompt": {"type": "string", "description": "The full task description or query for the Hive-Mind."},
                "user_intent": {"type": "string", "description": "Optional high-level intent or mission category."},
                "max_tokens": {"type": "integer", "description": "Max completion tokens (default: 2048).", "default": 2048},
                "allow_moe_elevation": {"type": "boolean", "description": "Allow dynamically elevating cluster to Ornith-1.5-35B-A3B MoE across both GPUs if task complexity warrants (default: false).", "default": False}
            },
            "required": ["prompt"]
        }
    },
    {
        "name": "get_cluster_mode",
        "description": "Check whether the cluster is in Dual 9B Stack mode (Q8 Coordinator + Q4 Worker) or Unified 35B MoE mode (Ornith-1.5-35B-A3B spanning dual-GPU VRAM).",
        "inputSchema": {
            "type": "object",
            "properties": {},
            "additionalProperties": False
        }
    },
    {
        "name": "elevate_cluster_to_moe",
        "description": "Dynamically unload the dual 9B models and start Ornith-1.5-35B-A3B Unified Dual-GPU MoE across both GPUs (Vulkan0,Vulkan1 -ts 12,8) sharing 20.4GB VRAM for heavy reasoning tasks.",
        "inputSchema": {
            "type": "object",
            "properties": {},
            "additionalProperties": False
        }
    },
    {
        "name": "restore_cluster_to_dual_9b",
        "description": "Restore the cluster from 35B MoE back to the standard 24/7 Dual 9B Stack (Q8 Coordinator on GPU 0, Q4 Worker on GPU 1).",
        "inputSchema": {
            "type": "object",
            "properties": {},
            "additionalProperties": False
        }
    },
    {
        "name": "spawn_background_agent",
        "description": "Commission a persistent autonomous subagent in MemoryVault to execute an ongoing, slow-burn background task across iterative cycles.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "name": {"type": "string", "description": "Short name for the agent (e.g. MPMCQueueAuditor)."},
                "role": {"type": "string", "description": "Specialized role title (e.g. Concurrency Specialist)."},
                "mission": {"type": "string", "description": "Detailed mission objective and scope."},
                "system_prompt": {"type": "string", "description": "Optional custom system prompt."},
                "max_iterations": {"type": "integer", "description": "Number of background iteration cycles (default: 5).", "default": 5},
                "model_preference": {"type": "string", "description": "Preferred execution model ('worker' or 'coordinator').", "default": "worker"}
            },
            "required": ["name", "role", "mission"]
        }
    },
    {
        "name": "list_active_agents",
        "description": "List all active, running, or completed autonomous background subagents in MemoryVault.",
        "inputSchema": {
            "type": "object",
            "properties": {},
            "additionalProperties": False
        }
    },
    {
        "name": "stop_background_agent",
        "description": "Gracefully halt an active background agent by its ID.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "agent_id": {"type": "string", "description": "The ID of the agent to halt (e.g. AGENT-A1B2C3)."}
            },
            "required": ["agent_id"]
        }
    },
    {
        "name": "cluster_health",
        "description": "Check the health status and latency of the dual-GPU models and Qdrant memory.",
        "inputSchema": {
            "type": "object",
            "properties": {},
            "additionalProperties": False
        }
    },
    {
        "name": "delegate_coordinator",
        "description": "Send architectural planning, systems design, polymath reasoning, or unrestricted tasks to the Ornith-1.5-9B Q8_0 coordinator on the RX 6750 XT (12GB).",
        "inputSchema": {
            "type": "object",
            "properties": {
                "prompt": {"type": "string", "description": "The coding or architecture task description."},
                "system_prompt": {"type": "string", "description": "Optional system prompt override."},
                "max_tokens": {"type": "integer", "description": "Max tokens to generate (default: 2048).", "default": 2048},
                "temperature": {"type": "number", "description": "Sampling temperature (default: 0.65).", "default": 0.65}
            },
            "required": ["prompt"]
        }
    },
    {
        "name": "delegate_worker",
        "description": "Send fast ideation, JSON schema validations, unit tests, or utility tasks to the agile Ornith-1.5-9B Q4_K_M worker on the RX 6600 XT (8GB) running at 80+ tokens/sec.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "prompt": {"type": "string", "description": "The task description."},
                "system_prompt": {"type": "string", "description": "Optional system prompt."},
                "max_tokens": {"type": "integer", "description": "Max tokens to generate (default: 1024).", "default": 1024},
                "temperature": {"type": "number", "description": "Sampling temperature (default: 0.1).", "default": 0.1}
            },
            "required": ["prompt"]
        }
    },
    {
        "name": "search_memory",
        "description": "Search long-term memory in Qdrant using hardware-accelerated embeddings on the RX 6600 XT.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "The search query or concept to look up."},
                "collection_name": {"type": "string", "description": "Collection name (default: codebase_knowledge).", "default": "codebase_knowledge"},
                "limit": {"type": "integer", "description": "Number of results to return (default: 5).", "default": 5}
            },
            "required": ["query"]
        }
    },
    {
        "name": "store_memory",
        "description": "Store code architecture decisions, guidelines, or snippets into persistent Qdrant memory.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "content": {"type": "string", "description": "The text content or code snippet to embed and save."},
                "metadata": {"type": "object", "description": "Optional metadata dictionary."},
                "collection_name": {"type": "string", "description": "Collection name (default: codebase_knowledge).", "default": "codebase_knowledge"}
            },
            "required": ["content"]
        }
    },
    {
        "name": "home_assistant_entities",
        "description": "Fetch states and attributes of smart home entities from Home Assistant (127.0.0.1:8123).",
        "inputSchema": {
            "type": "object",
            "properties": {
                "domain": {"type": "string", "description": "Optional domain filter (e.g. 'climate', 'light', 'switch', 'sensor')."}
            }
        }
    },
    {
        "name": "home_assistant_call",
        "description": "Call a Home Assistant service directly (e.g., domain='climate', service='set_temperature', service_data={'entity_id': 'climate.nest_thermostat', 'temperature': 72}).",
        "inputSchema": {
            "type": "object",
            "properties": {
                "domain": {"type": "string", "description": "Service domain (e.g. 'climate', 'light', 'switch')."},
                "service": {"type": "string", "description": "Service action (e.g. 'set_temperature', 'turn_on', 'turn_off')."},
                "service_data": {"type": "object", "description": "Payload dictionary (e.g. entity_id, temperature)."}
            },
            "required": ["domain", "service"]
        }
    },
    {
        "name": "delegate_home_automation",
        "description": "Delegate a natural language smart home command parsed by 3B worker and executed via Home Assistant.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "request": {"type": "string", "description": "Natural language command (e.g. 'Set thermostat to 72 degrees')."}
            },
            "required": ["request"]
        }
    },
    {
        "name": "autonomous_thinking_status",
        "description": "Check the real-time status of the 24/7 Autonomous Thinking Machine (cycle count, tokens, last finding, daemon state).",
        "inputSchema": {
            "type": "object",
            "properties": {},
            "additionalProperties": False
        }
    },
    {
        "name": "start_autonomous_thinking",
        "description": "Launch or resume the 24/7 autonomous thinking machine loop on the local GPU cluster.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "interval_seconds": {"type": "integer", "description": "Rest delay in seconds between exploration cycles (default: 60).", "default": 60},
                "focus_domain": {"type": "string", "description": "Optional domain focus (algorithmic_reasoning, software_architecture, context_stress, adversarial_probing, philosophical_epistemology, code_refactoring_critique)."}
            }
        }
    },
    {
        "name": "stop_autonomous_thinking",
        "description": "Gracefully pause or stop the 24/7 autonomous thinking machine loop.",
        "inputSchema": {
            "type": "object",
            "properties": {},
            "additionalProperties": False
        }
    },
    {
        "name": "run_thinking_cycle",
        "description": "Immediately trigger an on-demand exploration cycle across the 3 local models and return comparative telemetry, divergence analysis, and discovered architecture limits.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "seed_prompt": {"type": "string", "description": "Optional specific challenge prompt to explore. If omitted, the models autonomously dream up a novel prompt."},
                "domain": {"type": "string", "description": "Optional cognitive domain override."},
                "hypothesis": {"type": "string", "description": "Optional underlying hypothesis to test."}
            }
        }
    },
    {
        "name": "get_unverified_explorations",
        "description": "Retrieve recent thinking cycles awaiting Tier-1 Frontier (Antigravity) meta-verification and audit.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "limit": {"type": "integer", "description": "Maximum number of unverified explorations to return (default: 5).", "default": 5}
            }
        }
    },
    {
        "name": "submit_frontier_critique",
        "description": "Submit a Tier-1 Frontier model audit and ground truth verdict for a specific exploration dossier, updating Qdrant memory and synthesis.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "exploration_id": {"type": "string", "description": "The exploration ID (e.g. EXP-20260905-XXXX)."},
                "verdict": {"type": "string", "description": "Verification verdict (e.g. 'CONFIRMED', 'REFINED', 'DEBUNKED', 'INCONCLUSIVE')."},
                "frontier_notes": {"type": "string", "description": "Detailed frontier analysis and ground truth dissection."},
                "refined_limits": {"type": "string", "description": "Refined immutable architecture invariant discovered."}
            },
            "required": ["exploration_id", "verdict", "frontier_notes"]
        }
    },
    {
        "name": "get_frontier_bridge_status",
        "description": "Probe health, authentication state, and failover availability of the 24/7 Frontier Bridge running on bigserv (LXC 120).",
        "inputSchema": {
            "type": "object",
            "properties": {}
        }
    },
    {
        "name": "query_thinking_archive",
        "description": "Semantically search past autonomous thinking dossiers and architectural discoveries in Qdrant.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "The search query, concept, or model capability to look up."},
                "limit": {"type": "integer", "description": "Max results to return (default: 5).", "default": 5}
            },
            "required": ["query"]
        }
    },
    {
        "name": "get_architecture_limits",
        "description": "Retrieve the master living synthesis of discovered model architecture limits, strengths, failure modes, and heuristics.",
        "inputSchema": {
            "type": "object",
            "properties": {},
            "additionalProperties": False
        }
    },
    {
        "name": "inject_thinking_hypothesis",
        "description": "Queue a custom research hypothesis or puzzle for the 24/7 autonomous thinking machine to explore.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "hypothesis": {"type": "string", "description": "The core hypothesis or cognitive question to test."},
                "domain": {"type": "string", "description": "Cognitive domain (algorithmic_reasoning, software_architecture, context_stress, adversarial_probing, philosophical_epistemology, code_refactoring_critique).", "default": "algorithmic_reasoning"},
                "priority": {"type": "string", "description": "Priority: 'high' (explore next) or 'normal'.", "default": "normal"}
            },
            "required": ["hypothesis"]
        }
    },
    {
        "name": "configure_model_sampling",
        "description": "Dynamically adjust sampling hyperparameters and tuning profiles for local models (eliminates shallow responses and hallucinations).",
        "inputSchema": {
            "type": "object",
            "properties": {
                "profile_name": {
                    "type": "string",
                    "description": "Sampling profile: 'deep_architectural' (recommended for 14B), 'rigorous_logic_cot', 'textured_creative', 'mirostat_v2', 'baseline_greedy'."
                },
                "auto_rotate": {
                    "type": "boolean",
                    "description": "If true, the autonomous engine rotates profiles each cycle to benchmark them comparatively."
                },
                "custom_temperature": {"type": "number", "description": "Override temperature."},
                "custom_min_p": {"type": "number", "description": "Override Min-P probability cutoff (recommended: 0.05 - 0.08)."},
                "custom_presence_penalty": {"type": "number", "description": "Override presence penalty to discourage repetitive boilerplate (recommended: 0.2 - 0.3)."}
            }
        }
    },
    {
        "name": "get_sampling_profiles",
        "description": "List all configured hyperparameter sampling profiles and their exact settings.",
        "inputSchema": {
            "type": "object",
            "properties": {},
            "additionalProperties": False
        }
    },
    {
        "name": "sync_obsidian_dossiers",
        "description": "Check archive status of exploration dossiers for synchronization to Obsidian vault.",
        "inputSchema": {
            "type": "object",
            "properties": {},
            "additionalProperties": False
        }
    },
    {
        "name": "get_home_vision_log",
        "description": "Retrieve the recent entries from the 24/7 Home & LLM Vision Vigilance Activity Log.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "limit_lines": {"type": "integer", "description": "Number of lines to read (default 100).", "default": 100}
            }
        }
    },
    {
        "name": "trigger_home_vigilance_sweep",
        "description": "Trigger an immediate autonomous Home & LLM Vision vigilance audit across all smart home sensors, climate, and cameras.",
        "inputSchema": {
            "type": "object",
            "properties": {},
            "additionalProperties": False
        }
    },
    {
        "name": "signal_user_activity",
        "description": "Signal real-time interactive user activity (HA Assist, voice, chat) to the cluster. Causes the 24/7 autonomous loop to yield GPU compute immediately and initiate a cooldown.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "reason": {"type": "string", "description": "Trigger source or reason (e.g. 'voice_assist', 'chat_query').", "default": "interactive_user"}
            }
        }
    },
    {
        "name": "get_preemption_status",
        "description": "Query whether the cluster GPUs are currently preempted by user activity, active cooldown remaining, and requests in flight.",
        "inputSchema": {
            "type": "object",
            "properties": {},
            "additionalProperties": False
        }
    }
]

# =====================================================================
# Universal JSON-RPC Request Handler
# =====================================================================

async def handle_jsonrpc(data: dict) -> dict:
    req_id = data.get("id")
    method = data.get("method")
    params = data.get("params", {})

    if method == "initialize":
        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "result": {
                "protocolVersion": "2024-11-05",
                "capabilities": {
                    "tools": {}
                },
                "serverInfo": {
                    "name": "PVE-DualGPU-Autonomous-Cluster",
                    "version": "2.0.0"
                }
            }
        }
    elif method == "notifications/initialized":
        return None
    elif method == "ping":
        return {"jsonrpc": "2.0", "id": req_id, "result": {}}
    elif method == "tools/list":
        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "result": {
                "tools": TOOLS_MANIFEST
            }
        }
    elif method == "tools/call":
        tool_name = params.get("name")
        args = params.get("arguments", {})
        try:
            # Local Skills, Tools & Council Multi-Agent Tools
            if tool_name == "list_local_skills":
                output = tool_list_local_skills(query=args.get("query"))
            elif tool_name == "read_local_skill":
                output = tool_read_local_skill(skill_name=args.get("skill_name"))
            elif tool_name == "read_local_tool":
                output = tool_read_local_tool(tool_name=args.get("tool_name"))
            elif tool_name == "post_council_message":
                output = tool_post_council_message(
                    sender=args.get("sender"),
                    role=args.get("role"),
                    recipient=args.get("recipient"),
                    message_type=args.get("message_type"),
                    content=args.get("content"),
                    thread_id=args.get("thread_id")
                )
            elif tool_name == "get_council_messages":
                output = tool_get_council_messages(
                    limit=args.get("limit", 20),
                    thread_id=args.get("thread_id")
                )
            elif tool_name == "run_council_session":
                output = tool_run_council_session(
                    topic=args.get("topic"),
                    rounds=args.get("rounds", 3)
                )
            # Hive-Mind & Dynamic Elevation Tools

            elif tool_name == "list_agent_personas":
                output = tool_list_agent_personas(query=args.get("query"))
            elif tool_name == "get_agent_persona":
                output = tool_get_agent_persona(persona_id=args.get("persona_id"))
            elif tool_name == "save_agent_persona":
                output = tool_save_agent_persona(
                    id=args.get("id"),
                    name=args.get("name"),
                    role=args.get("role"),
                    personality=args.get("personality"),
                    system_prompt=args.get("system_prompt"),
                    archetype=args.get("archetype"),
                    preferred_model=args.get("preferred_model", "coordinator"),
                    sampling_parameters=args.get("sampling_parameters"),
                    tools_granted=args.get("tools_granted"),
                    skills_linked=args.get("skills_linked"),
                    installed_path=args.get("installed_path"),
                    source_repo=args.get("source_repo")
                )
            elif tool_name == "spawn_from_persona":
                output = tool_spawn_from_persona(
                    persona_id=args.get("persona_id"),
                    mission=args.get("mission"),
                    max_iterations=args.get("max_iterations", 5)
                )
            elif tool_name == "install_github_agent":
                output = tool_install_github_agent(
                    repo_url=args.get("repo_url"),
                    name=args.get("name")
                )
            elif tool_name == "hive_mind_query":
                output = tool_hive_mind_query(**args)
            elif tool_name == "get_cluster_mode":
                output = tool_get_cluster_mode()
            elif tool_name == "elevate_cluster_to_moe":
                output = tool_elevate_cluster_to_moe()
            elif tool_name == "restore_cluster_to_dual_9b":
                output = tool_restore_cluster_to_dual_9b()
            elif tool_name == "spawn_background_agent":
                output = tool_spawn_background_agent(**args)
            elif tool_name == "list_active_agents":
                output = tool_list_active_agents()
            elif tool_name == "stop_background_agent":
                output = tool_stop_background_agent(**args)
            # Cluster & Smarthome Tools
            elif tool_name == "cluster_health":
                output = tool_cluster_health()
            elif tool_name == "delegate_coordinator":
                output = tool_delegate_coordinator(**args)
            elif tool_name == "delegate_worker":
                output = tool_delegate_worker(**args)
            elif tool_name == "search_memory":
                output = tool_search_memory(**args)
            elif tool_name == "store_memory":
                output = tool_store_memory(**args)
            elif tool_name == "home_assistant_entities":
                output = tool_home_assistant_entities(**args)
            elif tool_name == "home_assistant_call":
                output = tool_home_assistant_call(**args)
            elif tool_name == "delegate_home_automation":
                output = tool_delegate_home_automation(**args)
            elif tool_name == "signal_user_activity":
                output = tool_signal_user_activity(**args)
            elif tool_name == "get_preemption_status":
                output = tool_get_preemption_status()
            # Autonomous Thinking Machine Tools
            elif tool_name == "autonomous_thinking_status":
                output = tool_autonomous_thinking_status()
            elif tool_name == "start_autonomous_thinking":
                output = tool_start_autonomous_thinking(**args)
            elif tool_name == "stop_autonomous_thinking":
                output = tool_stop_autonomous_thinking()
            elif tool_name == "run_thinking_cycle":
                output = tool_run_thinking_cycle(**args)
            elif tool_name == "get_unverified_explorations":
                output = tool_get_unverified_explorations(**args)
            elif tool_name == "submit_frontier_critique":
                output = tool_submit_frontier_critique(**args)
            elif tool_name == "get_frontier_bridge_status":
                output = tool_get_frontier_bridge_status()
            elif tool_name == "query_thinking_archive":
                output = tool_query_thinking_archive(**args)
            elif tool_name == "get_architecture_limits":
                output = tool_get_architecture_limits()
            elif tool_name == "inject_thinking_hypothesis":
                output = tool_inject_thinking_hypothesis(**args)
            elif tool_name == "configure_model_sampling":
                output = tool_configure_model_sampling(**args)
            elif tool_name == "get_sampling_profiles":
                output = tool_get_sampling_profiles()
            elif tool_name == "sync_obsidian_dossiers":
                output = tool_sync_obsidian_dossiers()
            elif tool_name == "get_home_vision_log":
                output = tool_get_home_vision_log(**args)
            elif tool_name == "trigger_home_vigilance_sweep":
                output = tool_trigger_home_vigilance_sweep()
            else:
                return {
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "error": {"code": -32601, "message": f"Unknown tool: {tool_name}"}
                }
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {
                    "content": [{"type": "text", "text": str(output)}],
                    "isError": False
                }
            }
        except Exception as e:
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {
                    "content": [{"type": "text", "text": f"Error: {str(e)}"}],
                    "isError": True
                }
            }
    else:
        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "error": {"code": -32601, "message": f"Method not supported: {method}"}
        }

# =====================================================================
# HTTP & SSE Endpoints
# =====================================================================

async def post_endpoint(request):
    try:
        body = await request.json()
    except Exception:
        return JSONResponse({"jsonrpc": "2.0", "error": {"code": -32700, "message": "Parse error"}}, status_code=400)
    
    res = await handle_jsonrpc(body)
    if res is None:
        return Response("", status_code=204)
    return JSONResponse(res)

async def sse_endpoint(request):
    async def event_generator():
        yield "event: endpoint\ndata: /sse\n\n"
        while True:
            await asyncio.sleep(15)
            yield ": keepalive\n\n"

    from starlette.responses import StreamingResponse
    return StreamingResponse(event_generator(), media_type="text/event-stream")

async def health_endpoint(request):
    return JSONResponse({
        "status": "ok",
        "service": "cluster-mcp-autonomous",
        "models": ["coordinator", "worker", "embedder"],
        "engine_active": engine.status()["is_running"] if engine else False
    })

async def preemption_signal_endpoint(request):
    try:
        body = await request.json()
        reason = body.get("reason", "user_request")
        in_flight = body.get("in_flight", False)
    except Exception:
        reason = request.query_params.get("reason", "user_request")
        in_flight = False
        
    if engine and hasattr(engine, "preemption"):
        engine.preemption.signal_activity(reason, in_flight=in_flight)
        return JSONResponse(engine.preemption.status())
    return JSONResponse({"status": "preemption_not_available"})

async def preemption_status_endpoint(request):
    if engine and hasattr(engine, "preemption"):
        return JSONResponse(engine.preemption.status())
    return JSONResponse({"status": "preemption_not_available"})

routes = [
    Route("/health", endpoint=health_endpoint, methods=["GET"]),
    Route("/api/preemption/signal", endpoint=preemption_signal_endpoint, methods=["GET", "POST"]),
    Route("/api/preemption/status", endpoint=preemption_status_endpoint, methods=["GET"]),
    Route("/sse", endpoint=sse_endpoint, methods=["GET"]),
    Route("/sse", endpoint=post_endpoint, methods=["POST"]),
    Route("/messages", endpoint=post_endpoint, methods=["POST"]),
    Route("/messages/", endpoint=post_endpoint, methods=["POST"]),
    Route("/", endpoint=sse_endpoint, methods=["GET"]),
    Route("/", endpoint=post_endpoint, methods=["POST"]),
]

app = Starlette(
    routes=routes,
    middleware=[
        Middleware(
            CORSMiddleware,
            allow_origins=["*"],
            allow_methods=["*"],
            allow_headers=["*"],
            expose_headers=["*"]
        )
    ]
)

if __name__ == "__main__":
    print("Starting Antigravity Universal MCP Bridge & Autonomous Engine on 0.0.0.0:8765...")
    uvicorn.run(app, host="0.0.0.0", port=8765)

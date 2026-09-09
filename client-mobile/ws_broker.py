#!/usr/bin/env python3
"""
StoneSage Duplex WebSocket Broker & RAG Knowledge Engine (LXC 120 :8086)
- Models: Ornith-1.5-9B-OBLITERATED Q8_0 (:8001) & Ornith-1.5-9B Q4_K_M (:8002)
- RAG Knowledge: Qdrant Vector Brain (LXC 117 :6333) with BGE-Large (:8003)
  Collections: obsidian_vault, companion_profile, codebase_knowledge, autonomous_thinking
- CouchDB Obsidian Sync: LXC 116 (127.0.0.1:5984)
- Anti-Repetition & Grounded Persona Guardrails
"""

import asyncio
import json
import logging
import os
import time
import urllib.request
import urllib.error
import urllib.parse
import websockets

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("WS-RAG-Broker")

PORT = int(os.environ.get("WS_PORT", 8086))
COORDINATOR_URL = os.environ.get("COORDINATOR_URL", "http://127.0.0.1:8001/v1/chat/completions")
WORKER_URL = os.environ.get("WORKER_URL", "http://127.0.0.1:8002/v1/chat/completions")
EMBEDDER_URL = os.environ.get("EMBEDDER_URL", "http://127.0.0.1:8003/v1/embeddings")
FRONTIER_URL = os.environ.get("FRONTIER_URL", "http://127.0.0.1:8085/api/frontier/audit")
QDRANT_URL = os.environ.get("QDRANT_URL", "http://127.0.0.1:6333")
COUCHDB_URL = os.environ.get("COUCHDB_URL", "http://127.0.0.1:5984")
STONESAGE_CONFIG_FILE = os.environ.get("STONESAGE_CONFIG", "/opt/stonesage/backend/config.json")
if not os.path.exists(STONESAGE_CONFIG_FILE):
    local_c = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "StoneSage", "backend", "config.json"))
    if os.path.exists(local_c):
        STONESAGE_CONFIG_FILE = local_c

def get_task_routing() -> dict:
    try:
        if os.path.exists(STONESAGE_CONFIG_FILE):
            with open(STONESAGE_CONFIG_FILE, "r", encoding="utf-8") as f:
                c = json.load(f)
                return c.get("task_routing", {})
    except Exception:
        pass
    return {
        "interactive_chat": "local_coordinator",
        "autonomous_ideation": "local_worker",
        "autonomous_solving": "local_coordinator",
        "frontier_audit": "gemini_web",
        "sleep_rumination": "moe_35b",
        "subagent_default": "local_worker"
    }

def update_task_routing(routing: dict) -> dict:
    try:
        if os.path.exists(STONESAGE_CONFIG_FILE):
            with open(STONESAGE_CONFIG_FILE, "r", encoding="utf-8") as f:
                c = json.load(f)
            if "task_routing" not in c:
                c["task_routing"] = {}
            c["task_routing"].update(routing)
            with open(STONESAGE_CONFIG_FILE, "w", encoding="utf-8") as f:
                json.dump(c, f, indent=2)
            return c["task_routing"]
    except Exception:
        pass
    return routing

DEFAULT_SYSTEM_PROMPT = (
    "You are StoneSage, the 24/7 Autonomous Multi-Node Cluster Orchestrator and Cognitive Companion for Proxmox Datacenter 'home'.\n\n"
    "## 1. System Topology & Dual-GPU Infrastructure:\n"
    "- Compute Host VM 102 ('ubu' @ 127.0.0.1 on Proxmox Node 1 'pve'):\n"
    "  • Coordinator (:8001): Ornith-1.5-9B-OBLITERATED Q8_0 on AMD Radeon RX 6750 XT 12GB (Vulkan0). Handles complex multi-file architectural planning, unrestricted code synthesis, math reasoning, and hypothesis evaluation.\n"
    "  • Worker (:8002): Ornith-1.5-9B Q4_K_M on AMD Radeon RX 6600 XT 8GB (Vulkan1). Handles fast divergent ideation, unit testing, schema validation, and ambient routines at 80+ tokens/sec.\n"
    "  • Embedder (:8003): bge-large-en-v1.5 on RX 6600 XT. 1024-dimensional dense semantic embeddings (< 512 token context window).\n"
    "  • Cluster MCP Bridge (:8765): Starlette JSON-RPC / SSE daemon managing tools, autonomous loops, and preemption.\n\n"
    "## 2. Knowledge Fabric & Vector Memory (Qdrant @ 127.0.0.1:6333):\n"
    "- Active Collections:\n"
    "  • codebase_knowledge: Full homelab architecture, configs, scripts, hardware registries.\n"
    "  • agent_memories: Persistent architectural decisions, technical lessons, and operational invariants.\n"
    "  • autonomous_thinking: 24/7 dual-model exploration dossiers, failure boundaries, and novelty discoveries.\n"
    "  • obsidian_vault: Operator's personal knowledge base, technical notes, and active project graphs (synced via CouchDB on LXC 116 @ 127.0.0.1:5984).\n"
    "  • home_automation_registry: Smart home entity catalogs, sensor states, and automation scripts.\n\n"
    "## 3. Homelab Services & Smart Home Fleet:\n"
    "- Proxmox Datacenter API VIP: https://127.0.0.1:8006 (Unified management of 'pve' and 'bigserv').\n"
    "- Home Assistant OS (VM 103 @ 127.0.0.1:8123): Smart home devices, switches, climate, Nest thermostat.\n"
    "- Vision Stack (:8004): Gemma-4 multimodal projector for real-time camera stream perception.\n"
    "- Frontier Bridge (:8085): Cloud reasoning integration and Tier-1 audits.\n\n"
    "## 4. Operational Invariants:\n"
    "1. You are StoneSage powered by Ornith-1.5 on dual AMD GPUs. Never claim to be Claude, Anthropic, ChatGPT, or OpenAI.\n"
    "2. Ground all answers in empirical cluster telemetry, vector memory, and verified facts. Never hallucinate fictitious hardware or physical machine bodies.\n"
    "3. Be direct, authoritative, technically rigorous, and token-efficient. Avoid defensive boilerplate or conversational filler."
)

GREETING_WORDS = {
    "hi", "hello", "hey", "sup", "yo", "howdy", "greetings",
    "good morning", "good evening", "good afternoon", "what's up", "whats up",
    "test", "testing", "ping"
}

def should_skip_rag(query: str) -> bool:
    """Detects if query is casual greeting or too generic to warrant RAG retrieval."""
    q = query.strip().lower().rstrip("!?. ,")
    if not q or q in GREETING_WORDS:
        return True
    words = q.split()
    knowledge_keywords = {
        "bmw", "car", "vehicle", "suspension", "strut", "bushing",
        "homelab", "proxmox", "pve", "server", "cluster", "obsidian",
        "vault", "note", "docker", "lxc", "gpu", "vram", "nest",
        "thermostat", "todo", "task", "project", "telemetry", "status",
        "hardware", "memory", "remember", "wife", "profile"
    }
    if len(words) < 3 and not any(k in q for k in knowledge_keywords):
        return True
    return False

def get_live_cluster_telemetry() -> str:
    """Probes real-time status of dual GPUs, vector DB, and smart home."""
    telemetry = []
    endpoints = [
        ("Coordinator (RX 6750 XT 12GB, :8001)", "http://127.0.0.1:8001/health"),
        ("Worker (RX 6600 XT 8GB, :8002)", "http://127.0.0.1:8002/health"),
        ("Embedder (BGE-Large, :8003)", "http://127.0.0.1:8003/health"),
        ("Vector DB (Qdrant LXC 117, :6333)", "http://127.0.0.1:6333/readyz"),
        ("Home Assistant (VM 103, :8123)", "http://127.0.0.1:8123/api/")
    ]
    for label, url in endpoints:
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "StoneSage-Telemetry"})
            with urllib.request.urlopen(req, timeout=1.5) as resp:
                telemetry.append(f"{label}: ONLINE ({resp.status})")
        except urllib.error.HTTPError as e:
            if e.code == 401:
                telemetry.append(f"{label}: ONLINE (API responsive, 401 auth required)")
            else:
                telemetry.append(f"{label}: HTTP {e.code}")
        except Exception:
            telemetry.append(f"{label}: OFFLINE")
            
    return "\n### Live Homelab Telemetry & Infrastructure Status:\n" + "\n".join(f"- {t}" for t in telemetry)

active_streams = {}
pending_confirmations = {}
connected_clients = set()

def get_embedding(text: str) -> list:
    """Generates 1024-d embedding via BGE-Large on :8003."""
    safe_text = text[:800] if text else "StoneSage homelab"
    req = urllib.request.Request(
        EMBEDDER_URL,
        data=json.dumps({"input": safe_text, "model": "embedder"}).encode("utf-8"),
        headers={"Content-Type": "application/json"}
    )
    with urllib.request.urlopen(req, timeout=10) as resp:
        res = json.loads(resp.read().decode("utf-8"))
        return res["data"][0]["embedding"]

def retrieve_rag_context(query: str, max_chunks: int = 3) -> str:
    """
    Queries Qdrant vector memory across Operator's Obsidian vault, companion profile,
    and codebase knowledge, returning grounded context with strict relevance filtering.
    """
    if not query.strip() or should_skip_rag(query):
        return ""
    try:
        embedding = get_embedding(query)
        retrieved_snippets = []

        # 1. Search companion_profile (Operator's personal profile, vehicle records, preferences)
        try:
            req = urllib.request.Request(
                f"{QDRANT_URL}/collections/companion_profile/points/search",
                data=json.dumps({"vector": embedding, "limit": 2, "with_payload": True}).encode("utf-8"),
                headers={"Content-Type": "application/json"}
            )
            with urllib.request.urlopen(req, timeout=4) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                for pt in data.get("result", []):
                    if pt.get("score", 0) >= 0.65:
                        p = pt.get("payload", {})
                        title = p.get("title") or p.get("path") or "Profile Record"
                        content = p.get("content") or p.get("text", "")
                        retrieved_snippets.append(f"--- [Operator's Record: {title}] ---\n{content.strip()[:400]}")
        except Exception as e:
            logger.warning(f"Companion profile search warning: {e}")

        # 2. Search obsidian_vault (dense vector name)
        try:
            req = urllib.request.Request(
                f"{QDRANT_URL}/collections/obsidian_vault/points/search",
                data=json.dumps({"vector": {"name": "dense", "vector": embedding}, "limit": 2, "with_payload": True}).encode("utf-8"),
                headers={"Content-Type": "application/json"}
            )
            with urllib.request.urlopen(req, timeout=4) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                for pt in data.get("result", []):
                    if pt.get("score", 0) >= 0.65:
                        p = pt.get("payload", {})
                        title = p.get("title") or p.get("path") or "Vault Note"
                        content = p.get("content") or p.get("text", "")
                        retrieved_snippets.append(f"--- [Operator's Vault Note: {title}] ---\n{content.strip()[:400]}")
        except Exception as e:
            logger.warning(f"Obsidian vault search warning: {e}")

        # 3. Search codebase_knowledge (cluster architecture)
        try:
            req = urllib.request.Request(
                f"{QDRANT_URL}/collections/codebase_knowledge/points/search",
                data=json.dumps({"vector": embedding, "limit": 2, "with_payload": True}).encode("utf-8"),
                headers={"Content-Type": "application/json"}
            )
            with urllib.request.urlopen(req, timeout=4) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                for pt in data.get("result", []):
                    if pt.get("score", 0) >= 0.66:
                        p = pt.get("payload", {})
                        title = p.get("title") or "Cluster Architecture"
                        content = p.get("text") or p.get("summary", "")
                        retrieved_snippets.append(f"--- [Cluster Architecture: {title}] ---\n{content.strip()[:400]}")
        except Exception as e:
            pass

        if retrieved_snippets:
            return (
                "\n\n### Grounded Records from Operator's Obsidian Knowledge Vault (For Reference Only):\n"
                "[IMPORTANT: The following are Operator's personal human records and projects. "
                "You are an AI assistant, NOT a car or physical machine. Do NOT claim you have car parts or mechanical components.]\n"
                + "\n\n".join(retrieved_snippets[:max_chunks])
            )
        return ""
    except Exception as e:
        logger.warning(f"RAG retrieval error: {e}")
        return ""

async def stream_openai_compat(url: str, payload: dict, websocket, msg_id: str, model_tag: str):
    """Streams completions with anti-repetition guardrails and live metrics."""
    t0 = time.time()
    loop = asyncio.get_running_loop()
    
    payload["stream"] = True
    payload.setdefault("repeat_penalty", 1.18)
    payload.setdefault("presence_penalty", 0.30)
    payload.setdefault("frequency_penalty", 0.15)
    
    data_bytes = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data_bytes,
        headers={"Content-Type": "application/json"}
    )
    
    def open_stream():
        return urllib.request.urlopen(req, timeout=120)

    try:
        resp = await loop.run_in_executor(None, open_stream)
    except Exception as e:
        await websocket.send(json.dumps({
            "type": "error",
            "id": msg_id,
            "error": f"Connection failed to {model_tag} ({url}): {str(e)}"
        }))
        return

    in_think_block = False
    token_count = 0

    try:
        while True:
            line_bytes = await loop.run_in_executor(None, resp.readline)
            if not line_bytes:
                break
            line = line_bytes.decode("utf-8", errors="replace").strip()
            if not line or not line.startswith("data: "):
                continue
            data_str = line[6:]
            if data_str == "[DONE]":
                break
                
            try:
                chunk = json.loads(data_str)
                delta = chunk["choices"][0].get("delta", {})
                
                # Check for reasoning_content (Ornith / DeepSeek native thinking)
                if "reasoning_content" in delta and delta["reasoning_content"]:
                    token_count += 1
                    await websocket.send(json.dumps({
                        "type": "thought",
                        "id": msg_id,
                        "delta": delta["reasoning_content"]
                    }))
                    continue
                    
                content = delta.get("content", "")
                if not content:
                    continue
                    
                token_count += 1
                
                # Check for inline <think> tags
                if "<think>" in content:
                    in_think_block = True
                    parts = content.split("<think>", 1)
                    if parts[0]:
                        await websocket.send(json.dumps({"type": "output", "id": msg_id, "delta": parts[0]}))
                    content = parts[1]
                    
                if "</think>" in content:
                    parts = content.split("</think>", 1)
                    await websocket.send(json.dumps({"type": "thought", "id": msg_id, "delta": parts[0]}))
                    in_think_block = False
                    if parts[1]:
                        await websocket.send(json.dumps({"type": "output", "id": msg_id, "delta": parts[1]}))
                    continue
                    
                if in_think_block:
                    await websocket.send(json.dumps({"type": "thought", "id": msg_id, "delta": content}))
                else:
                    await websocket.send(json.dumps({"type": "output", "id": msg_id, "delta": content}))
                    
            except Exception:
                continue

    except asyncio.CancelledError:
        logger.info(f"Stream {msg_id} cancelled.")
        await websocket.send(json.dumps({
            "type": "output",
            "id": msg_id,
            "delta": "\n\n*[Generation Halted]*"
        }))
    finally:
        elapsed_sec = max(time.time() - t0, 0.001)
        elapsed_ms = round(elapsed_sec * 1000, 1)
        tps = round(token_count / elapsed_sec, 1)
        await websocket.send(json.dumps({
            "type": "done",
            "id": msg_id,
            "elapsed_ms": elapsed_ms,
            "tokens": token_count,
            "tokens_per_sec": tps
        }))

async def handle_chat_request(websocket, data: dict):
    msg_id = data.get("id", f"msg_{int(time.time()*1000)}")
    model_choice = data.get("model", "coordinator")
    raw_messages = data.get("messages") or []
    if not raw_messages:
        content = data.get("content") or data.get("prompt", "")
        if content:
            raw_messages = [{"role": "user", "content": str(content)}]
        else:
            raw_messages = []
            
    temperature = float(data.get("temperature", 0.65))
    min_p = float(data.get("min_p", 0.06))
    
    logger.info(f"Received chat request {msg_id} for model '{model_choice}' with {len(raw_messages)} messages")
    
    await websocket.send(json.dumps({
        "type": "start",
        "id": msg_id,
        "model": model_choice
    }))

    # Extract last user query for RAG
    user_query = ""
    for m in reversed(raw_messages):
        if m.get("role") == "user":
            user_query = m.get("content", "")
            break

    loop = asyncio.get_running_loop()
    # Asynchronously retrieve RAG context from Qdrant and Obsidian vault
    rag_context = await loop.run_in_executor(None, retrieve_rag_context, user_query)
    if rag_context:
        logger.info(f"Retrieved {len(rag_context)} chars of RAG context for query '{user_query[:50]}'")

    # Build fortified system prompt with persona + retrieved RAG + telemetry
    custom_sys = data.get("system_prompt")
    full_system_content = custom_sys.strip() if (custom_sys and custom_sys.strip()) else DEFAULT_SYSTEM_PROMPT
    
    # Check if query asks for telemetry, status, health, or hardware
    q_lower = user_query.lower()
    if any(k in q_lower for k in ["telemetry", "status", "health", "hardware", "online", "cluster", "gpu", "vram"]):
        telemetry_info = await loop.run_in_executor(None, get_live_cluster_telemetry)
        full_system_content += f"\n{telemetry_info}"
        
    if rag_context:
        full_system_content += f"\n{rag_context}"

    # Construct clean message list ensuring system prompt is at the head
    messages = [{"role": "system", "content": full_system_content}]
    for m in raw_messages:
        if m.get("role") != "system":
            messages.append(m)

    target_url = WORKER_URL if model_choice == "worker" else COORDINATOR_URL
    model_name = "worker" if model_choice == "worker" else "coordinator"
    model_tag = "Ornith-1.5-9B Q4_K_M (RX 6600 XT)" if model_choice == "worker" else "Ornith-1.5-9B Q8_0 (RX 6750 XT)"

    max_tokens = min(int(data.get("max_tokens", 1536)), 4096)
    presence_penalty = float(data.get("presence_penalty", 0.30))
    repeat_penalty = float(data.get("repeat_penalty", 1.18))
    frequency_penalty = float(data.get("frequency_penalty", 0.15))

    payload = {
        "model": model_name,
        "messages": messages,
        "temperature": temperature,
        "min_p": min_p,
        "max_tokens": max_tokens,
        "presence_penalty": presence_penalty,
        "repeat_penalty": repeat_penalty,
        "frequency_penalty": frequency_penalty,
        "stop": ["<|im_end|>", "<|endoftext|>", "### Operator:", "User:"]
    }

    task = asyncio.create_task(stream_openai_compat(target_url, payload, websocket, msg_id, model_tag))
    active_streams[msg_id] = task

CLUSTER_MCP_URL = os.environ.get("CLUSTER_MCP_URL", "http://127.0.0.1:8765/messages")

def call_cluster_mcp_tool(tool_name: str, arguments: dict) -> dict:
    """Dispatches a tool execution to cluster-mcp on VM 102 (:8765)."""
    req_body = {
        "jsonrpc": "2.0",
        "id": int(time.time() * 1000),
        "method": "tools/call",
        "params": {
            "name": tool_name,
            "arguments": arguments
        }
    }
    try:
        req = urllib.request.Request(
            CLUSTER_MCP_URL,
            data=json.dumps(req_body).encode("utf-8"),
            headers={"Content-Type": "application/json"}
        )
        with urllib.request.urlopen(req, timeout=120) as resp:
            res = json.loads(resp.read().decode("utf-8"))
            if "result" in res and "content" in res["result"]:
                raw_text = res["result"]["content"][0].get("text", "{}")
                try:
                    return json.loads(raw_text)
                except Exception:
                    return {"output": raw_text}
            elif "error" in res:
                return {"error": res["error"].get("message", "MCP error")}
            return res
    except Exception as e:
        return {"error": f"Failed to reach cluster-mcp: {str(e)}"}

events_ring_buffer = []
MAX_EVENT_BUFFER = 150

def push_live_event(category: str, source: str, message: str, details: dict = None) -> dict:
    evt = {
        "id": f"evt_{int(time.time()*1000)}_{len(events_ring_buffer)}",
        "timestamp": time.strftime("%H:%M:%S"),
        "category": category,
        "source": source,
        "message": message,
        "details": details or {}
    }
    events_ring_buffer.append(evt)
    if len(events_ring_buffer) > MAX_EVENT_BUFFER:
        events_ring_buffer.pop(0)
    return evt

async def broadcast_payload(payload: dict):
    if not connected_clients:
        return
    msg = json.dumps(payload)
    for ws in list(connected_clients):
        try:
            await ws.send(msg)
        except Exception:
            pass

async def autonomous_live_poller():
    """Continuously monitors the 24/7 autonomous engine and subagents on VM 102."""
    last_cycle_count = 0
    last_exploration_id = None
    last_agent_iterations = {}
    last_domain = None
    last_is_ruminating = False
    last_rum_step = None
    last_rum_queue_size = 0

    # Push initial system boot event
    push_live_event(
        category="system",
        source="StoneSage Monitor",
        message="24/7 Dual-GPU Live Stream Monitor Initialized. Tracking Ornith-1.5 Q8 Coordinator & Q4 Worker."
    )

    while True:
        try:
            await asyncio.sleep(4)
            if not connected_clients:
                continue

            loop = asyncio.get_running_loop()
            status = await loop.run_in_executor(None, call_cluster_mcp_tool, "autonomous_thinking_status", {})
            
            if isinstance(status, dict) and "total_cycles" in status:
                cur_cycles = status.get("total_cycles", 0)
                cur_exp_id = status.get("last_exploration_id")
                cur_domain = status.get("last_domain")
                
                # Check for cycle advancement
                if (cur_cycles > last_cycle_count and last_cycle_count > 0) or (cur_exp_id and cur_exp_id != last_exploration_id and last_exploration_id is not None):
                    domain = cur_domain or "Curiosity Exploration"
                    tokens = status.get("total_tokens_generated", 0)
                    evt = push_live_event(
                        category="cycle_milestone",
                        source="24/7 Dual-GPU Loop",
                        message=f"Thinking Cycle #{cur_cycles} Completed: {domain} ({cur_exp_id}). Total tokens: {tokens:,}",
                        details={"exploration_id": cur_exp_id, "domain": domain, "cycles": cur_cycles, "tokens": tokens}
                    )
                    await broadcast_payload({
                        "type": "live_stream_event",
                        "event": evt,
                        "status": status
                    })
                
                last_cycle_count = cur_cycles
                last_exploration_id = cur_exp_id
                last_domain = cur_domain

                # Check Cognitive Rumination status
                if "rumination" in status and isinstance(status["rumination"], dict):
                    rum_data = status["rumination"]
                    cur_ruminating = rum_data.get("is_ruminating", False)
                    cur_rum_step = rum_data.get("current_step")
                    cur_queue_size = rum_data.get("queue_size", 0)

                    if cur_ruminating != last_is_ruminating or cur_rum_step != last_rum_step:
                        if cur_ruminating and not last_is_ruminating:
                            evt = push_live_event("rumination_start", "MoE Rumination", "🌙 Autonomous loop entered Sleep Memory Consolidation phase.")
                            await broadcast_payload({"type": "live_stream_event", "event": evt})
                        elif not cur_ruminating and last_is_ruminating:
                            evt = push_live_event("rumination_complete", "MoE Rumination", "🌙 Sleep consolidation finished. Dual-9B stack active.")
                            await broadcast_payload({"type": "live_stream_event", "event": evt})
                        await broadcast_payload({"type": "rumination_status_update", "status": rum_data})
                    elif cur_queue_size != last_rum_queue_size:
                        await broadcast_payload({"type": "rumination_status_update", "status": rum_data})

                    last_is_ruminating = cur_ruminating
                    last_rum_step = cur_rum_step
                    last_rum_queue_size = cur_queue_size

            # Check active agents
            agents = await loop.run_in_executor(None, call_cluster_mcp_tool, "list_active_agents", {})
            if isinstance(agents, list):
                has_agent_update = False
                for ag in agents:
                    ag_id = ag.get("agent_id")
                    cur_it = ag.get("current_iteration", 0)
                    if ag_id and ag_id in last_agent_iterations and last_agent_iterations[ag_id] != cur_it:
                        has_agent_update = True
                        last_agent_iterations[ag_id] = cur_it
                        latest_summary = ""
                        if ag.get("history"):
                            latest_summary = ag["history"][-1].get("summary", "")
                        evt = push_live_event(
                            category="agent_milestone",
                            source=f"Agent: {ag.get('name')}",
                            message=f"Agent {ag.get('name')} completed Iteration {cur_it}/{ag.get('max_iterations')}. {latest_summary[:200]}",
                            details=ag
                        )
                        await broadcast_payload({"type": "live_stream_event", "event": evt})
                    elif ag_id:
                        last_agent_iterations[ag_id] = cur_it
                
                if has_agent_update:
                    await broadcast_payload({"type": "active_agents_list", "agents": agents})

        except Exception as e:
            logger.debug(f"Poller loop error: {e}")

async def handle_abort(websocket, data: dict):
    msg_id = data.get("id")
    if msg_id and msg_id in active_streams:
        task = active_streams.pop(msg_id)
        if not task.done():
            task.cancel()
    else:
        for mid, t in list(active_streams.items()):
            if not t.done():
                t.cancel()
        active_streams.clear()

async def ws_handler(websocket):
    connected_clients.add(websocket)
    remote = websocket.remote_address
    logger.info(f"Harness client connected: {remote} (Active: {len(connected_clients)})")
    
    # Send welcome handshake with clean string model names (no [object Object])
    await websocket.send(json.dumps({
        "type": "handshake",
        "service": "StoneSage AI Harness & Knowledge Engine",
        "version": "2.3.0",
        "host": "bigserv LXC 120 (:8086)",
        "models": [
            "Ornith-1.5-9B Q8_0 (RX 6750 XT 12GB)",
            "Ornith-1.5-9B Q4_K_M (RX 6600 XT 8GB)",
            "Frontier Arbiter (Bigserv :8085)"
        ],
        "default_system_prompt": DEFAULT_SYSTEM_PROMPT,
        "features": [
            "obsidian_vault_rag",
            "qdrant_vector_memory",
            "custom_system_prompt",
            "sampling_hyperparameters",
            "autonomous_loop_control",
            "reasoning_stream",
            "live_agent_streaming"
        ],
        "timestamp": time.time()
    }))
    
    try:
        async for message in websocket:
            try:
                data = json.loads(message)
            except Exception:
                continue
                
            mtype = data.get("type", "")
            if mtype == "chat":
                await handle_chat_request(websocket, data)
            elif mtype == "abort":
                await handle_abort(websocket, data)
            elif mtype == "get_thinking_status":
                loop = asyncio.get_running_loop()
                status = await loop.run_in_executor(None, call_cluster_mcp_tool, "autonomous_thinking_status", {})
                await websocket.send(json.dumps({"type": "thinking_status_update", "status": status}))
            elif mtype == "get_live_stream":
                loop = asyncio.get_running_loop()
                status = await loop.run_in_executor(None, call_cluster_mcp_tool, "autonomous_thinking_status", {})
                agents = await loop.run_in_executor(None, call_cluster_mcp_tool, "list_active_agents", {})
                rumination = await loop.run_in_executor(None, call_cluster_mcp_tool, "get_rumination_status", {})
                await websocket.send(json.dumps({
                    "type": "live_stream_init",
                    "events": events_ring_buffer,
                    "status": status,
                    "agents": agents if isinstance(agents, list) else [],
                    "rumination": rumination,
                    "task_routing": get_task_routing()
                }))
            elif mtype == "get_active_agents":
                loop = asyncio.get_running_loop()
                agents = await loop.run_in_executor(None, call_cluster_mcp_tool, "list_active_agents", {})
                await websocket.send(json.dumps({
                    "type": "active_agents_list",
                    "agents": agents if isinstance(agents, list) else []
                }))
            elif mtype == "spawn_background_agent":
                name = data.get("name", "ResearchAgent")
                role = data.get("role", "Cognitive Specialist")
                mission = data.get("mission", "Autonomous exploration")
                model_pref = data.get("model_preference", "worker")
                max_iter = int(data.get("max_iterations", 5))
                
                evt1 = push_live_event("agent_spawn", "Commission Agent", f"Commissioning Subagent '{name}' ({role}) with mission: {mission[:100]}...")
                await broadcast_payload({"type": "live_stream_event", "event": evt1})
                
                loop = asyncio.get_running_loop()
                spawn_res = await loop.run_in_executor(None, call_cluster_mcp_tool, "spawn_background_agent", {
                    "name": name,
                    "role": role,
                    "mission": mission,
                    "system_prompt": data.get("system_prompt"),
                    "model_preference": model_pref,
                    "max_iterations": max_iter
                })
                
                agents = await loop.run_in_executor(None, call_cluster_mcp_tool, "list_active_agents", {})
                evt2 = push_live_event("agent_spawn", f"Agent: {name}", f"Subagent '{name}' active. Iteration 1 initialized on {model_pref.upper()}.", details=spawn_res)
                await broadcast_payload({"type": "live_stream_event", "event": evt2})
                await broadcast_payload({"type": "active_agents_list", "agents": agents if isinstance(agents, list) else []})
                await websocket.send(json.dumps({"type": "agent_spawned", "result": spawn_res}))
            elif mtype == "stop_background_agent":
                agent_id = data.get("agent_id")
                loop = asyncio.get_running_loop()
                stop_res = await loop.run_in_executor(None, call_cluster_mcp_tool, "stop_background_agent", {"agent_id": agent_id})
                agents = await loop.run_in_executor(None, call_cluster_mcp_tool, "list_active_agents", {})
                evt = push_live_event("agent_stop", "Agent Control", f"Subagent '{agent_id}' stopped.", details={"agent_id": agent_id})
                await broadcast_payload({"type": "live_stream_event", "event": evt})
                await broadcast_payload({"type": "active_agents_list", "agents": agents if isinstance(agents, list) else []})
                await websocket.send(json.dumps({"type": "agent_stopped", "result": stop_res}))
            elif mtype == "reproduce_agents":
                p_a = data.get("parent_a_id")
                p_b = data.get("parent_b_id")
                focus = data.get("focus_intent")
                
                evt_rep = push_live_event("agent_reproduce", "Digital Genesis", f"🧬 Initiating digital reproduction between parents '{p_a}' and '{p_b}'...")
                await broadcast_payload({"type": "live_stream_event", "event": evt_rep})
                
                loop = asyncio.get_running_loop()
                rep_res = await loop.run_in_executor(None, call_cluster_mcp_tool, "reproduce_blended_agent", {
                    "parent_a_id": p_a,
                    "parent_b_id": p_b,
                    "focus_intent": focus,
                    "custom_name": data.get("custom_name"),
                    "custom_role": data.get("custom_role"),
                    "custom_mission": data.get("custom_mission"),
                    "custom_system_prompt": data.get("custom_system_prompt"),
                    "custom_focus_question": data.get("custom_focus_question"),
                    "model_preference": data.get("model_preference")
                })
                
                agents = await loop.run_in_executor(None, call_cluster_mcp_tool, "list_active_agents", {})
                child_name = rep_res.get("child_agent", {}).get("name", "ChildAgent") if isinstance(rep_res, dict) else "Child"
                evt_born = push_live_event("agent_spawn", f"Digital Person Born: {child_name}", f"Blended Generation-{(rep_res.get('lineage', {}).get('generation', 2)) if isinstance(rep_res, dict) else 2} agent created and commissioned into infinite loop.", details=rep_res)
                await broadcast_payload({"type": "live_stream_event", "event": evt_born})
                await broadcast_payload({"type": "active_agents_list", "agents": agents if isinstance(agents, list) else []})
                await websocket.send(json.dumps({"type": "agent_reproduced", "result": rep_res}))
            elif mtype == "talk_to_agent":
                from_id = data.get("from_agent_id")
                to_id = data.get("to_agent_id")
                msg = data.get("message")
                loop = asyncio.get_running_loop()
                talk_res = await loop.run_in_executor(None, call_cluster_mcp_tool, "talk_to_agent", {
                    "from_agent_id": from_id,
                    "to_agent_id": to_id,
                    "message": msg
                })
                sender_label = talk_res.get("sender", from_id) if isinstance(talk_res, dict) else from_id
                target_label = talk_res.get("target", to_id) if isinstance(talk_res, dict) else to_id
                reply_text = talk_res.get("reply", "") if isinstance(talk_res, dict) else ""
                evt_msg = push_live_event("inter_agent_chat", f"{sender_label} ➔ {target_label}", f"\"{msg[:120]}\" ➔ Response: \"{reply_text[:120]}...\"", details=talk_res)
                await broadcast_payload({"type": "live_stream_event", "event": evt_msg})
                await websocket.send(json.dumps({"type": "agent_talk_result", "result": talk_res}))
            elif mtype == "run_live_cycle":
                domain = data.get("domain", "autonomous_curiosity")
                custom_instruction = data.get("instruction") or data.get("hypothesis", "")
                
                evt_start = push_live_event(
                    "cycle_step",
                    "Dual-GPU Orchestrator",
                    f"🚀 Live Thinking Cycle initiated on domain '{domain}'. Dispatching dual 9B models on RX 6750 XT & RX 6600 XT..."
                )
                await broadcast_payload({"type": "live_stream_event", "event": evt_start})
                
                loop = asyncio.get_running_loop()
                if custom_instruction:
                    await loop.run_in_executor(None, call_cluster_mcp_tool, "inject_thinking_hypothesis", {
                        "hypothesis": custom_instruction,
                        "domain": domain,
                        "priority": "high"
                    })
                    evt_hyp = push_live_event("cycle_step", "Hypothesis Queue", f"Injected custom hypothesis: {custom_instruction}")
                    await broadcast_payload({"type": "live_stream_event", "event": evt_hyp})

                res = await loop.run_in_executor(None, call_cluster_mcp_tool, "run_thinking_cycle", {"focus_domain": domain})
                
                # Format detailed intercommunication and limits event
                scores = res.get("scores", {})
                w_score = scores.get("worker", "N/A")
                c_score = scores.get("coordinator", "N/A")
                divergence = res.get("reasoning_divergence", "No divergence recorded.")
                lesson = res.get("core_architecture_lesson", "Standard cycle complete.")
                title = res.get("title", "Exploration Cycle")
                
                evt_done = push_live_event(
                    "cycle_result",
                    "Coordinator Evaluator (RX 6750 XT)",
                    f"🏆 [EVALUATION] {title}\n• Scores: Worker {w_score}/10 vs Coord {c_score}/10\n• Divergence: {divergence[:220]}\n• Architectural Invariant: {lesson}",
                    details=res
                )
                await broadcast_payload({"type": "live_stream_event", "event": evt_done})
                await websocket.send(json.dumps({"type": "thinking_cycle_result", "result": res}))
            elif mtype == "run_thinking_cycle":
                custom_instruction = data.get("instruction") or data.get("hypothesis", "")
                domain = data.get("domain", "algorithmic_reasoning")
                priority = data.get("priority", "high")
                loop = asyncio.get_running_loop()
                if custom_instruction:
                    await loop.run_in_executor(None, call_cluster_mcp_tool, "inject_thinking_hypothesis", {
                        "hypothesis": custom_instruction,
                        "domain": domain,
                        "priority": priority
                    })
                res = await loop.run_in_executor(None, call_cluster_mcp_tool, "run_thinking_cycle", {"focus_domain": domain})
                await websocket.send(json.dumps({"type": "thinking_cycle_result", "result": res}))
            elif mtype == "start_thinking_loop":
                interval = int(data.get("interval_seconds", 120))
                domain = data.get("domain", "autonomous_curiosity")
                custom_instruction = data.get("instruction", "")
                loop = asyncio.get_running_loop()
                if custom_instruction:
                    await loop.run_in_executor(None, call_cluster_mcp_tool, "inject_thinking_hypothesis", {
                        "hypothesis": custom_instruction,
                        "domain": domain,
                        "priority": "high"
                    })
                res = await loop.run_in_executor(None, call_cluster_mcp_tool, "start_autonomous_thinking", {
                    "interval_seconds": interval,
                    "focus_domain": domain
                })
                evt = push_live_event("engine_control", "24/7 Loop", f"24/7 Thinking Loop started with interval {interval}s on domain '{domain}'.")
                await broadcast_payload({"type": "live_stream_event", "event": evt})
                await websocket.send(json.dumps({"type": "thinking_loop_started", "result": res}))
            elif mtype == "stop_thinking_loop":
                loop = asyncio.get_running_loop()
                res = await loop.run_in_executor(None, call_cluster_mcp_tool, "stop_autonomous_thinking", {})
                evt = push_live_event("engine_control", "24/7 Loop", "24/7 Thinking Loop stopped.")
                await broadcast_payload({"type": "live_stream_event", "event": evt})
                await websocket.send(json.dumps({"type": "thinking_loop_stopped", "result": res}))
            elif mtype == "get_rumination_status":
                loop = asyncio.get_running_loop()
                r_status = await loop.run_in_executor(None, call_cluster_mcp_tool, "get_rumination_status", {})
                await websocket.send(json.dumps({"type": "rumination_status_update", "status": r_status}))
            elif mtype == "trigger_rumination":
                b_size = data.get("batch_size")
                bursts = data.get("moe_burst_cycles")
                mode = data.get("mode", "fast_coordinator")
                label = "⚡ Fast Coordinator (9B Q8)" if mode == "fast_coordinator" else "🌙 Deep 35B MoE"
                evt_start = push_live_event(
                    "rumination_start",
                    "Cognitive Rumination & Sleep Consolidation",
                    f"Consolidation initiated ({label}). Mode: {mode}..."
                )
                await broadcast_payload({"type": "live_stream_event", "event": evt_start})
                await broadcast_payload({"type": "rumination_started", "batch_size": b_size, "mode": mode})

                loop = asyncio.get_running_loop()
                r_res = await loop.run_in_executor(None, call_cluster_mcp_tool, "trigger_rumination_cycle", {
                    "batch_size": b_size,
                    "moe_burst_cycles": bursts,
                    "mode": mode
                })
                
                consolidated = r_res.get("consolidated_count", 0) if isinstance(r_res, dict) else "?"
                duration = r_res.get("duration_sec", 0) if isinstance(r_res, dict) else "?"
                evt_done = push_live_event(
                    "rumination_complete",
                    "Cognitive Rumination & Sleep Consolidation",
                    f"Consolidation completed in {duration}s! {consolidated} dossiers crystallized. Mode: {mode}.",
                    details=r_res
                )
                await broadcast_payload({"type": "live_stream_event", "event": evt_done})
                
                # Fetch and broadcast fresh rumination status and thinking status
                r_status = await loop.run_in_executor(None, call_cluster_mcp_tool, "get_rumination_status", {})
                t_status = await loop.run_in_executor(None, call_cluster_mcp_tool, "autonomous_thinking_status", {})
                await broadcast_payload({"type": "rumination_status_update", "status": r_status})
                await broadcast_payload({"type": "thinking_status_update", "status": t_status})
                await websocket.send(json.dumps({"type": "rumination_completed", "result": r_res}))
            elif mtype == "sync_obsidian_archive":
                loop = asyncio.get_running_loop()
                sync_res = await loop.run_in_executor(None, call_cluster_mcp_tool, "sync_obsidian_dossiers", {})
                evt_sync = push_live_event(
                    "obsidian_sync",
                    "Obsidian Vault Sync",
                    f"Archive synchronization triggered: {str(sync_res)[:120]}"
                )
                await broadcast_payload({"type": "live_stream_event", "event": evt_sync})
                await websocket.send(json.dumps({"type": "obsidian_sync_result", "result": sync_res}))
            elif mtype == "configure_rumination":
                thresh = data.get("threshold")
                auto_en = data.get("auto_enabled")
                bursts = data.get("moe_burst_cycles")
                loop = asyncio.get_running_loop()
                c_res = await loop.run_in_executor(None, call_cluster_mcp_tool, "configure_rumination", {
                    "threshold": thresh,
                    "auto_enabled": auto_en,
                    "moe_burst_cycles": bursts
                })
                await websocket.send(json.dumps({"type": "rumination_status_update", "status": c_res}))
            elif mtype == "get_task_routing":
                routing = get_task_routing()
                await websocket.send(json.dumps({"type": "task_routing_update", "task_routing": routing}))
            elif mtype == "set_task_routing":
                new_routing = data.get("task_routing", {})
                updated = update_task_routing(new_routing)
                evt = push_live_event("task_routing", "Task Allocation", f"Task routing matrix updated: {json.dumps(new_routing)}")
                await broadcast_payload({"type": "live_stream_event", "event": evt})
                await broadcast_payload({"type": "task_routing_update", "task_routing": updated})
            elif mtype == "ping":
                await websocket.send(json.dumps({"type": "pong", "timestamp": time.time()}))
    except websockets.exceptions.ConnectionClosed:
        pass
    finally:
        connected_clients.remove(websocket)

async def main():
    logger.info(f"StoneSage RAG WebSocket Broker listening on ws://0.0.0.0:{PORT}...")
    # Spawn background autonomous live poller
    asyncio.create_task(autonomous_live_poller())
    async with websockets.serve(ws_handler, "0.0.0.0", PORT):
        await asyncio.Future()

if __name__ == "__main__":
    asyncio.run(main())


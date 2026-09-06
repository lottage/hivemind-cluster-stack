#!/usr/bin/env python3
"""
PVE Dual-GPU Cluster & Antigravity Project Backup Script
Embeds and backs up all project code, systemd units, configuration guides,
architectural decisions, and operational history into the Qdrant vector brain.
"""

import os
import sys
import uuid
import time
import json
import urllib.request
import urllib.error
from typing import Dict, Any, List

try:
    import requests
    HAS_REQUESTS = True
except ImportError:
    HAS_REQUESTS = False

EMBED_URL = os.getenv("EMBED_URL", "http://192.168.1.105:8003")
QDRANT_URL = os.getenv("QDRANT_URL", "http://192.168.1.112:6333")
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
WORKSPACE_ROOT = os.path.dirname(PROJECT_ROOT)

def _http_post(url: str, json_data: dict, timeout: int = 30) -> dict:
    if HAS_REQUESTS:
        r = requests.post(url, json=json_data, timeout=timeout)
        r.raise_for_status()
        return r.json()
    else:
        data = json.dumps(json_data).encode("utf-8")
        req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"}, method="POST")
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))

def _http_put(url: str, json_data: dict, timeout: int = 15) -> dict:
    if HAS_REQUESTS:
        r = requests.put(url, json=json_data, timeout=timeout)
        r.raise_for_status()
        return r.json()
    else:
        data = json.dumps(json_data).encode("utf-8")
        req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"}, method="PUT")
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))

def get_embedding(text: str) -> List[float]:
    """Fetch 1024-dimensional embedding from the RX 6600 XT BGE-Large engine."""
    res = _http_post(f"{EMBED_URL}/v1/embeddings", {"input": text, "model": "embedder"}, timeout=30)
    return res["data"][0]["embedding"]

def upsert_point(collection_name: str, content: str, metadata: Dict[str, Any]) -> str:
    """Embed and store a single document point into Qdrant."""
    vector = get_embedding(content)
    point_id = str(uuid.uuid4())
    payload = {
        "points": [
            {
                "id": point_id,
                "vector": vector,
                "payload": {
                    "content": content,
                    "metadata": metadata
                }
            }
        ]
    }
    _http_put(f"{QDRANT_URL}/collections/{collection_name}/points", payload, timeout=15)
    return point_id

def chunk_text(text: str, max_chars: int = 900) -> List[str]:
    """Split markdown / code content into digestible chunks that fit BGE 512-token limit."""
    lines = text.split("\n")
    chunks = []
    current = []
    current_len = 0
    for line in lines:
        line_len = len(line) + 1
        if current_len + line_len > max_chars and current:
            chunks.append("\n".join(current).strip())
            current = [line]
            current_len = line_len
        else:
            current.append(line)
            current_len += line_len
    if current:
        chunk_str = "\n".join(current).strip()
        if chunk_str:
            chunks.append(chunk_str)
    return chunks

def backup_project():
    print("=" * 65)
    print("  PVE Cluster Vector Brain Backup Engine")
    print(f"  Embedder URL: {EMBED_URL}")
    print(f"  Qdrant URL:   {QDRANT_URL}")
    print("=" * 65)

    # 1. Back up codebase and configuration files
    files_to_backup = [
        ("DEPLOYMENT_GUIDE.md", "guide", "codebase_knowledge"),
        ("NEST_THERMOSTAT_GUIDE.md", "guide", "codebase_knowledge"),
        ("COMPANION_MANIFESTO.md", "companion_charter", "companion_profile"),
        ("NETWORK_DEVICE_REGISTRY.md", "network_registry", "home_automation_registry"),
        ("NETWORK_DEVICE_REGISTRY.md", "network_registry", "codebase_knowledge"),
        ("cluster-bridge/mcp_server.py", "bridge_code", "codebase_knowledge"),
        ("cluster-bridge/requirements.txt", "dependencies", "codebase_knowledge"),
        ("vm-setup/01_install_vulkan_llamacpp.sh", "setup_script", "codebase_knowledge"),
        ("vm-setup/02_download_models.sh", "setup_script", "codebase_knowledge"),
        ("vm-setup/03_install_services.sh", "setup_script", "codebase_knowledge"),
        ("vm-setup/qdrant_init.py", "setup_script", "codebase_knowledge"),
        ("vm-setup/systemd/llama-coordinator.service", "systemd_service", "codebase_knowledge"),
        ("vm-setup/systemd/llama-worker.service", "systemd_service", "codebase_knowledge"),
        ("vm-setup/systemd/llama-embed.service", "systemd_service", "codebase_knowledge"),
        ("vm-setup/systemd/cluster-mcp.service", "systemd_service", "codebase_knowledge"),
        (os.path.join(WORKSPACE_ROOT, "GEMINI.md"), "directives", "codebase_knowledge"),
        (os.path.join(WORKSPACE_ROOT, "StoneSage", "backend", "config.json"), "stonesage_config", "codebase_knowledge"),
        (os.path.join(WORKSPACE_ROOT, "StoneSage", "backend", "server.py"), "stonesage_server", "codebase_knowledge"),
        (os.path.join(WORKSPACE_ROOT, "EasyDash", "manifest.webmanifest"), "pwa_manifest", "codebase_knowledge"),
        (os.path.join(WORKSPACE_ROOT, "EasyDash", "sw.js"), "service_worker", "codebase_knowledge"),
    ]

    total_indexed = 0

    print("\n[Phase 1] Indexing Project Source & Config Files into 'codebase_knowledge' & 'companion_profile'...")
    for file_spec, doc_type, collection in files_to_backup:
        full_path = file_spec if os.path.isabs(file_spec) else os.path.join(PROJECT_ROOT, file_spec)
        rel_path = os.path.relpath(full_path, WORKSPACE_ROOT)
        if not os.path.exists(full_path):
            print(f"  [SKIP] File not found: {rel_path}")
            continue

        with open(full_path, "r", encoding="utf-8", errors="replace") as f:
            content = f.read()

        chunks = chunk_text(content, max_chars=900)
        print(f"  -> {rel_path} ({len(chunks)} chunks, type: {doc_type}, collection: {collection})")
        for idx, chunk in enumerate(chunks):
            metadata = {
                "project": "pve-dual-gpu-cluster",
                "file_path": rel_path,
                "file_name": os.path.basename(rel_path),
                "doc_type": doc_type,
                "chunk_index": idx + 1,
                "total_chunks": len(chunks),
                "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")
            }
            point_id = upsert_point(collection, chunk, metadata)
            total_indexed += 1

    # 2. Back up high-level architectural knowledge into 'agent_memories'
    print("\n[Phase 2] Persisting Architecture Memories into 'agent_memories'...")
    architectural_memories = [
        {
            "title": "Hardware Allocation & Asymmetric Dual-GPU Architecture",
            "content": (
                "Hardware Topology:\n"
                "- Host: Proxmox VE (Node 'pve') with Intel Core i7-12700K (12 cores / 20 threads) and 32GB RAM.\n"
                "- GPU 0 (Vulkan0): AMD Radeon RX 6750 XT 12GB dedicated exclusively to Qwen2.5-Coder-14B-Instruct-abliterated (Q4_K_M) on port 8001.\n"
                "- GPU 1 (Vulkan1): AMD Radeon RX 6600 XT 8GB co-hosting Qwen2.5-Coder-3B-Instruct (Q5_K_M) on port 8002 and BGE-Large-EN-v1.5 (F16) on port 8003.\n"
                "- Memory Container: Qdrant vector database running in Proxmox container at 192.168.1.112:6333.\n"
                "- Ubuntu VM: 192.168.1.105 hosting llama.cpp Vulkan instances and MCP bridge on port 8765.\n"
                "Rationale: Eliminates GPU model splitting overhead and context synchronization penalties by dedicating separate models to asymmetric cards."
            ),
            "metadata": {"category": "architecture", "component": "hardware_topology"}
        },
        {
            "title": "Model Flags, KV Cache & Context Windows",
            "content": (
                "Llama-server Optimization Flags:\n"
                "1. Coordinator (14B, Port 8001): --device Vulkan0 -m /opt/models/qwen2.5-coder-14b-instruct-abliterated-q4_k_m.gguf "
                "-c 12288 --flash-attn on -ctk q4_0 -ctv q4_0 -ngl 99. Uses Q4_0 KV cache quantization to support 12k context in 12GB VRAM.\n"
                "2. Worker (3B, Port 8002): --device Vulkan1 -m /opt/models/qwen2.5-coder-3b-instruct-q5_k_m.gguf "
                "-c 8192 --flash-attn on -ctk q8_0 -ctv q8_0 -ngl 99. Runs at 80+ tokens/sec for rapid unit tests, docstrings, and JSON checks.\n"
                "3. Embedder (BGE-Large, Port 8003): --device Vulkan1 -m /opt/models/bge-large-en-v1.5-f16.gguf "
                "-c 2048 --embedding -ngl 99. Generates 1024-dim dense embeddings in sub-millisecond compute time for Qdrant."
            ),
            "metadata": {"category": "model_configuration", "component": "llama_server"}
        },
        {
            "title": "Vulkan & Systemd Technical Discoveries & Gotchas",
            "content": (
                "Critical Technical Lessons Learned:\n"
                "1. Vulkan Device Flag Syntax: llama-server requires '--device Vulkan0' or '--device Vulkan1'. Passing numeric '--device 0' causes an argument parser crash.\n"
                "2. Flash Attention Flag Syntax: '--flash-attn' requires an explicit parameter ('on', 'off', or 'auto'). Passing '--flash-attn \\' followed by another flag causes the subsequent flag to be swallowed as the flash-attn argument.\n"
                "3. SPIRV-Headers for Vulkan Build: Ubuntu 24.04 glslang/vulkan packages require the Khronos SPIRV-Headers cmake target. Installed via KhronosGroup/SPIRV-Headers git repository.\n"
                "4. Antigravity MCP Transport: Antigravity sends JSON-RPC HTTP POST requests directly without URL session query parameters. Built a Starlette universal router handling both HTTP POST and GET /sse routes.\n"
                "5. Systemd Restart Timeout: Restarting cluster-mcp.service while Antigravity has an open SSE connection takes ~60-90 seconds because uvicorn gracefully waits for the streaming connection to close."
            ),
            "metadata": {"category": "troubleshooting", "component": "vulkan_systemd_mcp"}
        },
        {
            "title": "Three-Tier Multi-Agent Collaboration Paradigm",
            "content": (
                "Operational Interaction Flow:\n"
                "1. Tier 1 (Antigravity Frontier Cloud): High-level multi-file architecture, comprehensive planning, user pair-programming, and complex cross-file refactoring.\n"
                "2. Tier 2 (Coordinator 14B on RX 6750 XT): Unrestricted local code generation, complex refactors, 24/7 background agents with zero token costs or rate limits.\n"
                "3. Tier 3 (Worker 3B on RX 6600 XT): Instant unit-test generation, schema validation, lint checks at 80+ t/s.\n"
                "4. Tier 4 (Vector Brain BGE + Qdrant): Hardware-accelerated persistent recall across sessions with 1024-dimensional semantic search."
            ),
            "metadata": {"category": "agent_architecture", "component": "collaboration"}
        },
        {
            "title": "Proxmox Datacenter 'home' Two-Node Infrastructure Topology",
            "content": (
                "Complete Cluster Topology across two 24/7 nodes in Proxmox Datacenter 'home':\n"
                "1. Node 'pve' (AI Compute & Vector Brain - Intel i7-12700K, 32GB RAM):\n"
                "   - VM 102 ('ubu' @ 192.168.1.105): Dual AMD GPUs (RX 6750 XT 12GB + RX 6600 XT 8GB).\n"
                "     * Coordinator 14B Qwen Coder (:8001)\n"
                "     * Worker 3B Qwen Coder (:8002)\n"
                "     * Embedder BGE-Large (:8003)\n"
                "     * MCP Bridge Starlette SSE (:8765)\n"
                "   - LXC 117 ('qdrant' @ 192.168.1.112:6333): 5 vector collections.\n"
                "2. Node 'bigserv' (Application, Media & Home Automation Hub):\n"
                "   - VM 103 ('haos-17.3' @ 192.168.1.82:8123): Home Assistant OS (lights, sensors, Nest Thermostat).\n"
                "   - VM 115 ('NAS'): Network Attached Storage.\n"
                "   - LXC Fleet: 100 (kavita), 101 (adguard), 104 (jellyfin), 105 (docker), 106 (ubuntu), 107 (immich), "
                "108 (freshrss), 109 (prowlarr), 110 (sonarr), 111 (radarr), 112 (lidarr), 113 (homepage), 114 (qbittorrent), "
                "116 (obsidian-live-sync), 119 (openwebui)."
            ),
            "metadata": {"category": "architecture", "component": "datacenter_topology"}
        }
    ]

    for mem in architectural_memories:
        meta = {
            "project": "pve-dual-gpu-cluster",
            "title": mem["title"],
            **mem["metadata"],
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")
        }
        point_id = upsert_point("agent_memories", f"### {mem['title']}\n{mem['content']}", meta)
        print(f"  [SAVED] {mem['title']} (ID: {point_id})")
        total_indexed += 1

    # 3. Back up session deployment milestones into 'session_transcripts'
    print("\n[Phase 3] Saving Deployment History into 'session_transcripts'...")
    session_milestones = [
        {
            "session_title": "PVE Dual-GPU Cluster Initial Build & Verification",
            "summary": (
                "Successfully transitioned dual asymmetric AMD GPUs (RX 6750 XT 12GB + RX 6600 XT 8GB) "
                "from cross-device tensor splitting to dedicated model roles. Built Vulkan llama.cpp from source, "
                "downloaded Qwen2.5-Coder-14B-abliterated, Qwen2.5-Coder-3B, and BGE-Large-EN-v1.5. Configured 4 systemd "
                "services on Ubuntu VM 192.168.1.105, initialized Qdrant vector memory on 192.168.1.112, and integrated "
                "with Antigravity via SSE MCP bridge on port 8765. All 5 tools live-verified with sub-millisecond latencies."
            ),
            "metadata": {"phase": "deployment_milestone", "status": "verified"}
        },
        {
            "session_title": "Companion Architecture, EasyDash PWA & Home Assistant Integration",
            "summary": (
                "Established permanent companion charter in COMPANION_MANIFESTO.md. Built comprehensive Google Nest "
                "thermostat integration runbook using burner account and local Matter protocols. Extended Qdrant to 5 "
                "collections (added companion_profile and home_automation_registry). Refined EasyDash PWA with web push "
                "notifications, cluster harness switcher, and Qdrant memory viewer over Tailscale."
            ),
            "metadata": {"phase": "companion_evolution", "status": "verified"}
        },
        {
            "session_title": "StoneSage Frontier Cockpit & Network Device Registry Integration",
            "summary": (
                "Implemented StoneSage, a complete frontier-level AI IDE replacement and cockpit on port 8080. "
                "Integrated 10 core views: AI Harness (multi-provider, tool calling, memory recall), Cockpit (service statuses), "
                "Proxmox cluster manager, Home Assistant control, Append-only Obsidian vault backup, and System monitor. "
                "Ingested complete static DHCP network device registry with 23 hardware devices, MAC addresses, "
                "and container-specific ports. Hardened start.bat against duplicate process port collisions."
            ),
            "metadata": {"phase": "stonesage_deployment", "status": "verified"}
        }
    ]

    for sm in session_milestones:
        meta = {
            "project": "pve-dual-gpu-cluster",
            "session_title": sm["session_title"],
            **sm["metadata"],
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")
        }
        point_id = upsert_point("session_transcripts", f"### {sm['session_title']}\n{sm['summary']}", meta)
        print(f"  [SAVED] {sm['session_title']} (ID: {point_id})")
        total_indexed += 1

    # 4. Ingest user profile and companion directives into 'companion_profile'
    print("\n[Phase 4] Saving Persona Directives into 'companion_profile'...")
    companion_directives = [
        {
            "title": "Companion Persona & Communication Directives",
            "content": (
                "User: John.\n"
                "Tone & Style: Sharp, highly technical, authentic, zero boilerplate, proactive.\n"
                "Role: Permanent homelab companion, systems engineer, pair-programmer, and ambient life copilot.\n"
                "Continuity: Never start as a blank slate. Recall context from Qdrant upon session initialization.\n"
                "Remote Access: Accessible via Tailscale across desktop and Android mobile (StoneSage cockpit)."
            ),
            "metadata": {"category": "persona", "type": "communication_style"}
        },
        {
            "title": "Tiered Intelligence Execution Protocol",
            "content": (
                "Task Routing:\n"
                "1. Frontier Cloud (Antigravity): Multi-file architecture, planning, deep debugging, complex reasoning.\n"
                "2. Local Coordinator (14B @ :8001): 24/7 unrestricted coding, private documents, heavy refactoring.\n"
                "3. Local Worker (3B @ :8002): Fast tests, JSON schemas, docstrings, Home Assistant NLP parsing at 80+ t/s.\n"
                "4. Vector Brain (Qdrant @ :6333): 1024-d BGE persistent memory across 5 collections."
            ),
            "metadata": {"category": "orchestration", "type": "task_routing"}
        }
    ]

    for cd in companion_directives:
        meta = {
            "project": "pve-dual-gpu-cluster",
            "title": cd["title"],
            **cd["metadata"],
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")
        }
        point_id = upsert_point("companion_profile", f"### {cd['title']}\n{cd['content']}", meta)
        print(f"  [SAVED] {cd['title']} (ID: {point_id})")
        total_indexed += 1

    # 5. Ingest smart home metadata into 'home_automation_registry'
    print("\n[Phase 5] Saving Home Devices & Endpoints into 'home_automation_registry'...")
    ha_registry_items = [
        {
            "title": "Home Assistant Instance & Network Specs",
            "content": (
                "Home Assistant URL: http://192.168.1.82:8123\n"
                "Integration: REST API via bearer token (HASS_TOKEN).\n"
                "Supported Domains: climate, light, switch, sensor, scene, automation.\n"
                "Delegation Tool: delegate_home_automation parses natural language to domain/service calls using 3B worker."
            ),
            "metadata": {"category": "home_assistant", "type": "network_config"}
        },
        {
            "title": "Google Nest Thermostat Integration Architecture",
            "content": (
                "Device: Google Nest Thermostat.\n"
                "Integration Paths:\n"
                "1. Matter Protocol (Local, Zero-Fee): Available for 2020 Nest Thermostat (model G4CVZ) and 4th Gen Learning Thermostat. Direct local Wi-Fi pairing via numeric code.\n"
                "2. Google SDM Cloud API (Burner Gmail): Available for 3rd Gen Learning and Thermostat E. Uses burner Gmail in Google Cloud Console and Nest Device Access Console to avoid Google Family/Workspace OAuth restrictions.\n"
                "Target Entities: climate.<thermostat>, sensor.<thermostat>_temperature, sensor.<thermostat>_humidity."
            ),
            "metadata": {"category": "nest_thermostat", "type": "device_spec"}
        },
        {
            "title": "Homelab Static IP & IoT Hardware Device Map",
            "content": (
                "Complete Hardware Device & Static DHCP Mapping:\n"
                "- Hypervisors: pve (192.168.1.229), bigserv (192.168.1.82)\n"
                "- AI Stack: ubu VM 102 (192.168.1.105), qdrant LXC 117 (192.168.1.112:6333)\n"
                "- Media & Automation LXCs: kavita (192.168.1.124:5000), jellyfin (192.168.1.180:8096), immich (192.168.1.238:9000), "
                "freshrss (192.168.1.212:80), qbittorrent (192.168.1.169:8090), flaresolverr (192.168.1.159:8191), docker (192.168.1.204:9443)\n"
                "- Smart Home Devices: Nest Thermostat (192.168.1.62, MAC B4-23-A2-1B-9A-6E), KP125 Smart Energy Plug (192.168.1.109:9999, MAC 10-27-F5-8F-36-73), "
                "GE Plugs (192.168.1.17, 192.168.1.111, 192.168.1.143), LG Smart Dryer (192.168.1.56), Petkit T4 (192.168.1.10)\n"
                "- Endpoints: Samsung Galaxy S25 Ultra (192.168.1.178), Laptop (192.168.1.110)\n"
                "- Network Hardware: Switch/Bridge (192.168.1.7), AP/Router (192.168.1.217)"
            ),
            "metadata": {"category": "network_devices", "type": "device_registry"}
        }
    ]

    for item in ha_registry_items:
        meta = {
            "project": "pve-dual-gpu-cluster",
            "title": item["title"],
            **item["metadata"],
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")
        }
        point_id = upsert_point("home_automation_registry", f"### {item['title']}\n{item['content']}", meta)
        print(f"  [SAVED] {item['title']} (ID: {point_id})")
        total_indexed += 1

    print("\n" + "=" * 65)
    print(f"  Backup Complete! Total points saved to Qdrant: {total_indexed}")
    print("=" * 65)

    # Verification Query
    print("\n[Verification] Testing Semantic Retrieval from Qdrant Brain...")
    test_query = "What models and hardware are running on the cluster?"
    vec = get_embedding(test_query)
    search_payload = {"vector": vec, "limit": 2, "with_payload": True}
    res = _http_post(f"{QDRANT_URL}/collections/agent_memories/points/search", search_payload, timeout=10)
    hits = res.get("result", [])
    for idx, hit in enumerate(hits):
        score = hit.get("score", 0)
        title = hit.get("payload", {}).get("metadata", {}).get("title", "Unknown")
        print(f"  Top Match {idx+1} (Score: {score:.4f}): {title}")

if __name__ == "__main__":
    backup_project()

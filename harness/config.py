"""
Dynamic Fleet Configuration & Multi-Node Network Registry.
Zero hardcoded model strings: all models, quants, and context lengths are polled live.
"""

import os
import json
import logging
import urllib.request
import urllib.error
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field

logger = logging.getLogger("Harness.Config")

@dataclass
class NodeEndpoint:
    node_id: str
    name: str
    base_url: str
    api_type: str = "openai"  # "openai", "llama-server", "lm-studio", "mcp"
    slots: int = 1
    device_name: str = "Unknown Device"
    total_memory_mb: int = 0
    role: str = "worker"
    is_roaming: bool = False
    active_model: Optional[str] = None
    active_context: int = 4096
    status: str = "unknown"

class FleetConfig:
    def __init__(self):
        # Base fleet endpoints
        self.coordinator_url = os.environ.get("COORDINATOR_URL", "http://192.168.1.105:8001/v1")
        self.worker_url = os.environ.get("WORKER_URL", "http://192.168.1.105:8002/v1")
        self.embedder_url = os.environ.get("EMBEDDER_URL", "http://192.168.1.105:8003/v1")
        self.edge_node_url = os.environ.get(
            "EDGE_NODE_URL",
            os.environ.get("EDGE_URL", os.environ.get("ALLY_EXTREME_URL", os.environ.get("ALLY_URL", "http://192.168.1.213:1234/v1")))
        )
        self.ally_extreme_url = self.edge_node_url  # Backward-compatible alias
        self.ally_x_url = self.edge_node_url        # Backward-compatible alias
        
        # Storage & Cluster Services
        self.valkey_host = os.environ.get("VALKEY_HOST", "192.168.1.105")
        self.valkey_port = int(os.environ.get("VALKEY_PORT", 6379))
        self.qdrant_url = os.environ.get("QDRANT_URL", "http://192.168.1.112:6333")
        self.couchdb_url = os.environ.get("COUCHDB_URL", "http://192.168.1.230:5984")
        self.postgres_url = os.environ.get("POSTGRES_URL", "")
        
        # Cluster Bridges & WebSockets
        self.assembly_ws = os.environ.get("ASSEMBLY_WS", "ws://192.168.1.105:8766/ws")
        self.assembly_http = os.environ.get("ASSEMBLY_HTTP", "http://192.168.1.105:8766")
        self.cluster_mcp_url = os.environ.get("CLUSTER_MCP_URL", "http://192.168.1.105:8765")
        
        # Proxmox Fleet Services
        self.proxmox_vip = os.environ.get("PROXMOX_VIP", "https://192.168.1.245:8006")
        self.hass_url = os.environ.get("HASS_URL", "http://192.168.1.82:8123")
        self.immich_url = os.environ.get("IMMICH_URL", "http://192.168.1.238:9000")
        self.freshrss_url = os.environ.get("FRESHRSS_URL", "http://192.168.1.212:80")
        self.kavita_url = os.environ.get("KAVITA_URL", "http://192.168.1.124:5000")
        self.voice_whisper_url = os.environ.get("VOICE_WHISPER_URL", "http://192.168.1.121:8200")
        self.voice_kokoro_url = os.environ.get("VOICE_KOKORO_URL", "http://192.168.1.121:8300")
        
        # Frontier Model Designation
        self.frontier_provider = "antigravity"
        self.frontier_model = "gemini-3.8-flash"

        # Registered Node Fleet (Device-Agnostic Endpoints)
        class NodeDict(dict):
            """Dictionary that collapses aliases to prevent duplicate fleet rows while preserving lookup compatibility."""
            ALIASES = {
                "node2_edge": "node2_ally_x",
                "node2_ally_extreme": "node2_ally_x",
            }

            def __getitem__(self, key):
                resolved = self.ALIASES.get(key, key)
                return super().__getitem__(resolved)

            def get(self, key, default=None):
                resolved = self.ALIASES.get(key, key)
                return super().get(resolved, default)

            def __contains__(self, key):
                resolved = self.ALIASES.get(key, key)
                return super().__contains__(resolved)

        self.nodes: Dict[str, NodeEndpoint] = NodeDict({
            "node1_primary": NodeEndpoint(
                node_id="node1_primary",
                name="Compute Node 1 Primary (:8001)",
                base_url=self.coordinator_url,
                role="coordinator",
                total_memory_mb=12288,
                slots=1,
                device_name="Compute Accelerator 0",
            ),
            "node1_secondary": NodeEndpoint(
                node_id="node1_secondary",
                name="Compute Node 1 Secondary (:8002)",
                base_url=self.worker_url,
                role="worker",
                total_memory_mb=8192,
                slots=2,
                device_name="Compute Accelerator 1",
            ),
            "vm102_dual": NodeEndpoint(
                node_id="vm102_dual",
                name="Compute Node 1 Spanned Array (:8001+:8002)",
                base_url=self.coordinator_url,
                role="dual_gpu",
                total_memory_mb=20480,
                slots=1,
                device_name="Spanned Multi-Accelerator Array",
            ),
            "node2_ally_x": NodeEndpoint(
                node_id="node2_ally_x",
                name="ROG Ally X Handheld Edge (192.168.1.213)",
                base_url=self.edge_node_url,
                role="edge_pool",
                total_memory_mb=24576,
                slots=2,
                is_roaming=True,
                device_name="ROG Ally X Handheld (Z1 Extreme / 24GB Unified LPDDR5X)",
            ),
            "local_workstation": NodeEndpoint(
                node_id="local_workstation",
                name="Host Workstation Desktop (192.168.1.132)",
                base_url=os.environ.get("WORKSTATION_URL", "http://192.168.1.132:8088/v1"),
                role="workstation",
                total_memory_mb=32768,
                slots=1,
                device_name="Windows Workstation Host",
            ),
        })
        self.active_node_id: str = "node1_primary"

    def set_active_node(self, node_id: str) -> bool:
        if node_id in self.nodes:
            self.active_node_id = node_id
            return True
        return False

    def get_active_node(self) -> NodeEndpoint:
        return self.nodes.get(self.active_node_id, self.nodes["node1_primary"])

    def get_active_node_id(self) -> str:
        return self.active_node_id

    def poll_node_models(self) -> Dict[str, Any]:
        """Dynamically queries each node's endpoint in parallel to retrieve loaded models and health."""
        import concurrent.futures
        import socket

        def _probe_tcp(host: str, port: int, timeout: float = 0.5) -> bool:
            try:
                with socket.create_connection((host, port), timeout=timeout):
                    return True
            except Exception:
                return False

        def _poll_single(item):
            nid, node = item
            parsed_u = urllib.parse.urlparse(node.base_url)
            host = parsed_u.hostname or "127.0.0.1"
            port = parsed_u.port or (443 if parsed_u.scheme == "https" else 80)

            # Pre-probe port to avoid hanging on offline hosts
            if not _probe_tcp(host, port, timeout=0.6):
                node.status = "offline"
                node.active_model = None
                return nid, {"status": "offline", "error": f"Port {port} unreachable on {host}"}

            # 1. First attempt LM Studio native API (/api/v1/models)
            lm_studio_api = f"{parsed_u.scheme}://{host}:{port}/api/v1/models"
            try:
                req = urllib.request.Request(lm_studio_api, headers={"User-Agent": "Harness-Poller"})
                with urllib.request.urlopen(req, timeout=1.5) as resp:
                    if resp.status == 200:
                        data = json.loads(resp.read().decode("utf-8"))
                        raw_models = data.get("models", [])
                        loaded = [m for m in raw_models if m.get("loaded_instances")]
                        if loaded:
                            m = loaded[0]
                            m_name = m.get("key") or m.get("display_name", "Unknown")
                            inst = m.get("loaded_instances", [])[0]
                            ctx = inst.get("config", {}).get("context_length", m.get("max_context_length", 32768))
                            node.active_model = m_name
                            node.active_context = ctx
                            node.status = "online"
                            return nid, {"status": "online", "model": m_name, "context": ctx, "models": raw_models, "api": "lm-studio"}
                        elif raw_models:
                            node.status = "online (no model loaded)"
                            node.active_model = None
                            return nid, {"status": "idle", "model": None, "available_count": len(raw_models), "api": "lm-studio"}
            except Exception:
                pass

            # 2. Attempt llama-server /props endpoint
            props_endpoint = f"{parsed_u.scheme}://{host}:{port}/props"
            try:
                req = urllib.request.Request(props_endpoint, headers={"User-Agent": "Harness-Poller"})
                with urllib.request.urlopen(req, timeout=1.2) as resp:
                    if resp.status == 200:
                        data = json.loads(resp.read().decode("utf-8"))
                        m_path = data.get("model_path") or ""
                        m_name = data.get("model_alias") or (m_path.split("/")[-1] if m_path else "Unknown")
                        ctx = data.get("default_generation_settings", {}).get("n_ctx", 8192)
                        node.active_model = m_name
                        node.active_context = ctx
                        node.slots = data.get("total_slots", node.slots)
                        node.status = "online"
                        return nid, {"status": "online", "model": m_name, "context": ctx, "slots": node.slots, "path": m_path, "api": "llama-server"}
            except Exception:
                pass

            # 3. Standard OpenAI /v1/models fallback
            models_endpoint = f"{node.base_url.rstrip('/')}/models"
            try:
                req = urllib.request.Request(models_endpoint, headers={"User-Agent": "Harness-Poller"})
                with urllib.request.urlopen(req, timeout=1.2) as resp:
                    if resp.status == 200:
                        data = json.loads(resp.read().decode("utf-8"))
                        model_list = data.get("data", [])
                        if model_list:
                            first_model = model_list[0].get("id", "Unknown")
                            node.active_model = first_model
                            node.status = "online"
                            return nid, {"status": "online", "model": first_model, "models": model_list, "api": "openai"}
                        else:
                            node.status = "online (no models loaded)"
                            node.active_model = None
                            return nid, {"status": "empty", "model": None}
            except Exception as e:
                node.status = "offline"
                return nid, {"status": "offline", "error": str(e)}

            node.status = "online"
            return nid, {"status": "online", "model": node.active_model}

        results = {}
        with concurrent.futures.ThreadPoolExecutor(max_workers=max(len(self.nodes), 1)) as executor:
            future_to_node = {executor.submit(_poll_single, item): item[0] for item in self.nodes.items()}
            for future in concurrent.futures.as_completed(future_to_node):
                try:
                    nid, res = future.result()
                    results[nid] = res
                except Exception as ex:
                    nid = future_to_node[future]
                    results[nid] = {"status": "offline", "error": str(ex)}

        return results

fleet_config = FleetConfig()


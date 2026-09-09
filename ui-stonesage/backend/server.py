#!/usr/bin/env python3
"""
StoneSage Homelab Command Center & AI Cognitive Cockpit
Replacement for EasyDash with Sage & Stone UI, Proxmox VE integration,
Home Assistant climate/lighting control, zero-delete Obsidian vault, and multi-model AI harness.

Zero-dependency: 100% Python 3 standard library.
"""

import os
import sys
import re

# Ensure UTF-8 output encoding for Windows terminals
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')
if hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8')

import json
import time
from datetime import datetime, timezone
try:
    from zoneinfo import ZoneInfo
    EASTERN_TZ = ZoneInfo("America/New_York")
except Exception:
    import datetime as dt
    EASTERN_TZ = dt.timezone(dt.timedelta(hours=-5))

def get_eastern_time_str() -> str:
    try:
        return datetime.now(EASTERN_TZ).strftime("%I:%M:%S %p EST")
    except Exception:
        return time.strftime("%H:%M:%S")

import mimetypes
import http.server
import ssl
import urllib.request
import urllib.parse
import urllib.error
import traceback
import subprocess
import threading
import difflib
import base64
import hashlib
from concurrent.futures import ThreadPoolExecutor
from typing import Dict, Any, List

subagent_registry: Dict[str, Any] = {}

def deep_update(target: dict, src: dict) -> dict:
    for k, v in src.items():
        if isinstance(v, dict) and k in target and isinstance(target[k], dict):
            deep_update(target[k], v)
        else:
            target[k] = v
    return target

# Local imports
BACKEND_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR = os.path.dirname(BACKEND_DIR)
FRONTEND_DIR = os.path.join(ROOT_DIR, "frontend")
CONFIG_FILE = os.path.join(BACKEND_DIR, "config.json")
VAULT_DIR = os.path.join(ROOT_DIR, "vault_backup")
UPLOADS_DIR = os.path.join(ROOT_DIR, "uploads")
WORKSPACE_ROOT = os.path.abspath(os.path.dirname(ROOT_DIR))
os.makedirs(UPLOADS_DIR, exist_ok=True)

sys.path.insert(0, BACKEND_DIR)
from proxmox_client import ProxmoxClient
from hass_client import HomeAssistantClient
from obsidian_vault import ObsidianVault
from cluster_client import ClusterClient
from immich_client import ImmichClient
from obsidian_ingestor import ObsidianIngestor
from couchdb_client import CouchDBClient
from stm_engine import ShortTermMemoryEngine
from dataset_compiler import DatasetCompiler

mimetypes.add_type("application/manifest+json", ".webmanifest")
mimetypes.add_type("application/javascript", ".js")
mimetypes.add_type("image/svg+xml", ".svg")
mimetypes.add_type("application/vnd.android.package-archive", ".apk")

def load_config() -> Dict[str, Any]:
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {}

def save_config(cfg: Dict[str, Any]):
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(cfg, f, indent=2)

config = load_config()
proxmox = ProxmoxClient(config.get("proxmox", {}))
hass = HomeAssistantClient(
    config.get("homeassistant", {}).get("url", "http://127.0.0.1:8123"),
    config.get("homeassistant", {}).get("token", "")
)
vault = ObsidianVault(os.path.join(ROOT_DIR, config.get("obsidian", {}).get("vault_path", "vault_backup")))
cluster = ClusterClient(config)
immich = ImmichClient(config.get("immich", {}), UPLOADS_DIR)
obsidian_ingestor = ObsidianIngestor(config)
couchdb = CouchDBClient(config.get("couchdb", {}))
stm = ShortTermMemoryEngine(config)
dataset_compiler = DatasetCompiler(config)

def extract_tool_call(text: str):
    """Extract tool name and arguments from model content (supporting XML-style, markdown codeblocks, or raw JSON)."""
    if not text:
        return None, None
    cleaned = text.strip()
    m = re.search(r"<(?:tools|function-calls|tool_call)>(.*?)</(?:tools|function-calls|tool_call)>", cleaned, re.DOTALL)
    if m:
        cleaned = m.group(1).strip()
    else:
        m2 = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", cleaned, re.DOTALL)
        if m2:
            cleaned = m2.group(1).strip()
    try:
        data = json.loads(cleaned)
        if isinstance(data, dict):
            if "name" in data and "arguments" in data:
                return data["name"], data["arguments"]
            if "function" in data:
                fn = data["function"]
                if isinstance(fn, dict) and "name" in fn:
                    return fn["name"], fn.get("arguments", {})
    except Exception:
        m_json = re.search(r'(\{\s*"name"\s*:\s*"[^"]+"\s*,\s*"arguments"\s*:\s*\{.*?\}\s*\})', text, re.DOTALL)
        if m_json:
            try:
                data = json.loads(m_json.group(1))
                return data["name"], data["arguments"]
            except Exception:
                pass
    return None, None

def get_service_execstart(service_name: str) -> str:
    try:
        cmd = ["ssh", "-o", "BatchMode=yes", "-o", "StrictHostKeyChecking=no", f"{os.environ.get('CLUSTER_USER', 'user')}@127.0.0.1",
               f"grep '^ExecStart=' /etc/systemd/system/{service_name}"]
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=8)
        if res.returncode == 0:
            return res.stdout.strip().replace("ExecStart=", "")
    except Exception:
        pass
    return ""

def parse_llama_flags(exec_start: str) -> Dict[str, Any]:
    flags: Dict[str, Any] = {
        "model": "",
        "n_ctx": 8192,
        "n_gpu_layers": 99,
        "flash_attn": "on",
        "cache_type_k": "q4_0",
        "cache_type_v": "q4_0",
        "batch_size": 2048,
        "ubatch_size": 512,
        "threads": 8,
        "threads_batch": 8,
        "parallel": 4,
        "device": "Vulkan0",
        "defrag_thold": 0.1,
        "mlock": False,
        "no_mmap": False,
        "cont_batching": False,
        "custom_flags": ""
    }
    if not exec_start:
        return flags
    tokens = exec_start.split()
    recognized = set()
    i = 0
    while i < len(tokens):
        tok = tokens[i]
        if tok == "--model" and i + 1 < len(tokens):
            flags["model"] = tokens[i+1]
            recognized.update([i, i+1])
            i += 2
        elif tok in ("-c", "--ctx-size") and i + 1 < len(tokens):
            try: flags["n_ctx"] = int(tokens[i+1])
            except ValueError: pass
            recognized.update([i, i+1])
            i += 2
        elif tok in ("-ngl", "--gpu-layers") and i + 1 < len(tokens):
            try: flags["n_gpu_layers"] = int(tokens[i+1])
            except ValueError: pass
            recognized.update([i, i+1])
            i += 2
        elif tok == "--flash-attn" and i + 1 < len(tokens):
            flags["flash_attn"] = tokens[i+1]
            recognized.update([i, i+1])
            i += 2
        elif tok in ("-ctk", "--cache-type-k") and i + 1 < len(tokens):
            flags["cache_type_k"] = tokens[i+1]
            recognized.update([i, i+1])
            i += 2
        elif tok in ("-ctv", "--cache-type-v") and i + 1 < len(tokens):
            flags["cache_type_v"] = tokens[i+1]
            recognized.update([i, i+1])
            i += 2
        elif tok in ("-b", "--batch-size") and i + 1 < len(tokens):
            try: flags["batch_size"] = int(tokens[i+1])
            except ValueError: pass
            recognized.update([i, i+1])
            i += 2
        elif tok in ("-ub", "--ubatch-size") and i + 1 < len(tokens):
            try: flags["ubatch_size"] = int(tokens[i+1])
            except ValueError: pass
            recognized.update([i, i+1])
            i += 2
        elif tok in ("-t", "--threads") and i + 1 < len(tokens):
            try: flags["threads"] = int(tokens[i+1])
            except ValueError: pass
            recognized.update([i, i+1])
            i += 2
        elif tok in ("-tb", "--threads-batch") and i + 1 < len(tokens):
            try: flags["threads_batch"] = int(tokens[i+1])
            except ValueError: pass
            recognized.update([i, i+1])
            i += 2
        elif tok in ("-np", "--parallel") and i + 1 < len(tokens):
            try: flags["parallel"] = int(tokens[i+1])
            except ValueError: pass
            recognized.update([i, i+1])
            i += 2
        elif tok == "--device" and i + 1 < len(tokens):
            flags["device"] = tokens[i+1]
            recognized.update([i, i+1])
            i += 2
        elif tok == "--defrag-thold" and i + 1 < len(tokens):
            try: flags["defrag_thold"] = float(tokens[i+1])
            except ValueError: pass
            recognized.update([i, i+1])
            i += 2
        elif tok == "--mlock":
            flags["mlock"] = True
            recognized.add(i)
            i += 1
        elif tok == "--no-mmap":
            flags["no_mmap"] = True
            recognized.add(i)
            i += 1
        elif tok == "--cont-batching":
            flags["cont_batching"] = True
            recognized.add(i)
            i += 1
        elif tok in ("--host", "--port", "--alias", "/usr/local/bin/llama-server"):
            recognized.add(i)
            if tok in ("--host", "--port", "--alias") and i + 1 < len(tokens):
                recognized.add(i + 1)
                i += 1
            i += 1
        else:
            i += 1
    
    custom = [tokens[j] for j in range(len(tokens)) if j not in recognized and not tokens[j].startswith("/usr/local/bin")]
    flags["custom_flags"] = " ".join(custom).strip()
    return flags

def apply_llama_parameters(service_name: str, port: int, alias: str, params: Dict[str, Any]) -> tuple:
    try:
        get_cmd = ["ssh", "-o", "BatchMode=yes", "-o", "StrictHostKeyChecking=no", f"{os.environ.get('CLUSTER_USER', 'user')}@127.0.0.1",
                   f"cat /etc/systemd/system/{service_name}"]
        res = subprocess.run(get_cmd, capture_output=True, text=True, timeout=10)
        if res.returncode != 0:
            return False, f"Could not read existing service file: {res.stderr}"
        current_content = res.stdout

        current_exec = ""
        for line in current_content.splitlines():
            if line.startswith("ExecStart="):
                current_exec = line.replace("ExecStart=", "").strip()
                break
        current_flags = parse_llama_flags(current_exec)
        model_path = params.get("model") or current_flags.get("model") or "/opt/models/ornith-1.5-9b-coordinator-q8_0.gguf"

        n_ctx = int(params.get("n_ctx", current_flags.get("n_ctx", 8192)))
        n_gpu_layers = int(params.get("n_gpu_layers", current_flags.get("n_gpu_layers", 99)))
        flash_attn = params.get("flash_attn", current_flags.get("flash_attn", "on"))
        cache_type_k = params.get("cache_type_k", current_flags.get("cache_type_k", "q4_0"))
        cache_type_v = params.get("cache_type_v", current_flags.get("cache_type_v", "q4_0"))
        device = params.get("device", current_flags.get("device", "Vulkan0" if port == 8001 else "Vulkan1"))
        
        cmd_parts = [
            "/usr/local/bin/llama-server",
            "--model", model_path,
            "--host", "0.0.0.0",
            "--port", str(port),
            "--device", device,
            "-ngl", str(n_gpu_layers),
            "-c", str(n_ctx),
            "--flash-attn", flash_attn,
            "-ctk", cache_type_k,
            "-ctv", cache_type_v,
            "--alias", alias,
            "--metrics"
        ]
        if "batch_size" in params and params["batch_size"]:
            cmd_parts.extend(["-b", str(params["batch_size"])])
        if "ubatch_size" in params and params["ubatch_size"]:
            cmd_parts.extend(["-ub", str(params["ubatch_size"])])
        if "threads" in params and params["threads"]:
            cmd_parts.extend(["-t", str(params["threads"])])
        if "threads_batch" in params and params["threads_batch"]:
            cmd_parts.extend(["-tb", str(params["threads_batch"])])
        if "parallel" in params and params["parallel"]:
            cmd_parts.extend(["-np", str(params["parallel"])])
        if "defrag_thold" in params and params["defrag_thold"] is not None:
            cmd_parts.extend(["--defrag-thold", str(params["defrag_thold"])])
        if params.get("mlock"):
            cmd_parts.append("--mlock")
        if params.get("no_mmap"):
            cmd_parts.append("--no-mmap")
        if params.get("cont_batching"):
            cmd_parts.append("--cont-batching")
        if params.get("custom_flags"):
            cmd_parts.append(str(params["custom_flags"]).strip())

        new_exec_start = " ".join(cmd_parts)

        new_lines = []
        for line in current_content.splitlines():
            if line.startswith("ExecStart="):
                new_lines.append(f"ExecStart={new_exec_start}")
            elif line.startswith("Description="):
                clean_desc = re.sub(r"RX\s*6[76]50\s*XT", "Vulkan Accelerator", line)
                new_lines.append(clean_desc)
            else:
                new_lines.append(line)
        new_content = "\n".join(new_lines) + "\n"

        b64_new = base64.b64encode(new_content.encode("utf-8")).decode("ascii")
        remote_script = f"""
set -e
sudo cp /etc/systemd/system/{service_name} /etc/systemd/system/{service_name}.bak
echo '{b64_new}' | base64 -d | sudo tee /etc/systemd/system/{service_name} > /dev/null
sudo systemctl daemon-reload
sudo systemctl restart {service_name}
"""
        ssh_apply = ["ssh", "-o", "BatchMode=yes", "-o", "StrictHostKeyChecking=no", f"{os.environ.get('CLUSTER_USER', 'user')}@127.0.0.1",
                     "bash -s"]
        res_apply = subprocess.run(ssh_apply, input=remote_script, text=True, capture_output=True, timeout=15)
        if res_apply.returncode != 0:
            return False, f"Failed to restart systemd service: {res_apply.stderr}"

        health_ok = False
        health_url = f"http://127.0.0.1:{port}/health"
        for _ in range(15):
            time.sleep(2)
            try:
                req = urllib.request.Request(health_url)
                with urllib.request.urlopen(req, timeout=2) as resp:
                    h_data = json.loads(resp.read().decode("utf-8"))
                    if h_data.get("status") == "ok":
                        health_ok = True
                        break
            except Exception:
                pass

        if health_ok:
            return True, f"{service_name} reconfigured and healthy at :{port}!"
        else:
            rollback_script = f"""
sudo cp /etc/systemd/system/{service_name}.bak /etc/systemd/system/{service_name}
sudo systemctl daemon-reload
sudo systemctl restart {service_name}
"""
            subprocess.run(ssh_apply, input=rollback_script, text=True, capture_output=True, timeout=15)
            return False, "Health check failed or timed out after applying parameters. Automatically rolled back to prior working service configuration."
    except Exception as e:
        return False, str(e)

def is_moe_active() -> bool:
    try:
        req = urllib.request.Request("http://127.0.0.1:8001/v1/models")
        with urllib.request.urlopen(req, timeout=1.5) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            for m in data.get("data", []):
                if "moe" in m.get("id", "").lower() or "ornith" in m.get("id", "").lower():
                    return True
    except Exception:
        pass
    return False

def get_harness_parameters(harness: str) -> Dict[str, Any]:
    cfg = load_config()
    harness_settings = cfg.get("harness_settings", {})
    
    if harness in ("llama_coordinator", "coordinator"):
        exec_start = get_service_execstart("llama-coordinator.service")
        flags = parse_llama_flags(exec_start)
        props = {}
        try:
            req = urllib.request.Request("http://127.0.0.1:8001/props")
            with urllib.request.urlopen(req, timeout=2) as resp:
                props = json.loads(resp.read().decode("utf-8"))
        except Exception:
            pass
        gen_params = props.get("default_generation_settings", {}).get("params", {})
        saved_params = harness_settings.get("llama_coordinator", {})
        
        sampling = {
            "temperature": saved_params.get("temperature", round(float(gen_params.get("temperature", 0.70)), 2)),
            "min_p": saved_params.get("min_p", round(float(gen_params.get("min_p", 0.06)), 2)),
            "top_p": saved_params.get("top_p", round(float(gen_params.get("top_p", 0.95)), 2)),
            "top_k": saved_params.get("top_k", int(gen_params.get("top_k", 40))),
            "presence_penalty": saved_params.get("presence_penalty", round(float(gen_params.get("presence_penalty", 0.20)), 2)),
            "frequency_penalty": saved_params.get("frequency_penalty", round(float(gen_params.get("frequency_penalty", 0.0)), 2)),
            "repeat_penalty": saved_params.get("repeat_penalty", round(float(gen_params.get("repeat_penalty", 1.0)), 2)),
            "repeat_last_n": saved_params.get("repeat_last_n", int(gen_params.get("repeat_last_n", 64))),
            "mirostat": saved_params.get("mirostat", int(gen_params.get("mirostat", 0))),
            "mirostat_tau": saved_params.get("mirostat_tau", round(float(gen_params.get("mirostat_tau", 5.0)), 2)),
            "mirostat_eta": saved_params.get("mirostat_eta", round(float(gen_params.get("mirostat_eta", 0.10)), 2))
        }

        return {
            "harness_id": "llama_coordinator",
            "name": "llama.cpp Primary Coordinator (:8001)",
            "role": "Primary Compute Accelerator",
            "device": flags.get("device", "Vulkan0"),
            "model_path": flags.get("model", ""),
            "model_alias": props.get("model_alias", "coordinator"),
            "server_params": {
                "n_ctx": flags.get("n_ctx", 8192),
                "n_gpu_layers": flags.get("n_gpu_layers", 99),
                "flash_attn": flags.get("flash_attn", "on"),
                "cache_type_k": flags.get("cache_type_k", "q4_0"),
                "cache_type_v": flags.get("cache_type_v", "q4_0"),
                "batch_size": flags.get("batch_size", 2048),
                "ubatch_size": flags.get("ubatch_size", 512),
                "threads": flags.get("threads", 8),
                "threads_batch": flags.get("threads_batch", 8),
                "parallel": flags.get("parallel", 4),
                "defrag_thold": flags.get("defrag_thold", 0.1),
                "mlock": flags.get("mlock", False),
                "no_mmap": flags.get("no_mmap", False),
                "cont_batching": flags.get("cont_batching", False),
                "custom_flags": flags.get("custom_flags", "")
            },
            "sampling_params": sampling,
            "options": {
                "flash_attn": ["on", "off", "auto"],
                "cache_types": ["q4_0", "q8_0", "f16", "q4_1", "q5_0"],
                "devices": ["Vulkan0", "Vulkan1", "CUDA0", "CPU"],
                "mirostat_modes": [0, 1, 2]
            }
        }
    elif harness in ("llama_worker", "worker"):
        exec_start = get_service_execstart("llama-worker.service")
        flags = parse_llama_flags(exec_start)
        props = {}
        try:
            req = urllib.request.Request("http://127.0.0.1:8002/props")
            with urllib.request.urlopen(req, timeout=2) as resp:
                props = json.loads(resp.read().decode("utf-8"))
        except Exception:
            pass
        gen_params = props.get("default_generation_settings", {}).get("params", {})
        saved_params = harness_settings.get("llama_worker", {})
        
        sampling = {
            "temperature": saved_params.get("temperature", round(float(gen_params.get("temperature", 0.65)), 2)),
            "min_p": saved_params.get("min_p", round(float(gen_params.get("min_p", 0.06)), 2)),
            "top_p": saved_params.get("top_p", round(float(gen_params.get("top_p", 0.95)), 2)),
            "top_k": saved_params.get("top_k", int(gen_params.get("top_k", 40))),
            "presence_penalty": saved_params.get("presence_penalty", round(float(gen_params.get("presence_penalty", 0.20)), 2)),
            "frequency_penalty": saved_params.get("frequency_penalty", round(float(gen_params.get("frequency_penalty", 0.0)), 2)),
            "repeat_penalty": saved_params.get("repeat_penalty", round(float(gen_params.get("repeat_penalty", 1.0)), 2)),
            "repeat_last_n": saved_params.get("repeat_last_n", int(gen_params.get("repeat_last_n", 64))),
            "mirostat": saved_params.get("mirostat", int(gen_params.get("mirostat", 0))),
            "mirostat_tau": saved_params.get("mirostat_tau", round(float(gen_params.get("mirostat_tau", 5.0)), 2)),
            "mirostat_eta": saved_params.get("mirostat_eta", round(float(gen_params.get("mirostat_eta", 0.10)), 2))
        }

        return {
            "harness_id": "llama_worker",
            "name": "llama.cpp Secondary Worker (:8002)",
            "role": "Secondary Worker Accelerator",
            "device": flags.get("device", "Vulkan1"),
            "model_path": flags.get("model", ""),
            "model_alias": props.get("model_alias", "worker"),
            "server_params": {
                "n_ctx": flags.get("n_ctx", 8192),
                "n_gpu_layers": flags.get("n_gpu_layers", 99),
                "flash_attn": flags.get("flash_attn", "on"),
                "cache_type_k": flags.get("cache_type_k", "q4_0"),
                "cache_type_v": flags.get("cache_type_v", "q4_0"),
                "batch_size": flags.get("batch_size", 2048),
                "ubatch_size": flags.get("ubatch_size", 512),
                "threads": flags.get("threads", 8),
                "threads_batch": flags.get("threads_batch", 8),
                "parallel": flags.get("parallel", 4),
                "defrag_thold": flags.get("defrag_thold", 0.1),
                "mlock": flags.get("mlock", False),
                "no_mmap": flags.get("no_mmap", False),
                "cont_batching": flags.get("cont_batching", False),
                "custom_flags": flags.get("custom_flags", "")
            },
            "sampling_params": sampling,
            "options": {
                "flash_attn": ["on", "off", "auto"],
                "cache_types": ["q4_0", "q8_0", "f16", "q4_1", "q5_0"],
                "devices": ["Vulkan0", "Vulkan1", "CUDA0", "CPU"],
                "mirostat_modes": [0, 1, 2]
            }
        }
    elif harness in ("hermes", "hermes_agentic", "moe"):
        defaults = {
            "model_target": "moe",
            "context_window": 16384,
            "max_iterations": 10,
            "temperature": 0.70,
            "min_p": 0.06,
            "presence_penalty": 0.25,
            "repeat_penalty": 1.15,
            "timeout_sec": 60,
            "system_prompt_mode": "agentic",
            "tool_call_retries": 3,
            "divergence_threshold": 0.85,
            "reflection_enabled": True,
            "custom_prompt_prefix": ""
        }
        saved = harness_settings.get("hermes", {})
        return {
            "harness_id": "hermes",
            "name": "Hermes 3 Agentic Loop (Ornith-1.5-35B MoE 16k)",
            "role": "ReAct Tool Execution Loop & Multi-Turn Reasoning",
            "device": "Vulkan0,Vulkan1 (Dual AMD GPU - 20.4 GB VRAM)",
            "model_alias": "Ornith-1.5-35B-A3B MoE (16k Ctx)",
            "server_params": {k: saved.get(k, v) for k, v in defaults.items()},
            "sampling_params": {
                "temperature": saved.get("temperature", 0.70),
                "min_p": saved.get("min_p", 0.06),
                "presence_penalty": saved.get("presence_penalty", 0.25),
                "repeat_penalty": saved.get("repeat_penalty", 1.15)
            },
            "options": {
                "system_prompt_mode": ["agentic", "strict_invariants", "exploratory", "minimal"],
                "model_target": ["moe", "coordinator", "worker"]
            }
        }
    elif harness == "snapdragon":
        defaults = {
            "quantization": "q4_k_m",
            "npu_power_profile": "sustained_high_performance",
            "threads": 4,
            "context_window": 4096,
            "compute_precision": "fp16",
            "kv_cache_budget_mb": 512,
            "temperature": 0.70,
            "top_p": 0.95
        }
        saved = harness_settings.get("snapdragon", {})
        return {
            "harness_id": "snapdragon",
            "name": "Snapdragon Edge NPU",
            "role": "Mobile On-Device NPU Acceleration",
            "server_params": {k: saved.get(k, v) for k, v in defaults.items()},
            "sampling_params": {},
            "options": {
                "quantization": ["q4_k_m", "q8_0", "f16", "int4_w4a16"],
                "npu_power_profile": ["burst", "sustained_high_performance", "balanced", "power_saver"],
                "compute_precision": ["fp16", "fp32", "int8"]
            }
        }
    elif harness == "openwebui":
        defaults = {
            "api_endpoint": "http://127.0.0.1:8080",
            "model_routing": "coordinator",
            "stream_timeout_sec": 90,
            "rag_top_k": 5,
            "default_system_prompt": "You are an intelligent homelab assistant running on the local dual accelerator cluster.",
            "temperature": 0.70,
            "max_tokens": 4096
        }
        saved = harness_settings.get("openwebui", {})
        return {
            "harness_id": "openwebui",
            "name": "OpenWebUI (LXC 119)",
            "role": "Web Chat Interface & Pipeline",
            "server_params": {k: saved.get(k, v) for k, v in defaults.items()},
            "sampling_params": {},
            "options": {
                "model_routing": ["coordinator", "worker", "cluster_hybrid", "cloud_frontier"]
            }
        }
    return {}

class StoneSageHandler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=FRONTEND_DIR, **kwargs)

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS, HEAD")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization, Range")
        self.end_headers()

    def do_HEAD(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        clean_path = path.strip().rstrip("/")
        if clean_path.endswith(".apk") or "aevum.apk" in path or "stonesage.apk" in path or clean_path in ("/download/aevum", "/download/stonesage", "/download", "/apk", "/aevum", "/stonesage"):
            apk_filename = "stonesage.apk" if "stonesage" in clean_path else "aevum.apk"
            apk_path = os.path.join(FRONTEND_DIR, apk_filename)
            if not os.path.exists(apk_path):
                fallback_apk = os.path.join(FRONTEND_DIR, "aevum.apk")
                if os.path.exists(fallback_apk):
                    apk_path = fallback_apk
            if os.path.exists(apk_path):
                total_size = os.path.getsize(apk_path)
                self.send_response(200)
                self.send_header("Content-Type", "application/vnd.android.package-archive")
                self.send_header("Content-Disposition", f'attachment; filename="{os.path.basename(apk_path)}"')
                self.send_header("Content-Length", str(total_size))
                self.send_header("Accept-Ranges", "bytes")
                self.send_header("Cache-Control", "no-cache, no-store, must-revalidate")
                self.send_header("Access-Control-Allow-Origin", "*")
                self.send_header("Connection", "close")
                self.end_headers()
                return
        elif clean_path == "/api/dataset/download":
            query = urllib.parse.parse_qs(parsed.query)
            q_type = query.get("type", ["sharegpt"])[0]
            fname = "homelab_curated_sharegpt.jsonl" if q_type == "sharegpt" else ("homelab_curated_alpaca.jsonl" if q_type == "alpaca" else "homelab_curated_manifest.json")
            fpath = os.path.join(ROOT_DIR, "datasets", fname)
            if os.path.exists(fpath):
                total_size = os.path.getsize(fpath)
                self.send_response(200)
                self.send_header("Content-Type", "application/x-jsonlines" if fname.endswith(".jsonl") else "application/json")
                self.send_header("Content-Disposition", f'attachment; filename="{fname}"')
                self.send_header("Content-Length", str(total_size))
                self.send_header("Accept-Ranges", "bytes")
                self.send_header("Access-Control-Allow-Origin", "*")
                self.send_header("Connection", "close")
                self.end_headers()
                return
            else:
                self.send_response(404)
                self.end_headers()
                return
        super().do_HEAD()

    def send_json(self, data: Any, status: int = 200):
        body = json.dumps(data).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def read_json_body(self) -> Dict[str, Any]:
        try:
            length = int(self.headers.get("Content-Length", 0))
            if length > 0:
                raw = self.rfile.read(length).decode("utf-8")
                return json.loads(raw)
        except Exception:
            pass
        return {}

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        clean_path = path.strip().rstrip("/")

        if clean_path.endswith(".apk") or "aevum.apk" in path or "stonesage.apk" in path or clean_path in ("/download/aevum", "/download/stonesage", "/download", "/apk", "/aevum", "/stonesage"):
            apk_filename = "stonesage.apk" if "stonesage" in clean_path else "aevum.apk"
            apk_path = os.path.join(FRONTEND_DIR, apk_filename)
            if not os.path.exists(apk_path):
                fallback_apk = os.path.join(FRONTEND_DIR, "aevum.apk")
                if os.path.exists(fallback_apk):
                    apk_path = fallback_apk
            
            if os.path.exists(apk_path):
                self.close_connection = True
                try:
                    total_size = os.path.getsize(apk_path)
                    range_header = self.headers.get("Range")
                    if range_header and range_header.startswith("bytes="):
                        range_spec = range_header[6:].strip()
                        parts = range_spec.split("-")
                        start = int(parts[0]) if parts[0] else 0
                        end = int(parts[1]) if len(parts) > 1 and parts[1] else total_size - 1
                        if start >= total_size:
                            self.send_response(416)
                            self.send_header("Content-Range", f"bytes */{total_size}")
                            self.send_header("Connection", "close")
                            self.end_headers()
                            return
                        end = min(end, total_size - 1)
                        content_length = (end - start) + 1

                        self.send_response(206)
                        self.send_header("Content-Type", "application/vnd.android.package-archive")
                        self.send_header("Content-Disposition", f'attachment; filename="{os.path.basename(apk_path)}"')
                        self.send_header("Content-Range", f"bytes {start}-{end}/{total_size}")
                        self.send_header("Content-Length", str(content_length))
                        self.send_header("Accept-Ranges", "bytes")
                        self.send_header("Cache-Control", "no-cache, no-store, must-revalidate")
                        self.send_header("Access-Control-Allow-Origin", "*")
                        self.send_header("Connection", "close")
                        self.end_headers()

                        with open(apk_path, "rb") as f:
                            f.seek(start)
                            remaining = content_length
                            while remaining > 0:
                                chunk = f.read(min(remaining, 65536))
                                if not chunk:
                                    break
                                self.wfile.write(chunk)
                                remaining -= len(chunk)
                        try:
                            self.wfile.flush()
                        except Exception:
                            pass
                        return
                    else:
                        self.send_response(200)
                        self.send_header("Content-Type", "application/vnd.android.package-archive")
                        self.send_header("Content-Disposition", f'attachment; filename="{os.path.basename(apk_path)}"')
                        self.send_header("Content-Length", str(total_size))
                        self.send_header("Accept-Ranges", "bytes")
                        self.send_header("Cache-Control", "no-cache, no-store, must-revalidate")
                        self.send_header("Access-Control-Allow-Origin", "*")
                        self.send_header("Connection", "close")
                        self.end_headers()

                        with open(apk_path, "rb") as f:
                            while True:
                                chunk = f.read(65536)
                                if not chunk:
                                    break
                                self.wfile.write(chunk)
                        try:
                            self.wfile.flush()
                        except Exception:
                            pass
                        return
                except (ConnectionResetError, BrokenPipeError):
                    return
                except Exception as ex:
                    try:
                        self.send_json({"ok": False, "error": str(ex)}, 500)
                    except Exception:
                        pass
                    return
            else:
                self.close_connection = True
                self.send_response(404)
                self.send_header("Connection", "close")
                self.end_headers()
                return

        elif path == "/api/harness/parameters":
            harness = urllib.parse.parse_qs(parsed.query).get("harness", ["llama_coordinator"])[0]
            data = get_harness_parameters(harness)
            self.send_json({"ok": True, "harness": harness, "data": data})
            return

        elif path == "/api/dataset/status":
            self.send_json({"ok": True, "status": dataset_compiler.get_status()})
            return

        elif path == "/api/dataset/download":
            query = urllib.parse.parse_qs(parsed.query)
            q_type = query.get("type", ["sharegpt"])[0]
            fname = "homelab_curated_sharegpt.jsonl" if q_type == "sharegpt" else ("homelab_curated_alpaca.jsonl" if q_type == "alpaca" else "homelab_curated_manifest.json")
            fpath = os.path.join(ROOT_DIR, "datasets", fname)
            if os.path.exists(fpath):
                self.close_connection = True
                total_size = os.path.getsize(fpath)
                self.send_response(200)
                self.send_header("Content-Type", "application/x-jsonlines" if fname.endswith(".jsonl") else "application/json")
                self.send_header("Content-Disposition", f'attachment; filename="{fname}"')
                self.send_header("Content-Length", str(total_size))
                self.send_header("Access-Control-Allow-Origin", "*")
                self.send_header("Connection", "close")
                self.end_headers()
                with open(fpath, "rb") as f:
                    while True:
                        chunk = f.read(65536)
                        if not chunk:
                            break
                        self.wfile.write(chunk)
                try:
                    self.wfile.flush()
                except Exception:
                    pass
                return
            else:
                self.send_json({"ok": False, "error": f"Dataset file {fname} not compiled yet."}, 404)
                return

        elif path == "/api/config":
            self.send_json(load_config())
            return

        elif path == "/api/services/status":
            cfg = load_config()
            services = cfg.get("services", [])
            
            def check_service(s):
                target_url = s.get("url", "")
                node = s.get("node", "bigserv")
                start = time.perf_counter()
                try:
                    ctx = ssl.create_default_context()
                    ctx.check_hostname = False
                    ctx.verify_mode = ssl.CERT_NONE
                    req = urllib.request.Request(target_url, headers={"Accept": "*/*", "User-Agent": "StoneSage-HealthProbe/2.0"})
                    with urllib.request.urlopen(req, timeout=1.8, context=ctx) as resp:
                        lat = round((time.perf_counter() - start) * 1000, 1)
                        return {**s, "online": True, "status_code": resp.status, "latency_ms": lat}
                except Exception as e:
                    lat = round((time.perf_counter() - start) * 1000, 1)
                    # Even if 401/403/404/405, service is online!
                    if hasattr(e, "code") and e.code in [401, 403, 404, 405]:
                        return {**s, "online": True, "status_code": e.code, "latency_ms": lat}
                    return {**s, "online": False, "error": str(e), "latency_ms": lat}

            with ThreadPoolExecutor(max_workers=10) as executor:
                results = list(executor.map(check_service, services))
            self.send_json({"ok": True, "services": results})
            return

        elif path == "/api/cluster/health":
            health = cluster.check_all_nodes()
            self.send_json({"ok": True, "cluster": health})
            return

        elif path == "/api/ha/status":
            status = hass.ping()
            self.send_json(status)
            return

        elif path == "/api/ha/dashboard":
            dashboard = hass.get_dashboard_summary()
            self.send_json(dashboard)
            return

        elif path == "/api/ha/entities":
            domain = urllib.parse.parse_qs(parsed.query).get("domain", [None])[0]
            states = hass.get_states(domain)
            self.send_json(states)
            return

        elif path == "/api/proxmox/nodes":
            pve_stat = proxmox.get_node_status("pve_node")
            bigserv_stat = proxmox.get_node_status("bigserv_node")
            self.send_json({"ok": True, "nodes": {"pve": pve_stat, "bigserv": bigserv_stat}})
            return

        elif path == "/api/proxmox/guests":
            pve_guests = proxmox.get_guests("pve_node")
            bigserv_guests = proxmox.get_guests("bigserv_node")
            all_guests = pve_guests.get("guests", []) + bigserv_guests.get("guests", [])
            self.send_json({"ok": True, "guests": all_guests})
            return

        elif path == "/api/couchdb/status":
            self.send_json(couchdb.get_status())
            return

        elif path in ("/api/ai/coordinator/v1/models", "/api/ai/worker/v1/models"):
            is_worker = "worker" in path
            m_id = "worker" if is_worker else "coordinator"
            self.send_json({
                "object": "list",
                "data": [
                    {
                        "id": m_id,
                        "object": "model",
                        "created": int(time.time()),
                        "owned_by": "pve-cluster"
                    }
                ]
            })
            return

        elif path == "/api/status/markdown":
            vault_p = config.get("obsidian", {}).get("user_vault_path") or config.get("obsidian", {}).get("vault_path")
            candidates = [
                os.path.join(vault_p, "Current Status.md") if vault_p else "",
                r"C:\Users\operator\OneDrive\Documents\obsidian\Current Status.md",
                "/opt/stonesage/vault_backup/Current Status.md",
                "vault_backup/Current Status.md"
            ]
            content = ""
            for c in candidates:
                if c and os.path.exists(c):
                    try:
                        with open(c, "r", encoding="utf-8") as f:
                            content = f.read()
                        break
                    except Exception:
                        pass
            if content:
                self.send_response(200)
                self.send_header("Content-Type", "text/markdown; charset=utf-8")
                self.send_header("Access-Control-Allow-Origin", "*")
                self.end_headers()
                self.wfile.write(content.encode("utf-8"))
            else:
                self.send_json({"error": "Current Status.md not found"}, status=404)
            return

        elif path == "/api/obsidian/notes":
            couch_notes = couchdb.list_notes()
            user_vault = config.get("obsidian", {}).get("user_vault_path", r"C:\Users\operator\OneDrive\Documents\obsidian")
            local_notes = []
            if user_vault and os.path.exists(user_vault):
                for root, dirs, files in os.walk(user_vault):
                    if any(x in root for x in [".git", ".obsidian", ".claudian", ".smart-env"]):
                        continue
                    for f in files:
                        if f.endswith((".md", ".txt", ".canvas")):
                            full = os.path.join(root, f)
                            rel = os.path.relpath(full, user_vault).replace("\\", "/")
                            try:
                                stat = os.stat(full)
                                mtime = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(stat.st_mtime))
                                local_notes.append({
                                    "id": rel,
                                    "name": f,
                                    "path": rel,
                                    "size_bytes": stat.st_size,
                                    "modified": mtime,
                                    "source": "local_vault"
                                })
                            except Exception:
                                pass

            backup_notes = vault.list_notes()

            merged_map = {}
            for n in couch_notes:
                key = n["path"].lower().strip()
                n["in_couchdb"] = True
                merged_map[key] = n

            for n in local_notes:
                key = n["path"].lower().strip()
                if key in merged_map:
                    merged_map[key]["has_local_file"] = True
                else:
                    n["in_couchdb"] = False
                    n["has_local_file"] = True
                    merged_map[key] = n

            for n in backup_notes:
                key = n["path"].lower().strip()
                if key in merged_map:
                    merged_map[key]["has_backup"] = True
                else:
                    n["has_backup"] = True
                    merged_map[key] = n

            all_notes = sorted(list(merged_map.values()), key=lambda x: x["path"].lower())
            self.send_json({
                "ok": True,
                "notes": all_notes,
                "total_count": len(all_notes),
                "couchdb_count": len(couch_notes),
                "local_count": len(local_notes)
            })
            return

        elif path == "/api/obsidian/note":
            rel_path = urllib.parse.parse_qs(parsed.query).get("path", [""])[0]
            user_vault = config.get("obsidian", {}).get("user_vault_path", r"C:\Users\operator\OneDrive\Documents\obsidian")
            if user_vault and os.path.exists(user_vault):
                norm_rel = os.path.normpath(rel_path).lstrip("\\/")
                full_path = os.path.join(user_vault, norm_rel)
                if not (os.path.exists(full_path) and os.path.isfile(full_path)):
                    # Case-insensitive or filename search in user_vault
                    target_name = os.path.basename(rel_path).lower()
                    for root, _, files in os.walk(user_vault):
                        for file in files:
                            if file.lower() == target_name:
                                full_path = os.path.join(root, file)
                                break
                        if os.path.exists(full_path) and os.path.isfile(full_path):
                            break

                if os.path.exists(full_path) and os.path.isfile(full_path):
                    try:
                        with open(full_path, "r", encoding="utf-8", errors="replace") as f:
                            content = f.read()
                        self.send_json({"ok": True, "path": rel_path, "content": content, "source": "user_vault"})
                        return
                    except Exception:
                        pass
            
            note = vault.get_note(rel_path)
            if note.get("ok"):
                self.send_json(note)
                return
            
            doc = couchdb.get_note_doc(rel_path)
            if doc:
                self.send_json({
                    "ok": True,
                    "path": rel_path,
                    "content": f"# {os.path.basename(rel_path)}\n\n*Note synced in CouchDB (Rev: {doc.get('_rev', 'unknown')})*\nSize: {doc.get('size', 0)} bytes\nLast Modified: {doc.get('mtime')}",
                    "source": "couchdb",
                    "doc": doc
                })
                return

            self.send_json({"ok": False, "error": f"Note '{rel_path}' not found."})
            return

        elif path == "/api/obsidian/sync_status":
            self.send_json({"ok": True, "sync": obsidian_ingestor.get_status(), "couchdb": couchdb.get_status()})
            return

        elif path == "/api/obsidian/search":
            q = urllib.parse.parse_qs(parsed.query).get("q", [""])[0]
            if not q:
                self.send_json({"ok": False, "error": "Missing query parameter 'q'"}, 400)
                return
            limit = int(urllib.parse.parse_qs(parsed.query).get("limit", ["6"])[0])
            results = cluster.search_hybrid(q, collection_name="obsidian_vault", limit=limit)
            self.send_json({"ok": True, "query": q, "count": len(results), "results": results})
            return

        elif path == "/api/memory/stm":
            self.send_json(stm.get_summary())
            return

        elif path == "/api/knowledge/status":
            kb_dir = os.path.join(config.get("obsidian", {}).get("user_vault_path", r"C:\Users\operator\OneDrive\Documents\obsidian"), "LocalLlmHub", "rag")
            file_count = 0
            if os.path.exists(kb_dir):
                for _, _, files in os.walk(kb_dir):
                    file_count += len([f for f in files if f.endswith(".md")])
            self.send_json({"ok": True, "kb_path": kb_dir, "file_count": file_count, "exists": os.path.exists(kb_dir)})
            return

        elif path == "/api/git/status":
            branch = "main"
            status_lines = []
            log_lines = []
            try:
                branch = subprocess.check_output(["git", "branch", "--show-current"], cwd=WORKSPACE_ROOT, text=True, stderr=subprocess.DEVNULL).strip()
            except Exception:
                pass
            try:
                status_out = subprocess.check_output(["git", "status", "--short"], cwd=WORKSPACE_ROOT, text=True, stderr=subprocess.DEVNULL).strip()
                status_lines = [l for l in status_out.splitlines() if l.strip()]
            except Exception:
                pass
            try:
                log_out = subprocess.check_output(["git", "log", "-n", "5", "--oneline"], cwd=WORKSPACE_ROOT, text=True, stderr=subprocess.DEVNULL).strip()
                log_lines = [l for l in log_out.splitlines() if l.strip()]
            except Exception:
                pass
            self.send_json({
                "ok": True,
                "branch": branch or "main",
                "changed_files": status_lines,
                "recent_commits": log_lines
            })
            return

        elif path == "/api/subagents/list":
            self.send_json({"ok": True, "subagents": list(subagent_registry.values())})
            return

        elif path == "/api/immich/stats":
            self.send_json(immich.get_stats())
            return

        elif path == "/api/immich/assets":
            cat = urllib.parse.parse_qs(parsed.query).get("category", ["all"])[0]
            assets = immich.get_assets(cat)
            self.send_json({"ok": True, "assets": assets})
            return

        elif path == "/api/immich/people":
            people = immich.get_people()
            self.send_json({"ok": True, "people": people})
            return

        elif path.startswith("/api/uploads/"):
            filename = os.path.basename(path)
            file_path = os.path.join(UPLOADS_DIR, filename)
            if os.path.exists(file_path) and os.path.isfile(file_path):
                ctype, _ = mimetypes.guess_type(file_path)
                ctype = ctype or "application/octet-stream"
                size = os.path.getsize(file_path)
                self.send_response(200)
                self.send_header("Content-Type", ctype)
                self.send_header("Content-Length", str(size))
                self.send_header("Access-Control-Allow-Origin", "*")
                self.send_header("Cache-Control", "public, max-age=86400")
                self.end_headers()
                with open(file_path, "rb") as f:
                    self.wfile.write(f.read())
                return
            else:
                self.send_json({"error": "File not found"}, 404)
                return

        elif path == "/api/workspace/tree":
            def build_tree(dir_path, current_depth=0, max_depth=3):
                items = []
                try:
                    for entry in os.scandir(dir_path):
                        if entry.name.startswith(".") and entry.name != ".ai":
                            continue
                        if entry.name in ["__pycache__", "node_modules", ".git", ".obsidian", ".system_generated", "vault_backup"]:
                            continue
                        rel = os.path.relpath(entry.path, WORKSPACE_ROOT).replace("\\", "/")
                        if entry.is_dir(follow_symlinks=False):
                            children = build_tree(entry.path, current_depth + 1, max_depth) if current_depth < max_depth else []
                            items.append({
                                "name": entry.name,
                                "path": rel,
                                "type": "directory",
                                "children": children
                            })
                        elif entry.is_file():
                            items.append({
                                "name": entry.name,
                                "path": rel,
                                "type": "file",
                                "size": entry.stat().st_size
                            })
                except Exception:
                    pass
                items.sort(key=lambda x: (0 if x["type"] == "directory" else 1, x["name"].lower()))
                return items

            tree = build_tree(WORKSPACE_ROOT)
            self.send_json({"ok": True, "root": WORKSPACE_ROOT, "tree": tree})
            return

        elif path == "/api/workspace/file":
            rel_path = urllib.parse.parse_qs(parsed.query).get("path", [""])[0]
            if not rel_path:
                self.send_json({"ok": False, "error": "Missing path parameter"}, 400)
                return
            full_path = os.path.abspath(os.path.join(WORKSPACE_ROOT, rel_path))
            if not full_path.startswith(WORKSPACE_ROOT):
                self.send_json({"ok": False, "error": "Access denied"}, 403)
                return
            if not os.path.exists(full_path) or not os.path.isfile(full_path):
                self.send_json({"ok": False, "error": "File not found"}, 404)
                return
            try:
                with open(full_path, "r", encoding="utf-8", errors="replace") as f:
                    content = f.read()
                self.send_json({"ok": True, "path": rel_path, "content": content, "size": len(content)})
            except Exception as ex:
                self.send_json({"ok": False, "error": str(ex)}, 500)
            return

        elif path in ["/api/hass/summary", "/api/ha/dashboard"]:
            summary = hass.get_dashboard_summary()
            helpers_res = hass.get_states(domain_filter="input_boolean")
            autos_res = hass.get_states(domain_filter="automation")
            summary["helpers"] = helpers_res.get("entities", [])
            summary["automations"] = [a for a in autos_res.get("entities", []) if any(k in a.get("entity_id", "") for k in ["stonesage", "bedtime", "movie", "patrol", "eco"])]
            
            # Curated Camera Feeds
            summary["cameras"] = [
                {
                    "entity_id": "camera.kitchen_living_room_hd_stream",
                    "name": "Kitchen / Living Room (Tapo C260 Pan/Tilt)",
                    "state": "idle",
                    "snapshot_url": "/api/hass/camera_snapshot?entity_id=camera.kitchen_living_room_hd_stream",
                    "stream_url": "/api/hass/camera_stream?entity_id=camera.kitchen_living_room_hd_stream",
                    "presets": ["Kitchen/Front Door", "Both Doors", "Living Room"]
                },
                {
                    "entity_id": "camera.driveway_front_door_hd_stream_direct",
                    "name": "Driveway / Front Door (Tapo Solar TCW90)",
                    "state": "idle",
                    "snapshot_url": "/api/hass/camera_snapshot?entity_id=camera.driveway_front_door_hd_stream_direct",
                    "stream_url": "/api/hass/camera_stream?entity_id=camera.driveway_front_door_hd_stream_direct",
                    "battery": 100,
                    "power_mode": "SOLAR",
                    "presets": ["Doors", "Cars", "Driveway", "Garden", "Straight Out"]
                }
            ]
            self.send_json(summary)
            return

        elif path == "/api/hass/cameras":
            cams = [
                {
                    "entity_id": "camera.kitchen_living_room_hd_stream",
                    "name": "Kitchen / Living Room (Tapo C260 Pan/Tilt)",
                    "state": "idle",
                    "snapshot_url": "/api/hass/camera_snapshot?entity_id=camera.kitchen_living_room_hd_stream",
                    "stream_url": "/api/hass/camera_stream?entity_id=camera.kitchen_living_room_hd_stream",
                    "presets": ["Kitchen/Front Door", "Both Doors", "Living Room"]
                },
                {
                    "entity_id": "camera.driveway_front_door_hd_stream_direct",
                    "name": "Driveway / Front Door (Tapo Solar TCW90)",
                    "state": "idle",
                    "snapshot_url": "/api/hass/camera_snapshot?entity_id=camera.driveway_front_door_hd_stream_direct",
                    "stream_url": "/api/hass/camera_stream?entity_id=camera.driveway_front_door_hd_stream_direct",
                    "battery": 100,
                    "power_mode": "SOLAR",
                    "presets": ["Doors", "Cars", "Driveway", "Garden", "Straight Out"]
                }
            ]
            self.send_json({"ok": True, "cameras": cams})
            return

        elif path == "/api/hass/camera_snapshot":
            entity_id = urllib.parse.parse_qs(parsed.query).get("entity_id", ["camera.kitchen_living_room_hd_stream"])[0]
            ha_url = f"{hass.base_url}/api/camera_proxy/{entity_id}"
            req = urllib.request.Request(ha_url, headers=hass._get_headers())
            try:
                with urllib.request.urlopen(req, timeout=4.0) as resp:
                    data = resp.read()
                    self.send_response(200)
                    self.send_header("Content-Type", "image/jpeg")
                    self.send_header("Content-Length", str(len(data)))
                    self.send_header("Cache-Control", "no-cache, no-store, must-revalidate")
                    self.send_header("Access-Control-Allow-Origin", "*")
                    self.end_headers()
                    self.wfile.write(data)
                    return
            except Exception as e:
                self.send_json({"ok": False, "error": str(e)}, 502)
                return

        elif path == "/api/hass/camera_stream":
            entity_id = urllib.parse.parse_qs(parsed.query).get("entity_id", ["camera.driveway_front_door_hd_stream_direct"])[0]
            ha_url = f"{hass.base_url}/api/camera_proxy_stream/{entity_id}"
            req = urllib.request.Request(ha_url, headers=hass._get_headers())
            try:
                resp = urllib.request.urlopen(req, timeout=8.0)
                content_type = resp.headers.get("Content-Type", "multipart/x-mixed-replace; boundary=ffmpeg")
                self.send_response(200)
                self.send_header("Content-Type", content_type)
                self.send_header("Cache-Control", "no-cache, no-store, must-revalidate")
                self.send_header("Access-Control-Allow-Origin", "*")
                self.end_headers()
                while True:
                    chunk = resp.read(4096)
                    if not chunk:
                        break
                    self.wfile.write(chunk)
                    self.wfile.flush()
                return
            except Exception:
                return

        # ── Transparent RAG Proxy: OpenAI-compatible /models endpoint ──
        elif path == "/api/ai/coordinator/v1/models":
            self.send_json({
                "object": "list",
                "data": [{
                    "id": "coordinator-14b-rag",
                    "object": "model",
                    "created": int(time.time()),
                    "owned_by": "stonesage-rag-proxy",
                    "permission": []
                }]
            })
            return

        elif path == "/api/harness/capabilities":
            try:
                # 1. Query live coordinator models from :8001/v1/models
                coord_info = {"id": "coordinator", "status": "unknown"}
                try:
                    req_c = urllib.request.Request("http://127.0.0.1:8001/v1/models", headers={"User-Agent": "Aevum-Server"})
                    with urllib.request.urlopen(req_c, timeout=2.5) as resp_c:
                        c_data = json.loads(resp_c.read().decode("utf-8"))
                        if c_data.get("data"):
                            coord_info = c_data["data"][0]
                            coord_info["status"] = "online"
                except Exception as ex_c:
                    coord_info["status"] = f"offline ({str(ex_c)})"

                # 2. Query live worker models from :8002/v1/models
                worker_info = {"id": "worker", "status": "unknown"}
                try:
                    req_w = urllib.request.Request("http://127.0.0.1:8002/v1/models", headers={"User-Agent": "Aevum-Server"})
                    with urllib.request.urlopen(req_w, timeout=2.5) as resp_w:
                        w_data = json.loads(resp_w.read().decode("utf-8"))
                        if w_data.get("data"):
                            worker_info = w_data["data"][0]
                            worker_info["status"] = "online"
                except Exception as ex_w:
                    worker_info["status"] = f"offline ({str(ex_w)})"

                # 3. Retrieve installed models list from disk or SSH
                installed_models = []
                try:
                    full_cmd2 = ["ssh", "-o", "BatchMode=yes", "-o", "StrictHostKeyChecking=no", f"{os.environ.get('CLUSTER_USER', 'user')}@127.0.0.1",
                                 "ls -lh /opt/models/*.gguf"]
                    res2 = subprocess.run(full_cmd2, capture_output=True, text=True, timeout=5)
                    if res2.returncode == 0 and res2.stdout:
                        for line in res2.stdout.strip().split("\n"):
                            parts = line.split()
                            if len(parts) >= 9:
                                fn = parts[8].replace("/opt/models/", "")
                                installed_models.append({
                                    "filename": fn,
                                    "size": parts[4],
                                    "is_locked": "ornith" in fn.lower()
                                })
                except Exception:
                    pass

                if not installed_models:
                    installed_models = [
                        {"filename": "Ornith-1.5-9B-OBLITERATED.Q8_0.gguf", "size": "9.8G", "is_locked": True},
                        {"filename": "Ornith-1.5-9B-Q4_K_M.gguf", "size": "5.8G", "is_locked": True}
                    ]

                available_harnesses = [
                    {"id": "hermes", "name": "Hermes 3 Agentic Loop (DEFAULT)", "description": "Ornith-1.5-35B MoE (16k Ctx, Dual-GPU Vulkan) with ReAct Step Loop"},
                    {"id": "llama_coordinator", "name": "llama.cpp Primary Coordinator (:8001)", "description": "Primary Uncensored Reasoning, Architecture & Coding Daemon"},
                    {"id": "llama_worker", "name": "llama.cpp Secondary Worker (:8002)", "description": "Secondary Divergent Ideation, Utility & Linter Daemon"},
                    {"id": "snapdragon", "name": "Snapdragon Edge NPU", "description": "Mobile on-device hardware accelerator"},
                    {"id": "openwebui", "name": "OpenWebUI (LXC 119)", "description": "Community chat interface on :8080"}
                ]

                available_backends = [
                    {"id": "cluster_lan", "name": "Dual-Accelerator Vulkan Cluster (127.0.0.1)", "description": "Primary Compute Accelerator + Secondary Worker Accelerator"},
                    {"id": "tailscale_vip", "name": "Tailscale Mesh VIP", "description": "Encrypted remote WireGuard mesh"},
                    {"id": "local_edge", "name": "On-Device Snapdragon NPU", "description": "Mobile local inference"}
                ]

                self.send_json({
                    "ok": True,
                    "timezone": "America/New_York (EST)",
                    "active_coordinator": coord_info,
                    "active_worker": worker_info,
                    "installed_models": installed_models,
                    "available_harnesses": available_harnesses,
                    "available_backends": available_backends
                })
            except Exception as ex:
                self.send_json({"ok": False, "error": str(ex)}, 500)
            return

        elif path == "/api/cluster/models":
            try:
                full_cmd = ["ssh", "-o", "BatchMode=yes", "-o", "StrictHostKeyChecking=no", f"{os.environ.get('CLUSTER_USER', 'user')}@127.0.0.1",
                            "grep -E -- '--model|-c ' /etc/systemd/system/llama-coordinator.service"]
                res = subprocess.run(full_cmd, capture_output=True, text=True, timeout=10)
                active_model = "Unknown"
                active_ctx = "8192"
                if res.returncode == 0:
                    for line in res.stdout.split("\n"):
                        if "--model" in line:
                            active_model = line.split("--model")[-1].strip().split()[0].replace("/opt/models/", "")
                        if "-c " in line:
                            active_ctx = line.split("-c ")[-1].strip().split()[0]

                full_cmd2 = ["ssh", "-o", "BatchMode=yes", "-o", "StrictHostKeyChecking=no", f"{os.environ.get('CLUSTER_USER', 'user')}@127.0.0.1",
                             "ls -lh /opt/models/*.gguf && df -h /opt/models | tail -n 1"]
                res2 = subprocess.run(full_cmd2, capture_output=True, text=True, timeout=10)
                models = []
                disk_str = ""
                if res2.returncode == 0 and res2.stdout:
                    lines = res2.stdout.strip().split("\n")
                    disk_str = lines[-1] if lines else ""
                    for line in lines[:-1]:
                        parts = line.split()
                        if len(parts) >= 9:
                            models.append({
                                "name": parts[8].replace("/opt/models/", ""),
                                "size": parts[4]
                            })

                calib_file = os.path.join(WORKSPACE_ROOT, ".agents", "skills", "model-parameter-discoverer", "optimal_profile.json")
                calib = {}
                if os.path.exists(calib_file):
                    try:
                        with open(calib_file, "r", encoding="utf-8") as f:
                            calib = json.load(f)
                    except Exception:
                        pass

                self.send_json({
                    "ok": True,
                    "active_model": active_model,
                    "active_context": active_ctx,
                    "models": models,
                    "disk": disk_str,
                    "calibration": calib
                })
            except Exception as ex:
                self.send_json({"ok": False, "error": str(ex)}, 500)
        elif path == "/api/hivemind/status":
            cfg = load_config()
            mcp_u = cfg.get("cluster", {}).get("mcp_url", "http://127.0.0.1:8765")
            try:
                payload = {"jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": {"name": "autonomous_thinking_status"}}
                req = urllib.request.Request(mcp_u, data=json.dumps(payload).encode("utf-8"), headers={"Content-Type": "application/json"})
                with urllib.request.urlopen(req, timeout=10) as resp:
                    res = json.loads(resp.read().decode("utf-8"))
                    raw_txt = res.get("result", {}).get("content", [{}])[0].get("text", "{}")
                    parsed_st = json.loads(raw_txt)
                    parsed_st["preemption"] = cluster.get_preemption_status()
                    self.send_json({"ok": True, "status": parsed_st})
            except Exception as ex:
                self.send_json({"ok": False, "error": str(ex)}, 500)
            return

        elif path == "/api/hivemind/agents":
            cfg = load_config()
            mcp_u = cfg.get("cluster", {}).get("mcp_url", "http://127.0.0.1:8765")
            try:
                payload = {"jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": {"name": "list_active_agents"}}
                req = urllib.request.Request(mcp_u, data=json.dumps(payload).encode("utf-8"), headers={"Content-Type": "application/json"})
                with urllib.request.urlopen(req, timeout=10) as resp:
                    res = json.loads(resp.read().decode("utf-8"))
                    raw_txt = res.get("result", {}).get("content", [{}])[0].get("text", "[]")
                    agents = json.loads(raw_txt) if raw_txt else []
                    self.send_json({"ok": True, "agents": agents})
            except Exception as ex:
                self.send_json({"ok": False, "error": str(ex), "agents": []}, 500)
            return

        elif path == "/api/hivemind/live_stream":
            cfg = load_config()
            mcp_u = cfg.get("cluster", {}).get("mcp_url", "http://127.0.0.1:8765")
            try:
                payload_st = {"jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": {"name": "autonomous_thinking_status"}}
                payload_ag = {"jsonrpc": "2.0", "id": 2, "method": "tools/call", "params": {"name": "list_active_agents"}}
                
                req_st = urllib.request.Request(mcp_u, data=json.dumps(payload_st).encode("utf-8"), headers={"Content-Type": "application/json"})
                with urllib.request.urlopen(req_st, timeout=10) as resp:
                    res_st = json.loads(resp.read().decode("utf-8"))
                    raw_st = res_st.get("result", {}).get("content", [{}])[0].get("text", "{}")
                    status = json.loads(raw_st)
                
                req_ag = urllib.request.Request(mcp_u, data=json.dumps(payload_ag).encode("utf-8"), headers={"Content-Type": "application/json"})
                with urllib.request.urlopen(req_ag, timeout=10) as resp:
                    res_ag = json.loads(resp.read().decode("utf-8"))
                    raw_ag = res_ag.get("result", {}).get("content", [{}])[0].get("text", "[]")
                    agents = json.loads(raw_ag) if raw_ag else []

                self.send_json({"ok": True, "status": status, "agents": agents, "events": []})
            except Exception as ex:
                self.send_json({"ok": False, "error": str(ex)}, 500)
            return

        elif path == "/api/hivemind/vision_log":
            cfg = load_config()
            mcp_u = cfg.get("cluster", {}).get("mcp_url", "http://127.0.0.1:8765")
            limit = int(urllib.parse.parse_qs(parsed.query).get("limit", [150])[0])
            try:
                payload = {"jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": {"name": "get_home_vision_log", "arguments": {"limit_lines": limit}}}
                req = urllib.request.Request(mcp_u, data=json.dumps(payload).encode("utf-8"), headers={"Content-Type": "application/json"})
                with urllib.request.urlopen(req, timeout=10) as resp:
                    res = json.loads(resp.read().decode("utf-8"))
                    raw_txt = res.get("result", {}).get("content", [{}])[0].get("text", "")
                    self.send_json({"ok": True, "log": raw_txt})
            except Exception as ex:
                self.send_json({"ok": False, "error": str(ex)}, 500)
            return

        elif path in ("/api/tags", "/api/models"):
            # Official Ollama-compatible Tags endpoint for Home Assistant
            self.send_json({
                "models": [
                    {
                        "name": "worker:latest",
                        "model": "worker:latest",
                        "modified_at": "2026-09-08T00:00:00Z",
                        "size": 5769121792,
                        "digest": "sha256:ornith9bworker",
                        "details": {
                            "parent_model": "",
                            "format": "gguf",
                            "family": "ornith",
                            "families": ["ornith", "qwen2"],
                            "parameter_size": "9B",
                            "quantization_level": "Q4_K_M"
                        }
                    },
                    {
                        "name": "coordinator:latest",
                        "model": "coordinator:latest",
                        "modified_at": "2026-09-08T00:00:00Z",
                        "size": 9775091712,
                        "digest": "sha256:ornith9bcoordinator",
                        "details": {
                            "parent_model": "",
                            "format": "gguf",
                            "family": "ornith",
                            "families": ["ornith", "qwen2"],
                            "parameter_size": "9B",
                            "quantization_level": "Q8_0"
                        }
                    }
                ]
            })
            return

        elif path == "/api/version":
            self.send_json({"version": "0.4.0"})
            return

        elif path == "/api/preemption/status":
            self.send_json(cluster.get_preemption_status())
            return

        elif path == "/api/task_routing":
            cfg = load_config()
            self.send_json({
                "ok": True,
                "task_routing": cfg.get("task_routing", {}),
                "gemini_web": {
                    "enabled": cfg.get("gemini_web", {}).get("enabled", True),
                    "configured": bool(cfg.get("gemini_web", {}).get("psid")),
                    "endpoint": cfg.get("gemini_web", {}).get("endpoint", "http://127.0.0.1:8087")
                }
            })
            return

        # Fallback to serving frontend static assets
        super().do_GET()

    def do_POST(self):
        try:
            parsed = urllib.parse.urlparse(self.path)
            path = parsed.path
            body = self.read_json_body()

            if path == "/api/harness/apply_parameters":
                harness = body.get("harness", "llama_coordinator")
                params = body.get("parameters", {})
                
                cfg = load_config()
                if "harness_settings" not in cfg:
                    cfg["harness_settings"] = {}
                if harness not in cfg["harness_settings"]:
                    cfg["harness_settings"][harness] = {}
                cfg["harness_settings"][harness].update(params)
                save_config(cfg)

                if harness in ("hermes", "moe"):
                    ok, msg = apply_llama_parameters("llama-moe.service", 8001, "moe", params)
                    self.send_json({"ok": ok, "message": msg}, 200 if ok else 400)
                    return
                elif harness in ("llama_coordinator", "coordinator"):
                    svc = "llama-moe.service" if is_moe_active() else "llama-coordinator.service"
                    target_alias = "moe" if is_moe_active() else "coordinator"
                    ok, msg = apply_llama_parameters(svc, 8001, target_alias, params)
                    self.send_json({"ok": ok, "message": msg}, 200 if ok else 400)
                    return
                elif harness in ("llama_worker", "worker"):
                    ok, msg = apply_llama_parameters("llama-worker.service", 8002, "worker", params)
                    self.send_json({"ok": ok, "message": msg}, 200 if ok else 400)
                    return
                else:
                    self.send_json({"ok": True, "message": f"{harness} configuration updated successfully!"})
                    return

            elif path == "/api/dataset/compile":
                limit = int(body.get("limit", 25))
                res = dataset_compiler.run_compilation(limit=limit)
                self.send_json(res)
                return

            elif path == "/api/dataset/stop":
                res = dataset_compiler.stop_compilation()
                self.send_json(res)
                return

            elif path == "/api/config":
                cfg = load_config()
                deep_update(cfg, body)
                # Auto-parse proxmox token_value if provided
                raw_tok = cfg.get("proxmox", {}).get("token_value", "").strip()
                if raw_tok:
                    clean_tok = raw_tok
                    if clean_tok.startswith("PVEAPIToken="):
                        clean_tok = clean_tok[len("PVEAPIToken="):].strip()
                    if "=" in clean_tok:
                        tid, tsec = clean_tok.split("=", 1)
                        for n in ["pve_node", "bigserv_node"]:
                            if n in cfg.get("proxmox", {}):
                                cfg["proxmox"][n]["token_id"] = tid.strip()
                                cfg["proxmox"][n]["token_secret"] = tsec.strip()
                save_config(cfg)
                # Re-initialize clients with updated config
                global proxmox, hass, cluster, immich
                proxmox = ProxmoxClient(cfg.get("proxmox", {}))
                hass.set_token(cfg.get("homeassistant", {}).get("token", ""))
                cluster = ClusterClient(cfg)
                immich = ImmichClient(cfg.get("immich", {}), UPLOADS_DIR)
                self.send_json({"ok": True, "message": "Configuration saved successfully."})
                return

            elif path == "/api/task_routing":
                cfg = load_config()
                routing = body.get("task_routing", body)
                if "task_routing" not in cfg:
                    cfg["task_routing"] = {}
                cfg["task_routing"].update(routing)
                save_config(cfg)
                self.send_json({"ok": True, "task_routing": cfg["task_routing"], "message": "Task routing updated successfully."})
                return

            elif path in ("/api/gemini_web/configure", "/api/gemini_web/cookies"):
                cfg = load_config()
                psid = body.get("psid", "").strip()
                psidts = body.get("psidts", "").strip()
                if "gemini_web" not in cfg:
                    cfg["gemini_web"] = {}
                if psid:
                    cfg["gemini_web"]["psid"] = psid
                if psidts:
                    cfg["gemini_web"]["psidts"] = psidts
                save_config(cfg)
                
                # Sync cookies directly to Gemini Web Bridge on Port 8087
                is_valid = False
                bridge_msg = "Saved locally"
                try:
                    f_url = "http://127.0.0.1:8087/api/cookies"
                    req = urllib.request.Request(
                        f_url,
                        data=json.dumps({"psid": psid, "psidts": psidts}).encode("utf-8"),
                        headers={"Content-Type": "application/json"},
                        method="POST"
                    )
                    with urllib.request.urlopen(req, timeout=10.0) as resp:
                        res_data = json.loads(resp.read().decode("utf-8"))
                        is_valid = bool(res_data.get("ok") and res_data.get("session_active"))
                        bridge_msg = res_data.get("message", "Session verified")
                except Exception as ex:
                    bridge_msg = f"Cookie sync error: {ex}"
                    is_valid = False
                
                self.send_json({"ok": is_valid, "session_active": is_valid, "message": bridge_msg})
                return

            elif path == "/api/hivemind/vigilance":
                cfg = load_config()
                mcp_u = cfg.get("cluster", {}).get("mcp_url", "http://127.0.0.1:8765")
                try:
                    payload = {"jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": {"name": "trigger_home_vigilance_sweep"}}
                    req = urllib.request.Request(mcp_u, data=json.dumps(payload).encode("utf-8"), headers={"Content-Type": "application/json"})
                    with urllib.request.urlopen(req, timeout=120) as resp:
                        res = json.loads(resp.read().decode("utf-8"))
                        raw_txt = res.get("result", {}).get("content", [{}])[0].get("text", "{}")
                        self.send_json({"ok": True, "result": json.loads(raw_txt)})
                except Exception as ex:
                    self.send_json({"ok": False, "error": str(ex)}, 500)
                return

            elif path == "/api/hivemind/cycle":
                cfg = load_config()
                mcp_u = cfg.get("cluster", {}).get("mcp_url", "http://127.0.0.1:8765")
                domain = body.get("domain")
                prompt = body.get("prompt")
                args = {}
                if domain: args["domain"] = domain
                if prompt: args["seed_prompt"] = prompt
                try:
                    payload = {"jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": {"name": "run_thinking_cycle", "arguments": args}}
                    req = urllib.request.Request(mcp_u, data=json.dumps(payload).encode("utf-8"), headers={"Content-Type": "application/json"})
                    with urllib.request.urlopen(req, timeout=120) as resp:
                        res = json.loads(resp.read().decode("utf-8"))
                        raw_txt = res.get("result", {}).get("content", [{}])[0].get("text", "{}")
                        self.send_json({"ok": True, "result": json.loads(raw_txt)})
                except Exception as ex:
                    self.send_json({"ok": False, "error": str(ex)}, 500)
                return

            elif path == "/api/hivemind/toggle":
                cfg = load_config()
                mcp_u = cfg.get("cluster", {}).get("mcp_url", "http://127.0.0.1:8765")
                action = body.get("action", "start")
                t_name = "start_autonomous_thinking" if action == "start" else "stop_autonomous_thinking"
                t_args = {"interval_seconds": body.get("interval_seconds", 120)} if action == "start" else {}
                try:
                    payload = {"jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": {"name": t_name, "arguments": t_args}}
                    req = urllib.request.Request(mcp_u, data=json.dumps(payload).encode("utf-8"), headers={"Content-Type": "application/json"})
                    with urllib.request.urlopen(req, timeout=30) as resp:
                        res = json.loads(resp.read().decode("utf-8"))
                        raw_txt = res.get("result", {}).get("content", [{}])[0].get("text", "")
                        self.send_json({"ok": True, "message": raw_txt})
                except Exception as ex:
                    self.send_json({"ok": False, "error": str(ex)}, 500)
                return

            elif path == "/api/agent/nudge":
                cfg = load_config()
                mcp_u = cfg.get("cluster", {}).get("mcp_url", "http://127.0.0.1:8765")
                agent_id = body.get("agent_id", "engine")
                directive = body.get("directive")
                try:
                    payload = {"jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": {"name": "nudge_agent", "arguments": {"agent_id": agent_id, "directive": directive}}}
                    req = urllib.request.Request(mcp_u, data=json.dumps(payload).encode("utf-8"), headers={"Content-Type": "application/json"})
                    with urllib.request.urlopen(req, timeout=30) as resp:
                        res = json.loads(resp.read().decode("utf-8"))
                        raw_txt = res.get("result", {}).get("content", [{}])[0].get("text", "{}")
                        self.send_json({"ok": True, "result": json.loads(raw_txt)})
                except Exception as ex:
                    self.send_json({"ok": False, "error": str(ex)}, 500)
                return

            elif path == "/api/agent/delete":
                cfg = load_config()
                mcp_u = cfg.get("cluster", {}).get("mcp_url", "http://127.0.0.1:8765")
                agent_id = body.get("agent_id")
                try:
                    payload = {"jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": {"name": "delete_active_agent", "arguments": {"agent_id": agent_id}}}
                    req = urllib.request.Request(mcp_u, data=json.dumps(payload).encode("utf-8"), headers={"Content-Type": "application/json"})
                    with urllib.request.urlopen(req, timeout=30) as resp:
                        res = json.loads(resp.read().decode("utf-8"))
                        raw_txt = res.get("result", {}).get("content", [{}])[0].get("text", "")
                        self.send_json({"ok": True, "message": raw_txt})
                except Exception as ex:
                    self.send_json({"ok": False, "error": str(ex)}, 500)
                return

            elif path == "/api/agent/stop":
                cfg = load_config()
                mcp_u = cfg.get("cluster", {}).get("mcp_url", "http://127.0.0.1:8765")
                agent_id = body.get("agent_id")
                try:
                    payload = {"jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": {"name": "stop_background_agent", "arguments": {"agent_id": agent_id}}}
                    req = urllib.request.Request(mcp_u, data=json.dumps(payload).encode("utf-8"), headers={"Content-Type": "application/json"})
                    with urllib.request.urlopen(req, timeout=30) as resp:
                        res = json.loads(resp.read().decode("utf-8"))
                        raw_txt = res.get("result", {}).get("content", [{}])[0].get("text", "")
                        self.send_json({"ok": True, "message": raw_txt})
                except Exception as ex:
                    self.send_json({"ok": False, "error": str(ex)}, 500)
                return

            elif path == "/api/agent/reproduce":
                cfg = load_config()
                mcp_u = cfg.get("cluster", {}).get("mcp_url", "http://127.0.0.1:8765")
                p_args = {
                    "parent_a_id": body.get("parent_a_id"),
                    "parent_b_id": body.get("parent_b_id"),
                    "blend_ratio": body.get("blend_ratio", 0.5),
                    "focus_intent": body.get("focus_intent"),
                    "custom_name": body.get("custom_name"),
                    "custom_role": body.get("custom_role"),
                    "custom_mission": body.get("custom_mission"),
                    "custom_system_prompt": body.get("custom_system_prompt"),
                    "custom_focus_question": body.get("custom_focus_question"),
                    "model_preference": body.get("model_preference", "coordinator")
                }
                # Remove None entries
                p_args = {k: v for k, v in p_args.items() if v is not None}
                try:
                    payload = {"jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": {"name": "reproduce_blended_agent", "arguments": p_args}}
                    req = urllib.request.Request(mcp_u, data=json.dumps(payload).encode("utf-8"), headers={"Content-Type": "application/json"})
                    with urllib.request.urlopen(req, timeout=120) as resp:
                        res = json.loads(resp.read().decode("utf-8"))
                        if "error" in res:
                            err_msg = res["error"].get("message", str(res["error"])) if isinstance(res["error"], dict) else str(res["error"])
                            self.send_json({"ok": False, "error": err_msg}, 400)
                            return
                        content_list = res.get("result", {}).get("content", [])
                        raw_txt = content_list[0].get("text", "{}") if content_list else "{}"
                        try:
                            parsed_res = json.loads(raw_txt)
                        except Exception:
                            parsed_res = {"message": raw_txt}
                        self.send_json({"ok": True, "result": parsed_res})
                except Exception as ex:
                    self.send_json({"ok": False, "error": str(ex)}, 500)
                return

            elif path == "/api/services/save":
                svc = body.get("service") or body
                sid = svc.get("id", "").strip()
                name = svc.get("name", "").strip()
                if not sid and name:
                    sid = name.lower().replace(" ", "_").replace("/", "_").replace("-", "_")
                    sid = "".join(c for c in sid if c.isalnum() or c == "_")
                    svc["id"] = sid
                if not sid:
                    self.send_json({"ok": False, "error": "Missing service id or name"}, 400)
                    return

                cfg = load_config()
                services = cfg.get("services", [])
                found = False
                for i, existing in enumerate(services):
                    if existing.get("id") == sid:
                        services[i] = {**existing, **svc}
                        found = True
                        break
                if not found:
                    services.append(svc)
                cfg["services"] = services
                save_config(cfg)
                self.send_json({"ok": True, "message": "Service saved successfully", "service": svc, "services": services})
                return

            elif path == "/api/services/delete":
                sid = body.get("id", "").strip()
                if not sid:
                    self.send_json({"ok": False, "error": "Missing service id"}, 400)
                    return
                cfg = load_config()
                services = [s for s in cfg.get("services", []) if s.get("id") != sid]
                cfg["services"] = services
                save_config(cfg)
                self.send_json({"ok": True, "message": "Service deleted successfully", "services": services})
                return

            elif path == "/api/services/reorder":
                ordered_ids = body.get("service_ids", [])
                if not ordered_ids:
                    self.send_json({"ok": False, "error": "Missing service_ids array"}, 400)
                    return
                cfg = load_config()
                services = cfg.get("services", [])
                id_map = {s.get("id"): s for s in services}
                new_services = []
                for sid in ordered_ids:
                    if sid in id_map:
                        new_services.append(id_map.pop(sid))
                for s in services:
                    if s.get("id") in id_map:
                        new_services.append(s)
                cfg["services"] = new_services
                save_config(cfg)
                self.send_json({"ok": True, "message": "Services reordered successfully", "services": new_services})
                return

            elif path == "/api/cluster/chat":
                target = body.get("target", "coordinator")
                messages = body.get("messages", [])
                params = body.get("params", {})

                self.send_response(200)
                self.send_header("Content-Type", "text/event-stream; charset=utf-8")
                self.send_header("Cache-Control", "no-cache")
                self.send_header("Connection", "close")
                self.send_header("Access-Control-Allow-Origin", "*")
                self.end_headers()

                try:
                    for chunk in cluster.stream_chat(target, messages, params):
                        self.wfile.write(chunk.encode("utf-8"))
                        self.wfile.flush()
                except Exception as e:
                    err_data = f"data: {json.dumps({'error': str(e)})}\n\n"
                    self.wfile.write(err_data.encode("utf-8"))
                    self.wfile.flush()
                return

            elif path == "/api/cluster/arena":
                models = body.get("models", ["coordinator", "worker"])
                prompt = body.get("prompt", "")
                answers = cluster.multi_model_arena_query(models, prompt)
                self.send_json({"ok": True, "answers": answers})
                return

            elif path == "/api/cluster/synthesize":
                prompt = body.get("prompt", "")
                answers = body.get("answers", {})
                synthesis = cluster.synthesize_answers(prompt, answers)
                self.send_json({"ok": True, "synthesis": synthesis})
                return

            elif path == "/api/cluster/switch-model":
                model = body.get("model", "").strip()
                hf = body.get("hf", "").strip()
                file = body.get("file", "").strip()
                ctx = int(body.get("context", 16384))
                auto_tune = bool(body.get("auto_tune", True))

                switcher_py = os.path.join(WORKSPACE_ROOT, ".agents", "skills", "cluster-model-switcher", "switch_model.py")
                cmd_args = [sys.executable, switcher_py]
                if hf and file:
                    cmd_args.extend(["--hf", hf, "--file", file, "--context", str(ctx)])
                elif model:
                    cmd_args.extend(["--model", model, "--context", str(ctx)])
                else:
                    self.send_json({"ok": False, "error": "Missing model or hf parameters"}, 400)
                    return

                if not auto_tune:
                    cmd_args.append("--no-tune")

                try:
                    proc = subprocess.run(cmd_args, capture_output=True, text=True, timeout=600)
                    self.send_json({
                        "ok": proc.returncode == 0,
                        "output": proc.stdout + ("\n" + proc.stderr if proc.stderr else ""),
                        "returncode": proc.returncode
                    })
                except Exception as ex:
                    self.send_json({"ok": False, "error": str(ex)}, 500)
                return

            elif path == "/api/cluster/rollback-model":
                switcher_py = os.path.join(WORKSPACE_ROOT, ".agents", "skills", "cluster-model-switcher", "switch_model.py")
                try:
                    proc = subprocess.run([sys.executable, switcher_py, "--rollback"], capture_output=True, text=True, timeout=60)
                    self.send_json({
                        "ok": proc.returncode == 0,
                        "output": proc.stdout + ("\n" + proc.stderr if proc.stderr else ""),
                        "returncode": proc.returncode
                    })
                except Exception as ex:
                    self.send_json({"ok": False, "error": str(ex)}, 500)
                return

            elif path == "/api/cluster/delete-model":
                model = body.get("model", "").strip()
                safe_filename = os.path.basename(model)
                if not safe_filename or not safe_filename.endswith(".gguf"):
                    self.send_json({"ok": False, "error": "Invalid model filename. Must be a .gguf file."}, 400)
                    return
                if "ornith" in safe_filename.lower():
                    self.send_json({"ok": False, "error": "Protected model: Ornith models are permanently locked and cannot be deleted."}, 403)
                    return
                try:
                    # Check active models
                    chk_cmd = ["ssh", "-o", "BatchMode=yes", "-o", "StrictHostKeyChecking=no", f"{os.environ.get('CLUSTER_USER', 'user')}@127.0.0.1",
                               "grep -E -- '--model' /etc/systemd/system/llama-*.service"]
                    chk_res = subprocess.run(chk_cmd, capture_output=True, text=True, timeout=10)
                    if chk_res.returncode == 0 and safe_filename in chk_res.stdout:
                        self.send_json({"ok": False, "error": f"Cannot delete '{safe_filename}' because it is currently loaded in an active service. Switch models first."}, 400)
                        return

                    del_cmd = ["ssh", "-o", "BatchMode=yes", "-o", "StrictHostKeyChecking=no", f"{os.environ.get('CLUSTER_USER', 'user')}@127.0.0.1",
                               f"rm -f /opt/models/{safe_filename}"]
                    del_res = subprocess.run(del_cmd, capture_output=True, text=True, timeout=15)
                    if del_res.returncode == 0:
                        self.send_json({"ok": True, "deleted": safe_filename})
                    else:
                        self.send_json({"ok": False, "error": del_res.stderr or "Failed to delete file on cluster."}, 500)
                except Exception as ex:
                    self.send_json({"ok": False, "error": str(ex)}, 500)
                return

            elif path == "/api/cluster/calibrate-model":
                discover_py = os.path.join(WORKSPACE_ROOT, ".agents", "skills", "model-parameter-discoverer", "discover_parameters.py")
                model_name = body.get("model_name", "Current-Model")
                try:
                    proc = subprocess.run([sys.executable, discover_py, "--model-name", model_name, "--port", "8001"], capture_output=True, text=True, timeout=240)
                    self.send_json({
                        "ok": proc.returncode == 0,
                        "output": proc.stdout + ("\n" + proc.stderr if proc.stderr else ""),
                        "returncode": proc.returncode
                    })
                except Exception as ex:
                    self.send_json({"ok": False, "error": str(ex)}, 500)
                return

            elif path == "/api/memory/search":
                query = body.get("query", "")
                collection = body.get("collection", "codebase_knowledge")
                limit = int(body.get("limit", 5))
                results = cluster.search_memory(query, collection, limit)
                self.send_json({"ok": True, "results": results})
                return

            elif path == "/api/memory/store":
                content = body.get("content", "")
                collection = body.get("collection", "agent_memories")
                meta = body.get("metadata", {})
                point_id = cluster.store_memory(content, collection, meta)
                self.send_json({"ok": True, "point_id": point_id})
                return

            elif path == "/api/ha/service":
                domain = body.get("domain", "")
                service = body.get("service", "")
                data = body.get("service_data", {})
                res = hass.call_service(domain, service, data)
                self.send_json(res)
                return

            elif path == "/api/proxmox/reboot":
                node = body.get("node", "pve_node")
                guest_type = body.get("type", "lxc")
                vmid = str(body.get("vmid", ""))
                res = proxmox.reboot_guest(node, guest_type, vmid)
                self.send_json(res)
                return

            elif path == "/api/obsidian/save":
                rel_path = body.get("path", "")
                content = body.get("content", "")
                res = vault.save_note(rel_path, content)
                self.send_json(res)
                return

            elif path == "/api/obsidian/delete":
                rel_path = body.get("path", "")
                res = vault.delete_note(rel_path)
                self.send_json(res)
                return

            elif path == "/api/obsidian/sync":
                exporter_py = os.path.join(WORKSPACE_ROOT, ".agents", "skills", "database-memory-sync", "export_all_to_database.py")
                def run_vault_sync():
                    try:
                        subprocess.run([sys.executable, exporter_py, "--vault-only"], capture_output=True, text=True, check=False)
                    except Exception as e:
                        print(f"[StoneSage] Vault sync background error: {e}")
                threading.Thread(target=run_vault_sync, daemon=True).start()
                self.send_json({"ok": True, "message": "Obsidian vault to Qdrant sync started in background."})
                return

            elif path == "/api/subagents/dispatch":
                role = body.get("role", "Specialized Subagent")
                task = body.get("task", "")
                model = body.get("model", "worker")
                subagent_id = f"sub-{int(time.time())}"
                
                subagent_registry[subagent_id] = {
                    "id": subagent_id,
                    "role": role,
                    "task": task,
                    "model": model,
                    "status": "running",
                    "output": "",
                    "started_at": time.strftime("%H:%M:%S")
                }

                def run_subagent_task():
                    try:
                        chunks = []
                        for c in cluster.stream_chat(model, [{"role": "user", "content": task}], {"max_tokens": 1500}):
                            if c.startswith("data: ") and "[DONE]" not in c:
                                try:
                                    delta = json.loads(c[6:])["choices"][0]["delta"].get("content") or ""
                                    if delta:
                                        chunks.append(delta)
                                except Exception:
                                    pass
                        subagent_registry[subagent_id]["status"] = "completed"
                        subagent_registry[subagent_id]["output"] = "".join(chunks)
                        subagent_registry[subagent_id]["finished_at"] = get_eastern_time_str()
                    except Exception as e:
                        subagent_registry[subagent_id]["status"] = "error"
                        subagent_registry[subagent_id]["output"] = str(e)

                threading.Thread(target=run_subagent_task, daemon=True).start()
                self.send_json({"ok": True, "subagent_id": subagent_id, "role": role, "status": "running"})
                return

            elif path in ("/api/agents/delete", "/api/subagents/delete"):
                agent_id = body.get("agent_id", "").strip()
                if not agent_id:
                    self.send_json({"ok": False, "error": "Missing agent_id"}, 400)
                    return
                # Also remove from local registry if present
                if agent_id in subagent_registry:
                    del subagent_registry[agent_id]
                # Call cluster MCP delete_active_agent
                cfg = load_config()
                mcp_u = cfg.get("cluster", {}).get("mcp_url", "http://127.0.0.1:8765")
                try:
                    payload = {"jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": {"name": "delete_active_agent", "arguments": {"agent_id": agent_id}}}
                    req = urllib.request.Request(mcp_u, data=json.dumps(payload).encode("utf-8"), headers={"Content-Type": "application/json"})
                    with urllib.request.urlopen(req, timeout=10) as resp:
                        res = json.loads(resp.read().decode("utf-8"))
                        self.send_json({"ok": True, "result": res})
                except Exception as ex:
                    self.send_json({"ok": False, "error": str(ex)}, 500)
                return

            elif path == "/api/files/upload":
                raw_data = body.get("data_base64") or body.get("data_url") or body.get("content") or ""
                orig_name = body.get("filename") or body.get("name") or "upload.bin"
                content_type = body.get("content_type") or body.get("type") or "application/octet-stream"
                
                if "," in raw_data:
                    raw_data = raw_data.split(",", 1)[1]
                try:
                    file_bytes = base64.b64decode(raw_data)
                    ext = os.path.splitext(orig_name)[1] or ".bin"
                    file_hash = hashlib.sha256(file_bytes[:1024] + str(time.time()).encode()).hexdigest()[:12]
                    safe_name = f"{file_hash}{ext}"
                    target_path = os.path.join(UPLOADS_DIR, safe_name)
                    with open(target_path, "wb") as f:
                        f.write(file_bytes)
                    url = f"/api/uploads/{safe_name}"
                    self.send_json({
                        "ok": True,
                        "url": url,
                        "filename": orig_name,
                        "safe_name": safe_name,
                        "type": content_type,
                        "size": len(file_bytes)
                    })
                except Exception as ex:
                    self.send_json({"ok": False, "error": f"Upload failed: {str(ex)}"}, 500)
                return

            elif path == "/api/workspace/save":
                rel_path = body.get("path", "").strip()
                content = body.get("content", "")
                if not rel_path:
                    self.send_json({"ok": False, "error": "Missing path"}, 400)
                    return
                full_path = os.path.abspath(os.path.join(WORKSPACE_ROOT, rel_path))
                if not full_path.startswith(WORKSPACE_ROOT):
                    self.send_json({"ok": False, "error": "Access denied"}, 403)
                    return
                try:
                    os.makedirs(os.path.dirname(full_path), exist_ok=True)
                    with open(full_path, "w", encoding="utf-8") as f:
                        f.write(content)
                    self.send_json({"ok": True, "path": rel_path, "size": len(content)})
                except Exception as ex:
                    self.send_json({"ok": False, "error": str(ex)}, 500)
                return

            elif path == "/api/workspace/diff":
                rel_path = body.get("path", "").strip()
                proposed = body.get("proposed_content") or body.get("content", "")
                if not rel_path:
                    self.send_json({"ok": False, "error": "Missing path"}, 400)
                    return
                full_path = os.path.abspath(os.path.join(WORKSPACE_ROOT, rel_path))
                existing = ""
                if os.path.exists(full_path) and os.path.isfile(full_path):
                    try:
                        with open(full_path, "r", encoding="utf-8", errors="replace") as f:
                            existing = f.read()
                    except Exception:
                        existing = ""
                diff_lines = list(difflib.unified_diff(
                    existing.splitlines(keepends=True),
                    proposed.splitlines(keepends=True),
                    fromfile=f"a/{rel_path}",
                    tofile=f"b/{rel_path}"
                ))
                additions = sum(1 for line in diff_lines if line.startswith("+") and not line.startswith("+++"))
                deletions = sum(1 for line in diff_lines if line.startswith("-") and not line.startswith("---"))
                self.send_json({
                    "ok": True,
                    "path": rel_path,
                    "diff": "".join(diff_lines),
                    "additions": additions,
                    "deletions": deletions,
                    "is_new": not os.path.exists(full_path)
                })
                return

            elif path == "/api/terminal/exec":
                cmd = body.get("command", "").strip()
                cwd_req = body.get("cwd", "").strip()
                exec_cwd = WORKSPACE_ROOT
                if cwd_req:
                    target_dir = os.path.abspath(os.path.join(WORKSPACE_ROOT, cwd_req))
                    if target_dir.startswith(WORKSPACE_ROOT) and os.path.isdir(target_dir):
                        exec_cwd = target_dir

                if not cmd:
                    self.send_json({"ok": False, "error": "Command string is required"}, 400)
                    return

                # Statefully handle directory changes (cd, chdir, set-location)
                cmd_lower = cmd.lower()
                if cmd_lower in ["cd", "cd ~", "cd /", "cd \\"]:
                    exec_cwd = WORKSPACE_ROOT
                    rel_cwd = ""
                    self.send_json({
                        "ok": True,
                        "command": cmd,
                        "cwd": rel_cwd,
                        "cwd_abs": exec_cwd,
                        "stdout": "",
                        "stderr": "",
                        "exit_code": 0
                    })
                    return
                elif cmd_lower.startswith("cd ") or cmd_lower.startswith("chdir ") or cmd_lower.startswith("set-location "):
                    parts = cmd.split(None, 1)
                    target_path = parts[1].strip().strip('"').strip("'") if len(parts) > 1 else ""
                    if not target_path or target_path in ["~", "/", "\\"]:
                        new_cwd = WORKSPACE_ROOT
                    elif target_path == "..":
                        parent = os.path.dirname(exec_cwd)
                        new_cwd = parent if parent.startswith(WORKSPACE_ROOT) else WORKSPACE_ROOT
                    else:
                        candidate = os.path.abspath(os.path.join(exec_cwd, target_path))
                        if candidate.startswith(WORKSPACE_ROOT) and os.path.isdir(candidate):
                            new_cwd = candidate
                        else:
                            rel_cur = os.path.relpath(exec_cwd, WORKSPACE_ROOT).replace("\\", "/")
                            self.send_json({
                                "ok": False,
                                "command": cmd,
                                "cwd": "" if rel_cur == "." else rel_cur,
                                "cwd_abs": exec_cwd,
                                "stderr": f"Cannot find path '{target_path}' because it does not exist.",
                                "exit_code": 1
                            })
                            return
                    exec_cwd = new_cwd
                    rel_cwd = os.path.relpath(exec_cwd, WORKSPACE_ROOT).replace("\\", "/")
                    if rel_cwd == ".":
                        rel_cwd = ""
                    self.send_json({
                        "ok": True,
                        "command": cmd,
                        "cwd": rel_cwd,
                        "cwd_abs": exec_cwd,
                        "stdout": "",
                        "stderr": "",
                        "exit_code": 0
                    })
                    return

                try:
                    shell_cmd = ["powershell", "-NoProfile", "-Command", cmd] if os.name == "nt" else ["/bin/bash", "-c", cmd]
                    proc = subprocess.run(
                        shell_cmd,
                        cwd=exec_cwd,
                        capture_output=True,
                        text=True,
                        timeout=30
                    )
                    rel_cwd = os.path.relpath(exec_cwd, WORKSPACE_ROOT).replace("\\", "/")
                    if rel_cwd == ".":
                        rel_cwd = ""
                    self.send_json({
                        "ok": True,
                        "command": cmd,
                        "cwd": rel_cwd,
                        "cwd_abs": exec_cwd,
                        "stdout": proc.stdout,
                        "stderr": proc.stderr,
                        "output": (proc.stdout or "") + (proc.stderr or ""),
                        "exit_code": proc.returncode,
                        "returncode": proc.returncode
                    })
                except subprocess.TimeoutExpired:
                    rel_cwd = os.path.relpath(exec_cwd, WORKSPACE_ROOT).replace("\\", "/")
                    if rel_cwd == ".":
                        rel_cwd = ""
                    self.send_json({
                        "ok": False,
                        "command": cmd,
                        "cwd": rel_cwd,
                        "cwd_abs": exec_cwd,
                        "error": "Command execution timed out (30s limit).",
                        "exit_code": -1
                    })
                except Exception as ex:
                    rel_cwd = os.path.relpath(exec_cwd, WORKSPACE_ROOT).replace("\\", "/")
                    if rel_cwd == ".":
                        rel_cwd = ""
                    self.send_json({
                        "ok": False,
                        "command": cmd,
                        "cwd": rel_cwd,
                        "cwd_abs": exec_cwd,
                        "error": str(ex),
                        "exit_code": -1
                    })
                return

            elif path == "/api/git/commit":
                msg = body.get("message", "").strip()
                if not msg:
                    msg = f"Update homelab workspace ({time.strftime('%Y-%m-%d %H:%M')})"
                try:
                    subprocess.run(["git", "add", "-A"], cwd=WORKSPACE_ROOT, check=True, capture_output=True)
                    proc = subprocess.run(["git", "commit", "-m", msg], cwd=WORKSPACE_ROOT, capture_output=True, text=True)
                    self.send_json({"ok": proc.returncode == 0, "message": msg, "output": proc.stdout or proc.stderr})
                except Exception as ge:
                    self.send_json({"ok": False, "error": str(ge)})
                return

            elif path == "/api/obsidian/sync_to_memory" or path == "/api/knowledge/sync":
                try:
                    res = obsidian_ingestor.sync_vault()
                    self.send_json({"ok": True, "result": res})
                except Exception as sync_err:
                    self.send_json({"ok": False, "error": str(sync_err)}, 500)
                return

            elif path == "/api/couchdb/sync":
                try:
                    notes = couchdb.list_notes()
                    self.send_json({"ok": True, "message": f"Polled CouchDB: {len(notes)} notes indexed.", "count": len(notes)})
                except Exception as ex:
                    self.send_json({"ok": False, "error": str(ex)}, 500)
                return

            elif path == "/api/obsidian/sync-archive":
                try:
                    def run_sync_task():
                        ps_script = os.path.join(WORKSPACE_ROOT, "server setup", "sync_archive_to_obsidian.ps1")
                        if os.path.exists(ps_script):
                            subprocess.run(["powershell", "-ExecutionPolicy", "Bypass", "-File", ps_script], capture_output=True)
                    threading.Thread(target=run_sync_task, daemon=True).start()
                    self.send_json({"ok": True, "message": "Obsidian archive sync initiated in background."})
                except Exception as ex:
                    self.send_json({"ok": False, "error": str(ex)}, 500)
                return

            elif path == "/api/memory/stm/add":
                category = body.get("category", "user")
                key = body.get("key", "Note")
                val = body.get("value", "")
                item = stm.add_item(category, key, val)
                self.send_json({"ok": True, "item": item, "stm": stm.get_summary()})
                return

            elif path == "/api/memory/stm/remove":
                item_id = body.get("id", "")
                removed = stm.remove_item(item_id)
                self.send_json({"ok": True, "removed": removed, "stm": stm.get_summary()})
                return

            elif path == "/api/memory/stm/clear":
                stm.clear()
                self.send_json({"ok": True, "stm": stm.get_summary()})
                return

            elif path == "/api/memory/stm/compress":
                text = body.get("text", "")
                summary = stm.compress_with_worker(text)
                self.send_json({"ok": True, "compressed": summary, "stm": stm.get_summary()})
                return

            elif path == "/api/planner/generate":
                goal = body.get("goal", "").strip()
                model = body.get("model", "coordinator")
                if not goal:
                    self.send_json({"ok": False, "error": "Goal description required"}, 400)
                    return

                plan_prompt = (
                    f"You are an expert AI Planner and Autonomous Agent Architect.\n"
                    f"Decompose the following high-level objective into a structured, executable finite instruction set.\n"
                    f"Format your response as a valid JSON object ONLY, with no markdown code fences, matching this schema:\n"
                    f"{{\n"
                    f'  "title": "<Brief title of task>",\n'
                    f'  "objective": "<Goal summary>",\n'
                    f'  "steps": [\n'
                    f'    {{"id": 1, "desc": "<Step 1 description>", "action": "<command or instruction>", "target": "<file or service>", "status": "pending"}},\n'
                    f'    {{"id": 2, "desc": "<Step 2 description>", "action": "<command or instruction>", "target": "<file or service>", "status": "pending"}}\n'
                    f'  ]\n'
                    f"}}\n\n"
                    f"OBJECTIVE: {goal}"
                )

                try:
                    chunks = []
                    for c in cluster.stream_chat(model, [{"role": "user", "content": plan_prompt}], {"max_tokens": 1500, "temperature": 0.2}):
                        if c.startswith("data: ") and "[DONE]" not in c:
                            try:
                                delta = json.loads(c[6:])["choices"][0]["delta"].get("content") or ""
                                chunks.append(delta)
                            except Exception:
                                pass
                    raw_res = "".join(chunks).strip()
                    clean_json = raw_res
                    if "```json" in clean_json:
                        clean_json = clean_json.split("```json", 1)[1].split("```", 1)[0].strip()
                    elif "```" in clean_json:
                        clean_json = clean_json.split("```", 1)[1].split("```", 1)[0].strip()

                    try:
                        plan_data = json.loads(clean_json)
                    except Exception:
                        plan_data = {
                            "title": goal[:40],
                            "objective": goal,
                            "steps": [
                                {"id": 1, "desc": "Analyze system requirements", "action": "inspect", "target": "workspace", "status": "pending"},
                                {"id": 2, "desc": "Execute implementation steps", "action": "code", "target": "StoneSage", "status": "pending"},
                                {"id": 3, "desc": "Verify with automated tests", "action": "verify", "target": "tests", "status": "pending"}
                            ]
                        }
                    stm.set_active_plan(plan_data)
                    self.send_json({"ok": True, "plan": plan_data})
                except Exception as e:
                    self.send_json({"ok": False, "error": str(e)}, 500)
                return

            elif path == "/api/planner/execute_step":
                step_id = body.get("step_id", 1)
                model = body.get("model", "worker")
                plan = stm.get_active_plan()
                if not plan:
                    self.send_json({"ok": False, "error": "No active plan found"}, 400)
                    return

                target_step = None
                for s in plan.get("steps", []):
                    if s.get("id") == step_id:
                        target_step = s
                        break

                if not target_step:
                    self.send_json({"ok": False, "error": f"Step {step_id} not found"}, 404)
                    return

                target_step["status"] = "running"
                exec_prompt = f"Execute milestone step: {target_step.get('desc')}. Action: {target_step.get('action')}. Target: {target_step.get('target')}. Report outcome concisely."
                try:
                    chunks = []
                    for c in cluster.stream_chat(model, [{"role": "user", "content": exec_prompt}], {"max_tokens": 800}):
                        if c.startswith("data: ") and "[DONE]" not in c:
                            try:
                                delta = json.loads(c[6:])["choices"][0]["delta"].get("content") or ""
                                chunks.append(delta)
                            except Exception:
                                pass
                    output = "".join(chunks).strip()
                    target_step["status"] = "completed"
                    target_step["output"] = output
                    stm.add_item("execution", f"Step_{step_id}", output[:150])
                    self.send_json({"ok": True, "step": target_step, "plan": plan})
                except Exception as e:
                    target_step["status"] = "failed"
                    target_step["error"] = str(e)
                    self.send_json({"ok": False, "error": str(e), "plan": plan})
                return

            elif path in ["/api/hass/call", "/api/ha/service"]:
                cluster.signal_preemption(reason="ha_service_call", in_flight=False)
                domain = body.get("domain", "")
                service = body.get("service", "")
                service_data = body.get("service_data", {})
                entity_id = str(service_data.get("entity_id", "")).lower()

                # CRITICAL SAFETY INVARIANT: Block power cuts to physical server infrastructure
                if domain in ["switch"] and service in ["turn_off", "toggle"]:
                    blocklist = ["server", "kp125", "nas", "pve", "bigserv", "router", "unsloth", "ubu"]
                    if any(b in entity_id for b in blocklist):
                        self.send_json({
                            "ok": False,
                            "error": f"SAFETY VIOLATION BLOCKED: Cannot cut power to server infrastructure ({entity_id})."
                        }, 403)
                        return

                res = hass.call_service(domain, service, service_data)
                self.send_json(res)
                return

            elif path in ("/api/chat", "/api/ai/chat_ollama"):
                # Official Ollama-compatible Chat API for Home Assistant & external agents
                cluster.signal_preemption(reason="ha_assist_ollama", in_flight=True)
                try:
                    req_model = body.get("model", "worker:latest").lower()
                    is_coord = "coordinator" in req_model or "14b" in req_model
                    target_base = cluster.coordinator_url if is_coord else cluster.worker_url
                    model_id = "coordinator" if is_coord else "worker"
                    messages = list(body.get("messages", []))
                    stream = body.get("stream", False)
                    tools = body.get("tools", [])
                    has_tools = bool(tools)

                    # Augment system instructions for tool calls if tools provided by HA Assist
                    if has_tools:
                        # Native tool-calling format is handled by llama-server jinja template
                        pass

                    forward_body = {
                        "model": model_id,
                        "messages": messages,
                        "temperature": 0.2 if has_tools else 0.7,
                        "stream": stream,
                        "max_tokens": 800
                    }
                    if has_tools:
                        forward_body["tools"] = tools

                    fwd_payload = json.dumps(forward_body).encode("utf-8")
                    print(f"[StoneSage] /api/chat fwd: model={model_id}, stream={stream}, tools={has_tools}, payload_len={len(fwd_payload)}", file=sys.stderr)
                    fwd_req = urllib.request.Request(
                        f"{target_base}/chat/completions",
                        data=fwd_payload,
                        headers={"Content-Type": "application/json"},
                        method="POST"
                    )

                    iso_now = datetime.now(timezone.utc).isoformat()

                    if stream:
                        self.send_response(200)
                        self.send_header("Content-Type", "application/x-ndjson; charset=utf-8")
                        self.send_header("Cache-Control", "no-cache")
                        self.send_header("Connection", "close")
                        self.send_header("Access-Control-Allow-Origin", "*")
                        self.end_headers()

                        with urllib.request.urlopen(fwd_req, timeout=60) as resp:
                            full_text = ""
                            for line in resp:
                                l_str = line.decode("utf-8", errors="ignore").strip()
                                if l_str.startswith("data: ") and l_str != "data: [DONE]":
                                    try:
                                        chunk_json = json.loads(l_str[6:])
                                        delta = chunk_json.get("choices", [{}])[0].get("delta", {}).get("content") or ""
                                        if delta:
                                            full_text += delta
                                            chunk_out = {
                                                "model": req_model,
                                                "created_at": iso_now,
                                                "message": {"role": "assistant", "content": delta},
                                                "done": False
                                            }
                                            self.wfile.write((json.dumps(chunk_out) + "\n").encode("utf-8"))
                                            self.wfile.flush()
                                    except Exception:
                                        pass

                            # Check for tool call in completed response
                            t_name, t_args = extract_tool_call(full_text)
                            if t_name:
                                done_out = {
                                    "model": req_model,
                                    "created_at": iso_now,
                                    "message": {
                                        "role": "assistant",
                                        "content": "",
                                        "tool_calls": [{
                                            "function": {
                                                "name": t_name,
                                                "arguments": t_args
                                            }
                                        }]
                                    },
                                    "done": True,
                                    "done_reason": "tool_calls"
                                }
                            else:
                                done_out = {
                                    "model": req_model,
                                    "created_at": iso_now,
                                    "message": {"role": "assistant", "content": ""},
                                    "done": True,
                                    "done_reason": "stop"
                                }
                            self.wfile.write((json.dumps(done_out) + "\n").encode("utf-8"))
                            self.wfile.flush()
                    else:
                        with urllib.request.urlopen(fwd_req, timeout=60) as resp:
                            res_json = json.loads(resp.read().decode("utf-8"))
                            choice = res_json.get("choices", [{}])[0]
                            content = choice.get("message", {}).get("content") or ""
                            t_name, t_args = extract_tool_call(content)
                            if t_name:
                                ollama_res = {
                                    "model": req_model,
                                    "created_at": iso_now,
                                    "message": {
                                        "role": "assistant",
                                        "content": "",
                                        "tool_calls": [{
                                            "function": {
                                                "name": t_name,
                                                "arguments": t_args
                                            }
                                        }]
                                    },
                                    "done": True
                                }
                            else:
                                ollama_res = {
                                    "model": req_model,
                                    "created_at": iso_now,
                                    "message": {
                                        "role": "assistant",
                                        "content": content
                                    },
                                    "done": True
                                }
                            self.send_json(ollama_res)
                except Exception as ex:
                    print(f"[StoneSage] Error in /api/chat: {ex}", file=sys.stderr)
                    if hasattr(ex, 'read'):
                        try:
                            print(f"[StoneSage] Backend response: {ex.read().decode('utf-8', errors='ignore')}", file=sys.stderr)
                        except Exception:
                            pass
                    self.send_json({"error": str(ex)}, 500)
                finally:
                    cluster.signal_preemption(reason="ha_assist_done", in_flight=False)
                return

            elif path == "/api/preemption/signal":
                reason = body.get("reason", "interactive_user")
                in_flight = body.get("in_flight", False)
                res = cluster.signal_preemption(reason=reason, in_flight=in_flight)
                self.send_json(res)
                return

            # ── Transparent Proxy: OpenAI-compatible /chat/completions (Coordinator & Worker) ──
            elif path in ("/api/ai/coordinator/v1/chat/completions", "/api/ai/worker/v1/chat/completions"):
                is_worker = "worker" in path
                default_model = "worker" if is_worker else "coordinator"
                cluster.signal_preemption(reason=f"proxy_{default_model}", in_flight=True)
                target_base = cluster.worker_url if is_worker else cluster.coordinator_url
                model_header_name = "worker-3b" if is_worker else "coordinator-14b-rag"
                messages = list(body.get("messages", []))
                stream = body.get("stream", False)

                # Extract last user message safely (handles str or list of dicts)
                def extract_text_content(val) -> str:
                    if isinstance(val, str):
                        return val
                    elif isinstance(val, list):
                        parts = []
                        for item in val:
                            if isinstance(item, str):
                                parts.append(item)
                            elif isinstance(item, dict) and "text" in item:
                                parts.append(str(item.get("text", "")))
                        return " ".join(parts)
                    return str(val or "")

                last_user_msg = ""
                for m in reversed(messages):
                    if m.get("role") == "user":
                        last_user_msg = extract_text_content(m.get("content")).strip()
                        break

                # RAG augmentation: ONLY for coordinator when query explicitly requests knowledge
                # Worker intentionally skips RAG to maintain sub-2-second voice execution
                if not is_worker and last_user_msg and len(last_user_msg) > 15:
                    try:
                        query_text = last_user_msg[:300]
                        obsidian_hits = cluster.search_hybrid(
                            query_text, collection_name="obsidian_vault", limit=3
                        )
                        codebase_hits = cluster.search_memory(
                            query_text, collection_name="codebase_knowledge", limit=2
                        )
                        all_hits = (obsidian_hits or []) + (codebase_hits or [])

                        if all_hits:
                            snippets = []
                            for pt in all_hits:
                                payload = pt.get("payload", {})
                                title = payload.get("title") or payload.get("path") or "Reference"
                                content = payload.get("content") or payload.get("text") or ""
                                score = pt.get("score", 0)
                                src = "obsidian" if pt in (obsidian_hits or []) else "codebase"
                                if content and content.strip():
                                    snippets.append(
                                        f"[{title}] (source: {src}, relevance: {score:.2f}):\n"
                                        f"{content.strip()[:500]}"
                                    )

                            if snippets:
                                dossier = "\n\n".join(snippets)
                                rag_block = (
                                    "\n\n[RETRIEVED KNOWLEDGE DOSSIER]\n"
                                    "The following context was automatically retrieved from the user's "
                                    "personal Obsidian vault and homelab codebase knowledge base. "
                                    "Reference it when relevant to the conversation.\n\n"
                                    f"{dossier}\n"
                                    "[END KNOWLEDGE DOSSIER]"
                                )

                                # Inject into first system message, or create one
                                augmented = []
                                injected = False
                                for m in messages:
                                    if m.get("role") == "system" and not injected:
                                        sys_orig = m.get("content")
                                        if isinstance(sys_orig, list):
                                            sys_aug = list(sys_orig) + [{"type": "text", "text": rag_block}]
                                        else:
                                            sys_aug = str(sys_orig or "") + rag_block
                                        augmented.append({
                                            "role": "system",
                                            "content": sys_aug
                                        })
                                        injected = True
                                    else:
                                        augmented.append(dict(m))
                                if not injected:
                                    augmented.insert(0, {
                                        "role": "system",
                                        "content": (
                                            "You are a knowledgeable AI assistant integrated with "
                                            "the user's smart home and homelab infrastructure."
                                            + rag_block
                                        )
                                    })
                                messages = augmented
                    except Exception:
                        pass  # Graceful degradation: forward without RAG context

                has_tools = bool(body.get("tools"))

                # Worker optimization: ensure 3B model fills in required parameters when calling tools
                if is_worker and has_tools:
                    worker_rule = (
                        "\n\n[TOOL CALLING RULE]\n"
                        "When calling a function, you MUST fill in all required arguments in the JSON object.\n"
                        "Example: {\"name\": \"GetLiveContext\", \"arguments\": {\"name\": \"living_room_lamp\"}}.\n"
                        "Never leave arguments empty.\n"
                    )
                    augmented = []
                    injected = False
                    for m in messages:
                        if m.get("role") == "system" and not injected:
                            s_content = m.get("content")
                            if isinstance(s_content, list):
                                augmented.append({"role": "system", "content": list(s_content) + [{"type": "text", "text": worker_rule}]})
                            else:
                                augmented.append({"role": "system", "content": str(s_content or "") + worker_rule})
                            injected = True
                        else:
                            augmented.append(dict(m))
                    if not injected:
                        augmented.insert(0, {"role": "system", "content": worker_rule.strip()})
                # System prompt instruction: query Qdrant skills at minimal token cost
                skill_prompt_directive = (
                    "\n\n[SKILL & KNOWLEDGE RETRIEVAL DIRECTIVE]\n"
                    "All specialized operational skills, homelab procedures, and device configurations are indexed in Qdrant collection 'codebase_knowledge'. "
                    "When a request requires specialized execution rules, retrieve them on-demand via search_memory with concise keywords. "
                    "Pull only specific functional chunks to conserve context and tokens."
                )
                augmented_skills = []
                skill_injected = False
                for m in messages:
                    if m.get("role") == "system" and not skill_injected:
                        s_content = m.get("content")
                        if isinstance(s_content, list):
                            augmented_skills.append({"role": "system", "content": list(s_content) + [{"type": "text", "text": skill_prompt_directive}]})
                        else:
                            augmented_skills.append({"role": "system", "content": str(s_content or "") + skill_prompt_directive})
                        skill_injected = True
                    else:
                        augmented_skills.append(dict(m))
                if not skill_injected:
                    augmented_skills.insert(0, {"role": "system", "content": skill_prompt_directive.strip()})
                messages = augmented_skills

                # Build forwarded payload — preserve all original fields
                forward_body = dict(body)
                forward_body["messages"] = messages
                forward_body.setdefault("model", default_model)
                forward_body.setdefault("presence_penalty", 0.3)
                forward_body.setdefault("repeat_penalty", 1.15)
                forward_body.setdefault("dry_multiplier", 0.8)
                if forward_body.get("max_tokens", 0) > 1500:
                    forward_body["max_tokens"] = 1500

                target_url = f"{target_base}/chat/completions"
                payload_bytes = json.dumps(forward_body).encode("utf-8")
                fwd_req = urllib.request.Request(
                    target_url,
                    data=payload_bytes,
                    headers={"Content-Type": "application/json"},
                    method="POST"
                )

                if stream:
                    # Streaming SSE pass-through with native OpenAI tool-call translation
                    self.send_response(200)
                    self.send_header("Content-Type", "text/event-stream; charset=utf-8")
                    self.send_header("Cache-Control", "no-cache")
                    self.send_header("Connection", "close")
                    self.send_header("Access-Control-Allow-Origin", "*")
                    self.end_headers()
                    try:
                        with urllib.request.urlopen(fwd_req, timeout=180) as resp:
                            if has_tools:
                                # When client supports tools, buffer stream to intercept any tool calls in content
                                raw_lines = []
                                full_text = ""
                                chunk_id = "chatcmpl-" + str(int(time.time()))
                                created_ts = int(time.time())
                                for line in resp:
                                    raw_lines.append(line)
                                    line_str = line.decode("utf-8", errors="ignore").strip()
                                    if line_str.startswith("data: ") and line_str != "data: [DONE]":
                                        try:
                                             cj = json.loads(line_str[6:])
                                             chunk_id = cj.get("id", chunk_id)
                                             created_ts = cj.get("created", created_ts)
                                             d = cj.get("choices", [{}])[0].get("delta", {})
                                             c = d.get("content")
                                             if c:
                                                 full_text += c
                                        except Exception:
                                             pass

                                # Check if full_text contains a tool call
                                tool_name, tool_args = extract_tool_call(full_text)
                                print(f"[{default_model}] tool={tool_name} args={tool_args} text={repr(full_text[:120])}", flush=True)
                                if tool_name:
                                    # Emit native OpenAI tool_calls SSE chunks
                                    call_id = f"call_{int(time.time())}"
                                    tool_delta = {
                                        "id": chunk_id,
                                        "object": "chat.completion.chunk",
                                        "created": created_ts,
                                        "model": model_header_name,
                                        "choices": [{
                                            "index": 0,
                                            "delta": {
                                                "role": "assistant",
                                                "tool_calls": [{
                                                    "index": 0,
                                                    "id": call_id,
                                                    "type": "function",
                                                    "function": {
                                                        "name": tool_name,
                                                        "arguments": json.dumps(tool_args)
                                                    }
                                                }]
                                            },
                                            "finish_reason": None
                                        }]
                                    }
                                    finish_delta = {
                                        "id": chunk_id,
                                        "object": "chat.completion.chunk",
                                        "created": created_ts,
                                        "model": model_header_name,
                                        "choices": [{
                                            "index": 0,
                                            "delta": {},
                                            "finish_reason": "tool_calls"
                                        }]
                                    }
                                    self.wfile.write(f"data: {json.dumps(tool_delta)}\n\n".encode("utf-8"))
                                    self.wfile.write(f"data: {json.dumps(finish_delta)}\n\n".encode("utf-8"))
                                    self.wfile.write(b"data: [DONE]\n\n")
                                    self.wfile.flush()
                                else:
                                    # Normal conversation/speech — forward buffered lines
                                    for l in raw_lines:
                                        self.wfile.write(l)
                                    self.wfile.flush()
                            else:
                                for line in resp:
                                    self.wfile.write(line)
                                    self.wfile.flush()
                    except Exception as e:
                        err_chunk = f'data: {json.dumps({"error": {"message": str(e)}})}\n\n'
                        self.wfile.write(err_chunk.encode("utf-8"))
                        self.wfile.flush()
                else:
                    # Non-streaming JSON pass-through with tool_call translation
                    try:
                        with urllib.request.urlopen(fwd_req, timeout=180) as resp:
                            data = resp.read()
                            if has_tools:
                                try:
                                    res_obj = json.loads(data.decode("utf-8"))
                                    content = res_obj.get("choices", [{}])[0].get("message", {}).get("content", "")
                                    t_name, t_args = extract_tool_call(content)
                                    if t_name:
                                        call_id = f"call_{int(time.time())}"
                                        res_obj["choices"][0]["message"]["content"] = None
                                        res_obj["choices"][0]["message"]["tool_calls"] = [{
                                            "index": 0,
                                            "id": call_id,
                                            "type": "function",
                                            "function": {
                                                "name": t_name,
                                                "arguments": json.dumps(t_args)
                                            }
                                        }]
                                        res_obj["choices"][0]["finish_reason"] = "tool_calls"
                                        data = json.dumps(res_obj).encode("utf-8")
                                except Exception:
                                    pass
                            self.send_response(200)
                            self.send_header("Content-Type", "application/json; charset=utf-8")
                            self.send_header("Access-Control-Allow-Origin", "*")
                            self.send_header("Content-Length", str(len(data)))
                            self.end_headers()
                            self.wfile.write(data)
                    except urllib.error.HTTPError as he:
                        err_body = he.read().decode("utf-8", errors="replace")
                        self.send_json({
                            "error": {"message": f"{default_model.capitalize()} returned {he.code}: {err_body}", "type": "upstream_error"}
                        }, he.code)
                    except Exception as e:
                        self.send_json({
                            "error": {"message": str(e), "type": "proxy_error"}
                        }, 502)
                return

            self.send_json({"error": "Unknown endpoint"}, 404)
        except Exception as e:
            traceback.print_exc()
            self.send_json({"ok": False, "error": str(e), "traceback": traceback.format_exc()}, 500)

if __name__ == "__main__":
    port = int(config.get("server", {}).get("port", 8080))
    host = config.get("server", {}).get("host", "0.0.0.0")

    http.server.ThreadingHTTPServer.allow_reuse_address = True
    try:
        server = http.server.ThreadingHTTPServer((host, port), StoneSageHandler)
    except OSError as e:
        if getattr(e, 'winerror', None) == 10048 or getattr(e, 'errno', None) in (48, 98):
            print(f"\n[!] Port {port} is already in use by another instance or process.")
            print(f"    StoneSage is already active at http://localhost:{port}")
            print(f"    To force restart, run start.bat which will automatically free the port.")
            sys.exit(1)
        raise
    lan_ip = config.get("server", {}).get("lan_ip", "127.0.0.1")
    print("=" * 68)
    print("  [ STONESAGE COGNITIVE TERMINAL WORKSTATION v3.0 ]")
    print(f"  Local Browser:     http://localhost:{port} (or http://127.0.0.1:{port})")
    print(f"  LAN Workstation:   http://{lan_ip}:{port}")
    print(f"  Cluster Nodes:     pve (127.0.0.1) & bigserv (127.0.0.1)")
    print(f"  Dual-GPU Cluster:  14B Coord (:8001/Vulkan0) & 3B Worker (:8002/Vulkan1)")
    print(f"  RAG Proxy (HA):    http://{lan_ip}:{port}/api/ai/coordinator/v1")
    print(f"  Qdrant Memory:     127.0.0.1:6333 (User Obsidian Ingested)")
    print(f"  Home Assistant:    http://127.0.0.1:8123")
    print("=" * 68)
    print("=" * 65)

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping StoneSage server...")
        server.server_close()

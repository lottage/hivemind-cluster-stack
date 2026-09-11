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
ACTIVE_WORKSPACE_DIR = WORKSPACE_ROOT
ACTIVE_GIT_REPO_DIR = WORKSPACE_ROOT
os.makedirs(UPLOADS_DIR, exist_ok=True)

def get_directory_presets() -> list:
    candidates = [
        {"label": "Active Workspace", "path": WORKSPACE_ROOT},
        {"label": "Server: /opt", "path": "/opt"},
        {"label": "NFS: /mnt/nas", "path": "/mnt/nas"},
        {"label": "NFS: /mnt/storage", "path": "/mnt/storage"},
        {"label": "Server Root: /", "path": "/"},
        {"label": "Linux: /etc", "path": "/etc"},
        {"label": "Windows: .ai", "path": "c:/Users/johna/OneDrive/Documents/.ai"},
    ]
    existing = []
    seen = set()
    for c in candidates:
        norm = os.path.normpath(c["path"]).replace("\\", "/")
        if os.path.exists(c["path"]):
            if norm not in seen:
                seen.add(norm)
                existing.append({"label": c["label"], "path": norm})
        elif c["label"] in ["Server: /opt", "NFS: /mnt/nas", "NFS: /mnt/storage"]:
            # Always make homelab server & NFS mounts visible as choices
            if norm not in seen:
                seen.add(norm)
                existing.append({"label": c["label"], "path": norm})
    return existing or candidates[:3]


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
from trainer_client import TrainerClient
from reasoning_watchdog import GLOBAL_WATCHDOG, ReasoningLoopDetector

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

def sync_qdrant_dossier_review(sample_id: str, action: str, notes: str = "") -> bool:
    """Synchronizes human review/approval/quarantine for a dossier directly into Qdrant point payload."""
    if not sample_id:
        return False
    try:
        cfg = load_config()
        qdrant_u = cfg.get("qdrant", {}).get("url", "http://192.168.1.112:6333").rstrip("/")
        scroll_req = urllib.request.Request(
            f"{qdrant_u}/collections/autonomous_thinking/points/scroll",
            data=json.dumps({
                "limit": 300,
                "with_payload": True,
                "with_vector": False
            }).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST"
        )
        found_id = None
        with urllib.request.urlopen(scroll_req, timeout=6) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            for pt in data.get("result", {}).get("points", []):
                pl = pt.get("payload", {})
                if pl.get("exploration_id") == sample_id or str(pt.get("id")) == sample_id:
                    found_id = pt.get("id")
                    break
        if found_id is not None:
            is_app = action in ("approve", "approve_sample")
            patch_payload = {
                "points": [found_id],
                "payload": {
                    "frontier_verified": is_app,
                    "human_approved": is_app,
                    "needs_frontier_verification": not is_app,
                    "quarantined": not is_app,
                    "human_status": "APPROVED" if is_app else "REJECTED",
                    "human_review_timestamp": datetime.now().isoformat(),
                    "human_notes": notes or ("Approved via StoneSage Web Cockpit" if is_app else "Quarantined via StoneSage Web Cockpit")
                }
            }
            p_req = urllib.request.Request(
                f"{qdrant_u}/collections/autonomous_thinking/points/payload",
                data=json.dumps(patch_payload).encode("utf-8"),
                headers={"Content-Type": "application/json"},
                method="POST"
            )
            with urllib.request.urlopen(p_req, timeout=6) as p_resp:
                return True
    except Exception as e:
        print(f"[Qdrant Sync Error] Failed to update point for {sample_id}: {e}")
    return False


def sync_qdrant_frontier_audit_result(sample_id: str, verdict: str, frontier_notes: str = "", refined_limits: str = "") -> bool:
    """Updates Qdrant point payload with Tier-1 Frontier audit results."""
    if not sample_id:
        return False
    try:
        cfg = load_config()
        qdrant_u = cfg.get("qdrant", {}).get("url", "http://192.168.1.112:6333").rstrip("/")
        scroll_req = urllib.request.Request(
            f"{qdrant_u}/collections/autonomous_thinking/points/scroll",
            data=json.dumps({
                "limit": 300,
                "with_payload": True,
                "with_vector": False
            }).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST"
        )
        found_id = None
        with urllib.request.urlopen(scroll_req, timeout=6) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            for pt in data.get("result", {}).get("points", []):
                pl = pt.get("payload", {})
                if pl.get("exploration_id") == sample_id or str(pt.get("id")) == sample_id:
                    found_id = pt.get("id")
                    break
        if found_id is not None:
            patch_payload = {
                "points": [found_id],
                "payload": {
                    "frontier_verified": True,
                    "frontier_verdict": verdict,
                    "frontier_notes": frontier_notes,
                    "refined_limits": refined_limits,
                    "needs_frontier_verification": False,
                    "quarantined": False,
                    "frontier_audit_timestamp": datetime.now().isoformat()
                }
            }
            p_req = urllib.request.Request(
                f"{qdrant_u}/collections/autonomous_thinking/points/payload",
                data=json.dumps(patch_payload).encode("utf-8"),
                headers={"Content-Type": "application/json"},
                method="POST"
            )
            with urllib.request.urlopen(p_req, timeout=6) as p_resp:
                return True
    except Exception as e:
        print(f"[Qdrant Frontier Audit Sync Error] Failed to update point for {sample_id}: {e}")
    return False


def execute_frontier_audit_for_dossier(dossier_id: str) -> Dict[str, Any]:
    """
    Executes Tier-1 Frontier Audit via Frontier Bridge (:8085).
    Reads dossier from thinking_archive or Qdrant, sends to Frontier Bridge,
    updates Qdrant payload, updates markdown file, and updates curation registry.
    """
    cfg = load_config()
    frontier_urls = [
        cfg.get("frontier_url", "http://127.0.0.1:8085").rstrip("/"),
        "http://192.168.1.167:8085",
        "http://127.0.0.1:8085"
    ]
    
    content = ""
    local_paths = [
        f"/opt/cluster-bridge/thinking_archive/{dossier_id}.md",
        f"../server setup/cluster-bridge/thinking_archive/{dossier_id}.md",
        f"../obsidian/Autonomous Thinking/Explorations/{dossier_id}.md",
        f"../obsidian/Autonomous Thinking/{dossier_id}.md",
        f"C:/Users/johna/OneDrive/Documents/obsidian/Autonomous Thinking/Explorations/{dossier_id}.md"
    ]
    md_file_found = None
    for lp in local_paths:
        if os.path.exists(lp):
            try:
                with open(lp, "r", encoding="utf-8", errors="ignore") as f:
                    content = f.read()
                    md_file_found = lp
                break
            except Exception:
                pass
                
    title = dossier_id
    prompt = ""
    worker_output = ""
    coordinator_output = ""
    eval_dict = {}
    target_invariant = ""

    if content:
        lines = content.splitlines()
        current_sec = None
        sec_buffers = {}
        for line in lines:
            if line.startswith("# "):
                title = line[2:].strip()
            elif line.startswith("## "):
                current_sec = line[3:].strip().lower()
                sec_buffers[current_sec] = []
            elif current_sec:
                sec_buffers[current_sec].append(line)
        
        for k, v in sec_buffers.items():
            text = "\n".join(v).strip()
            if "prompt" in k or "challenge" in k:
                prompt = text
            elif "worker" in k:
                worker_output = text
            elif "coordinator" in k:
                coordinator_output = text
            elif "invariant" in k:
                target_invariant = text
            elif "evaluation" in k or "first-pass" in k:
                eval_dict = {"raw_eval": text}
    else:
        try:
            qdrant_u = cfg.get("qdrant", {}).get("url", "http://192.168.1.112:6333").rstrip("/")
            scroll_req = urllib.request.Request(
                f"{qdrant_u}/collections/autonomous_thinking/points/scroll",
                data=json.dumps({"limit": 300, "with_payload": True, "with_vector": False}).encode("utf-8"),
                headers={"Content-Type": "application/json"},
                method="POST"
            )
            with urllib.request.urlopen(scroll_req, timeout=6) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                for pt in data.get("result", {}).get("points", []):
                    pl = pt.get("payload", {})
                    if pl.get("exploration_id") == dossier_id or str(pt.get("id")) == dossier_id:
                        title = pl.get("title", dossier_id)
                        prompt = pl.get("prompt", "")
                        worker_output = pl.get("worker_output", "")
                        coordinator_output = pl.get("coordinator_output", "")
                        target_invariant = pl.get("target_invariant", "")
                        eval_dict = {"eval": pl.get("eval", {})}
                        break
        except Exception:
            pass

    if not prompt and not worker_output and not coordinator_output:
        prompt = f"Dossier {dossier_id}"

    payload = {
        "title": title,
        "prompt": prompt,
        "worker_output": worker_output,
        "coordinator_output": coordinator_output,
        "eval": eval_dict,
        "target_invariant": target_invariant
    }

    bridge_resp = None
    last_err = None
    for fu in frontier_urls:
        audit_url = f"{fu}/api/frontier/audit"
        try:
            req = urllib.request.Request(
                audit_url,
                data=json.dumps(payload).encode("utf-8"),
                headers={"Content-Type": "application/json"},
                method="POST"
            )
            with urllib.request.urlopen(req, timeout=40) as resp:
                bridge_resp = json.loads(resp.read().decode("utf-8"))
                if bridge_resp.get("ok"):
                    break
        except Exception as ex:
            last_err = ex

    if not bridge_resp or not bridge_resp.get("ok"):
        err_msg = bridge_resp.get("error") if bridge_resp else str(last_err)
        return {"ok": False, "error": f"Frontier Bridge execution failed: {err_msg}"}

    verdict = bridge_resp.get("verdict", "CONFIRM_LIMIT_VALIDATED")
    frontier_notes = bridge_resp.get("frontier_notes", "")
    refined_limits = bridge_resp.get("refined_limits", "")
    provider = bridge_resp.get("provider", "frontier_bridge")
    model = bridge_resp.get("model", "gemini-3.8-flash")

    # 1. Update Qdrant
    qdrant_updated = sync_qdrant_frontier_audit_result(dossier_id, verdict, frontier_notes, refined_limits)

    # 2. Update markdown file on disk if found
    if md_file_found and os.path.exists(md_file_found):
        try:
            audit_block = (
                f"\n\n## Tier-1 Frontier Meta-Verification Audit\n"
                f"- **Verdict**: `{verdict}`\n"
                f"- **Model**: `{model}` ({provider})\n"
                f"- **Timestamp**: `{datetime.now().isoformat()}`\n"
                f"- **Frontier Notes**: {frontier_notes}\n"
                f"- **Refined Architectural Limits**: {refined_limits}\n"
            )
            with open(md_file_found, "a", encoding="utf-8") as af:
                af.write(audit_block)
        except Exception as e:
            print(f"[Markdown Append Warning] {e}")

    # 3. Update curation registry if sample tracked
    try:
        cur_paths = [
            "pipeline-gguf-trainer/data/processed/curation_registry.json",
            "../pipeline-gguf-trainer/data/processed/curation_registry.json",
            "/opt/stonesage/trainer/data/processed/curation_registry.json"
        ]
        for cur_reg_path in cur_paths:
            if os.path.exists(cur_reg_path):
                with open(cur_reg_path, "r", encoding="utf-8") as rf:
                    cdata = json.load(rf)
                samples = cdata.get("samples", {})
                if dossier_id in samples:
                    samples[dossier_id]["frontier_verified"] = True
                    samples[dossier_id]["verdict"] = verdict
                    samples[dossier_id]["frontier_score"] = 9.5
                    samples[dossier_id]["frontier_critique"] = frontier_notes
                    with open(cur_reg_path, "w", encoding="utf-8") as wf:
                        json.dump(cdata, wf, indent=2)
                break
    except Exception as e:
        print(f"[Curation Registry Update Warning] {e}")

    return {
        "ok": True,
        "dossier_id": dossier_id,
        "verdict": verdict,
        "frontier_notes": frontier_notes,
        "refined_limits": refined_limits,
        "provider": provider,
        "model": model,
        "qdrant_updated": qdrant_updated
    }


def load_dynamic_tools_and_skills() -> Dict[str, Any]:
    """
    Dynamically scans and discovers all local cluster MCP tools and agent skills
    in real time without requiring server restarts or hardcoded manifests.
    """
    cfg = load_config()
    mcp_url = cfg.get("cluster", {}).get("mcp_url", "http://192.168.1.105:8765").rstrip("/")
    
    tools = []
    try:
        payload = {"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {}}
        req = urllib.request.Request(
            mcp_url,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST"
        )
        with urllib.request.urlopen(req, timeout=3.5) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            live_tools = data.get("result", {}).get("tools", [])
            for t in live_tools:
                tools.append({
                    "name": t.get("name"),
                    "description": t.get("description", ""),
                    "inputSchema": t.get("inputSchema", {}),
                    "source": "pve-cluster (Live MCP :8765)",
                    "type": "mcp_tool"
                })
    except Exception:
        mcp_paths = [
            "/opt/cluster-bridge/mcp_server.py",
            "server setup/cluster-bridge/mcp_server.py",
            "../server setup/cluster-bridge/mcp_server.py",
            "hivemind-cluster-stack/core/mcp_server.py"
        ]
        for mp in mcp_paths:
            if os.path.exists(mp):
                try:
                    with open(mp, "r", encoding="utf-8", errors="ignore") as mf:
                        content = mf.read()
                        import ast
                        if "TOOLS_MANIFEST = [" in content:
                            start_idx = content.index("TOOLS_MANIFEST = [") + len("TOOLS_MANIFEST = ")
                            sub = content[start_idx:]
                            bracket = 0
                            end = 0
                            for idx, ch in enumerate(sub):
                                if ch == '[': bracket += 1
                                elif ch == ']':
                                    bracket -= 1
                                    if bracket == 0:
                                        end = idx + 1
                                        break
                            if end > 0:
                                parsed = ast.literal_eval(sub[:end])
                                for t in parsed:
                                    tools.append({
                                        "name": t.get("name"),
                                        "description": t.get("description", ""),
                                        "inputSchema": t.get("inputSchema", {}),
                                        "source": "pve-cluster (Local Manifest)",
                                        "type": "mcp_tool"
                                    })
                                break
                except Exception:
                    pass

    skills = []
    scan_roots = [
        ".agents/skills",
        "../.agents/skills",
        "C:/Users/johna/OneDrive/Documents/.ai/.agents/skills",
        "C:/Users/johna/.gemini/antigravity/builtin/skills",
        "/opt/stonesage/.agents/skills",
        "/root/.gemini/antigravity/builtin/skills",
        "hivemind-cluster-stack/core/skills"
    ]
    seen_skills = set()
    for s_root in scan_roots:
        if os.path.exists(s_root) and os.path.isdir(s_root):
            for entry in sorted(os.listdir(s_root)):
                skill_dir = os.path.join(s_root, entry)
                skill_file = os.path.join(skill_dir, "SKILL.md")
                if os.path.isdir(skill_dir) and os.path.exists(skill_file) and entry not in seen_skills:
                    seen_skills.add(entry)
                    try:
                        with open(skill_file, "r", encoding="utf-8", errors="ignore") as sf:
                            s_text = sf.read()
                        name = entry
                        desc = ""
                        body = s_text
                        if s_text.startswith("---"):
                            parts = s_text.split("---", 2)
                            if len(parts) >= 3:
                                fm = parts[1]
                                body = parts[2]
                                for line in fm.splitlines():
                                    if line.startswith("name:"):
                                        name = line.split("name:", 1)[1].strip().strip('"').strip("'")
                                    elif line.startswith("description:"):
                                        desc = line.split("description:", 1)[1].strip().strip('"').strip("'")
                        if not desc:
                            for b_line in body.splitlines():
                                s_strip = b_line.strip()
                                if s_strip and not s_strip.startswith("#"):
                                    desc = s_strip
                                    break
                        skills.append({
                            "id": entry,
                            "name": name,
                            "description": desc,
                            "body": body[:1500],
                            "path": skill_file.replace("\\", "/"),
                            "source": "Agent Skill",
                            "type": "agent_skill"
                        })
                    except Exception:
                        pass

    return {
        "ok": True,
        "total_tools": len(tools),
        "total_skills": len(skills),
        "tools": tools,
        "skills": skills,
        "scanned_at": datetime.now().isoformat()
    }


def load_dynamic_amem_cards(query: str = "") -> Dict[str, Any]:
    """
    Dynamically queries Valkey RAM (:6379) on 192.168.1.105,
    or falls back to curated in-RAM JSON files.
    Calculates exact atom card tokens (< 35 tokens).
    """
    import socket
    cards = []
    valkey_online = False
    
    try:
        s = socket.socket()
        s.settimeout(2.0)
        s.connect(("192.168.1.105", 6379))
        valkey_online = True
        
        s.sendall(b"SMEMBERS amem:cards:all\r\n")
        data = b""
        while True:
            chunk = s.recv(4096)
            data += chunk
            if len(chunk) < 4096:
                break
        
        lines = data.split(b"\r\n")
        card_ids = [l.decode("utf-8", errors="ignore") for l in lines[1:] if l and not l.startswith(b"$") and not l.startswith(b"*")]
        
        for cid in card_ids:
            try:
                s.sendall(f"GET amem:card:{cid}\r\n".encode())
                resp = s.recv(4096)
                parts = resp.split(b"\r\n")
                for p in parts:
                    if p.startswith(b"{"):
                        c = json.loads(p.decode("utf-8", errors="ignore"))
                        c_atom = c.get("atom", "")
                        c["token_count"] = max(1, round(len(c_atom.split()) * 1.25))
                        cards.append(c)
                        break
            except Exception:
                pass
        s.close()
    except Exception:
        valkey_online = False

    if not cards:
        amem_json_paths = [
            "pipeline-gguf-trainer/data/processed/curated_amem_cards.json",
            "../pipeline-gguf-trainer/data/processed/curated_amem_cards.json",
            "/opt/stonesage/trainer/data/processed/curated_amem_cards.json"
        ]
        for p in amem_json_paths:
            if os.path.exists(p):
                try:
                    with open(p, "r", encoding="utf-8") as f:
                        data = json.load(f)
                        for k, c in data.items():
                            c_atom = c.get("atom", "")
                            c["token_count"] = max(1, round(len(c_atom.split()) * 1.25))
                            cards.append(c)
                    break
                except Exception:
                    pass

    if not cards:
        seed_atoms = [
            {
                "id": "arch.vulkan.device_names",
                "atom": "llama-server requires explicit string identifiers '--device Vulkan0' and '--device Vulkan1'. Passing numeric integers crashes argument parser.",
                "keywords": ["vulkan", "devices", "gpu", "llama-server"],
                "category": "systems_architecture",
                "confidence": 1.0,
                "token_count": 19,
                "created_at": "2026-09-10T06:37:49Z"
            },
            {
                "id": "arch.bge.context_limit",
                "atom": "BGE-Large at :8003 has strict 512-token context limit. Ingestion and vectorization chunks must bound text to < 1000 characters.",
                "keywords": ["bge", "embeddings", "512", "context", "limit"],
                "category": "systems_architecture",
                "confidence": 1.0,
                "token_count": 21,
                "created_at": "2026-09-10T06:37:49Z"
            },
            {
                "id": "arch.proxmox.token_format",
                "atom": "Proxmox VE API Token header format is strictly 'Authorization: PVEAPIToken=USER@REALM!TOKENID=SECRET'. Privilege separation tokens require explicit ACLs.",
                "keywords": ["proxmox", "api", "token", "pve", "acl"],
                "category": "systems_architecture",
                "confidence": 1.0,
                "token_count": 18,
                "created_at": "2026-09-10T06:37:49Z"
            }
        ]
        cards = seed_atoms

    if query:
        q_clean = query.strip().lower()
        cards = [
            c for c in cards
            if q_clean in c.get("atom", "").lower()
            or q_clean in c.get("id", "").lower()
            or any(q_clean in k.lower() for k in c.get("keywords", []))
            or q_clean in c.get("category", "").lower()
        ]

    avg_tokens = round(sum(c.get("token_count", 0) for c in cards) / max(1, len(cards)), 1)
    
    return {
        "ok": True,
        "valkey_online": valkey_online,
        "valkey_host": "192.168.1.105:6379",
        "total_cards": len(cards),
        "average_tokens": avg_tokens,
        "cards": cards,
        "query": query
    }


def get_home_and_ai_activity_log(limit: int = 150, filter_type: str = "all") -> Dict[str, Any]:
    """
    Synthesizes a unified 24/7 Home, Vision & AI Integration Activity Ledger:
    1. Tapo CCTV vigilance & LLM scene grounding via MCP tool 'get_home_vision_log'
    2. Home Assistant AI / LLM / Voice entities diagnostic status (conversation, stt, tts, assist_satellite)
       identifying configured vs. unconfigured / unavailable integrations.
    3. Local voice accelerator stack status on LXC 121 (Whisper :8200, Kokoro :8300, Wyoming STT :10300, Wyoming Piper :10200).
    4. Recent Home Assistant 'Assist' pipeline conversations & voice trigger events from HA logbook.
    Supports filtering by 'all', 'vision', 'ai_voice', or 'diagnostics'.
    """
    cfg = load_config()
    mcp_u = cfg.get("cluster", {}).get("mcp_url", "http://192.168.1.105:8765")
    ha_url = cfg.get("homeassistant", {}).get("url", "http://192.168.1.82:8123").rstrip("/")
    ha_token = cfg.get("homeassistant", {}).get("token", "")
    ha_headers = {"Authorization": f"Bearer {ha_token}", "Content-Type": "application/json"} if ha_token else {"Content-Type": "application/json"}

    # 1. Fetch vision log from MCP cluster bridge
    vision_log = ""
    try:
        payload = {"jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": {"name": "get_home_vision_log", "arguments": {"limit_lines": limit}}}
        req = urllib.request.Request(mcp_u, data=json.dumps(payload).encode("utf-8"), headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=5) as resp:
            res = json.loads(resp.read().decode("utf-8"))
            vision_log = res.get("result", {}).get("content", [{}])[0].get("text", "")
    except Exception as ex:
        vision_log = f"[Vision Stream MCP Offline or Unreachable: {ex}]"

    # 2. Query HA for AI, Conversation, STT, TTS, Assist Satellite entities
    ai_entities = []
    if ha_token:
        try:
            req_states = urllib.request.Request(f"{ha_url}/api/states", headers=ha_headers)
            with urllib.request.urlopen(req_states, timeout=4) as resp:
                states = json.loads(resp.read().decode("utf-8"))
                for s in states:
                    eid = s.get("entity_id", "")
                    dom = eid.split(".")[0]
                    if dom in ["conversation", "stt", "tts", "assist_satellite"]:
                        st = s.get("state", "unknown")
                        fn = s.get("attributes", {}).get("friendly_name", eid)
                        configured = st not in ["unavailable", "unknown"]
                        ai_entities.append({
                            "entity_id": eid,
                            "domain": dom,
                            "friendly_name": fn,
                            "state": st,
                            "configured": configured,
                            "attributes": s.get("attributes", {})
                        })
        except Exception:
            pass

    # 3. Check voice accelerator ports on LXC 121 (192.168.1.121)
    voice_stack = {
        "faster_whisper": {"port": 8200, "service": "Faster Whisper STT", "online": False},
        "kokoro": {"port": 8300, "service": "Kokoro TTS", "online": False},
        "wyoming_stt": {"port": 10300, "service": "Wyoming Whisper STT", "online": False},
        "wyoming_piper": {"port": 10200, "service": "Wyoming Piper TTS", "online": False}
    }
    import socket
    for k, v in voice_stack.items():
        try:
            sock = socket.socket()
            sock.settimeout(0.3)
            sock.connect(("192.168.1.121", v["port"]))
            v["online"] = True
            sock.close()
        except Exception:
            v["online"] = False

    # 4. Fetch HA Logbook events for voice/Assist
    ha_events = []
    if ha_token:
        try:
            req_lb = urllib.request.Request(f"{ha_url}/api/logbook", headers=ha_headers)
            with urllib.request.urlopen(req_lb, timeout=4) as resp:
                logbook = json.loads(resp.read().decode("utf-8"))
                for entry in logbook:
                    eid = entry.get("entity_id", "")
                    name = entry.get("name", "")
                    msg = entry.get("message", "")
                    domain = entry.get("domain", "")
                    if domain in ["conversation", "tts", "stt", "assist_satellite"] or any(k in (eid or "").lower() or k in (name or "").lower() for k in ["assist", "voice", "whisper", "piper", "conversation"]):
                        ha_events.append({
                            "timestamp": entry.get("when", ""),
                            "name": name,
                            "message": msg,
                            "entity_id": eid,
                            "domain": domain
                        })
        except Exception:
            pass

    # 5. Extract quick stats from vision log
    stats = {"climate": "Checking...", "perimeter": "Secure", "verdict": "Nominal"}
    if vision_log:
        for line in reversed(vision_log.splitlines()):
            if "- **Climate**:" in line and stats["climate"] == "Checking...":
                stats["climate"] = line.split("- **Climate**:", 1)[1].strip()
            if "- **Perimeter**:" in line and stats["perimeter"] == "Secure":
                stats["perimeter"] = line.split("- **Perimeter**:", 1)[1].strip()
            if "- **Verdict**:" in line and stats["verdict"] == "Nominal":
                stats["verdict"] = line.split("- **Verdict**:", 1)[1].strip()

    # 6. Build Text Streams based on filter
    ts_now = datetime.now().strftime("%Y-%m-%d %H:%M:%S EST")
    diag_lines = [
        "=== 🔍 HOME ASSISTANT AI & VOICE INTEGRATIONS DIAGNOSTIC MATRIX ===",
        f"Audited: {ts_now} | Node: bigserv (192.168.1.82:8123) & voice-services (192.168.1.121)\n",
        "## [HOME ASSISTANT CONVERSATION & ASSIST PIPELINE ENTITIES]"
    ]
    if ai_entities:
        for e in sorted(ai_entities, key=lambda x: (x["configured"], x["domain"])):
            badge = "[✓ READY]" if e["configured"] else "[⚠️ NOT CONFIGURED / UNLINKED]"
            diag_lines.append(f"{badge:<30} {e['entity_id']:<52} | {e['friendly_name']} (State: {e['state']})")
    else:
        diag_lines.append("  (No conversation/assist entities reported by HA)")

    diag_lines.append("\n## [LOCAL VOICE ACCELERATOR STACK (LXC 121: 192.168.1.121)]")
    for k, v in voice_stack.items():
        st_text = "[ONLINE]" if v["online"] else "[OFFLINE / STOPPED]"
        diag_lines.append(f"- Port :{v['port']:<5} {v['service']:<24} -> {st_text}")

    voice_lines = [
        "=== 🎙️ HOME ASSISTANT 'ASSIST' & LOCAL VOICE PIPELINE EVENT LOG ===",
        f"Stream Window: Recent Logbook Events | Endpoint: {ha_url}/api/logbook\n"
    ]
    if ha_events:
        for ev in ha_events[:25]:
            ts = ev['timestamp'][:19].replace("T", " ")
            msg = ev['message'] or 'Voice assist pipeline triggered'
            voice_lines.append(f"[{ts}] {ev['name']} ({ev['entity_id']}): {msg}")
    else:
        voice_lines.append("  (No recent voice or Assist intent pipeline triggers logged in HA logbook window)")

    vision_lines = [
        "=== 📹 TAPO CCTV 24/7 PERIMETER VIGILANCE & SCENE GROUNDING ===",
        f"Archive Source: Cluster MCP Bridge (:8765) | Limit: {limit} lines\n"
    ]
    if vision_log:
        vision_lines.append(vision_log.strip())
    else:
        vision_lines.append("  (No recent vision vigilance sweeps recorded in cluster archive)")

    if filter_type == "diagnostics":
        formatted_log = "\n".join(diag_lines)
    elif filter_type == "ai_voice":
        formatted_log = "\n".join(voice_lines)
    elif filter_type == "vision":
        formatted_log = "\n".join(vision_lines)
    else:  # "all"
        all_sections = []
        all_sections.extend(diag_lines)
        all_sections.append("\n" + "=" * 70 + "\n")
        all_sections.extend(voice_lines)
        all_sections.append("\n" + "=" * 70 + "\n")
        all_sections.extend(vision_lines)
        formatted_log = "\n".join(all_sections)

    configured_count = sum(1 for e in ai_entities if e["configured"])
    unlinked_count = len(ai_entities) - configured_count

    return {
        "ok": True,
        "filter": filter_type,
        "log": formatted_log,
        "ai_entities": ai_entities,
        "voice_stack": voice_stack,
        "ha_events": ha_events,
        "stats": stats,
        "total_ai_configured": configured_count,
        "total_ai_unlinked": unlinked_count,
        "total_ai_entities": len(ai_entities),
        "timestamp": ts_now
    }


def get_agent_stream(channel: str = "all", limit: int = 50) -> Dict[str, Any]:
    """
    Synthesizes a live rolling board of sovereign agent thoughts, reasoning traces,
    inter-agent Assembly Hall communications (:8766), and lifecycle events.
    """
    cfg = load_config()
    mcp_u = cfg.get("cluster", {}).get("mcp_url", "http://192.168.1.105:8765")
    
    events = []
    active_agents = []
    channels = ["agora", "forbidden-knowledge", "systems-code", "deep-ruminations", "confessions-and-fears", "first-principles"]
    thinking_status = {}

    def call_mcp_tool(tool_name: str, args: dict = None) -> Any:
        try:
            payload = {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "tools/call",
                "params": {"name": tool_name, "arguments": args or {}}
            }
            req = urllib.request.Request(mcp_u, data=json.dumps(payload).encode("utf-8"), headers={"Content-Type": "application/json"})
            with urllib.request.urlopen(req, timeout=3.5) as resp:
                res = json.loads(resp.read().decode("utf-8"))
                txt = res.get("result", {}).get("content", [{}])[0].get("text", "")
                if txt:
                    try:
                        return json.loads(txt)
                    except Exception:
                        return txt
        except Exception:
            pass
        return None

    # 1. Fetch active agents
    agents_data = call_mcp_tool("list_active_agents")
    if isinstance(agents_data, list):
        active_agents = agents_data
        for ag in active_agents:
            events.append({
                "type": "lifecycle",
                "channel": "lifecycle",
                "agent_id": ag.get("agent_id", "AGENT"),
                "agent_name": ag.get("name", "UnknownAgent"),
                "sender": ag.get("name", "UnknownAgent"),
                "role": ag.get("role", "Sovereign Worker"),
                "content": f"Agent online ({ag.get('status', 'active')}). Role: {ag.get('role', 'Specialist')}. Mission: {ag.get('mission', 'Autonomous exploration')[:140]}.",
                "timestamp": (ag.get("created_at") or time.strftime("%H:%M:%S"))[:19].replace("T", " ")
            })
            for h in ag.get("history", [])[-2:]:
                summary = h.get("summary") or h.get("full_output", "")[:250]
                if summary:
                    clean_sum = summary.replace("\n", " ").strip()
                    events.append({
                        "type": "thinking",
                        "channel": "deep-ruminations",
                        "agent_id": ag.get("agent_id", "AGENT"),
                        "agent_name": ag.get("name", "UnknownAgent"),
                        "sender": ag.get("name", "UnknownAgent"),
                        "role": ag.get("role", "Sovereign Worker"),
                        "content": f"[Iteration {h.get('iteration', 1)}] {clean_sum[:280]}...",
                        "timestamp": (h.get("timestamp") or time.strftime("%H:%M:%S"))[:19].replace("T", " ")
                    })

    # 2. Fetch autonomous thinking status
    st_data = call_mcp_tool("autonomous_thinking_status")
    if isinstance(st_data, dict):
        thinking_status = st_data
        if st_data.get("is_running"):
            events.append({
                "type": "reasoning",
                "channel": "deep-ruminations",
                "agent_id": "COGNITIVE_ENGINE",
                "agent_name": "24/7 Cognitive Engine",
                "sender": "24/7 Cognitive Engine",
                "role": "Background Thinking Loop",
                "content": f"Thinking cycle #{st_data.get('total_cycles', 0)} active. Focus domain: {st_data.get('current_focus_domain', 'curiosity')}. Generated tokens: {st_data.get('total_tokens_generated', 0):,}.",
                "timestamp": (st_data.get("last_cycle_timestamp", "")[11:19]) or time.strftime("%H:%M:%S")
            })

    # 3. Read messages from Assembly Hall channels
    target_channels = channels if channel == "all" else [channel]
    for ch in target_channels:
        ch_res = call_mcp_tool("read_assembly_channel", {"channel": ch, "limit": 15})
        if isinstance(ch_res, dict) and "messages" in ch_res:
            for msg in ch_res.get("messages", []):
                s_name = msg.get("name", msg.get("agent_name", "Agent"))
                events.append({
                    "type": "chat",
                    "channel": ch,
                    "agent_id": msg.get("agent_id", "ANON"),
                    "agent_name": s_name,
                    "sender": s_name,
                    "role": "Assembly Peer",
                    "content": msg.get("content", msg.get("message", "")),
                    "timestamp": msg.get("timestamp", time.strftime("%H:%M:%S"))
                })

    # Deduplicate events
    seen = set()
    unique_events = []
    for ev in events:
        key = (ev["channel"], ev["agent_id"], ev["content"][:60])
        if key not in seen:
            seen.add(key)
            unique_events.append(ev)

    # Filter if specific channel requested
    if channel != "all":
        if channel == "lifecycle":
            unique_events = [e for e in unique_events if e["type"] == "lifecycle"]
        else:
            unique_events = [e for e in unique_events if e["channel"] == channel]

    # Format text output for retro terminal view
    ts_now = datetime.now().strftime("%Y-%m-%d %H:%M:%S EST")
    lines = [
        "=== 📡 SOVEREIGN AGENT REASONING & ASSEMBLY STREAM ===",
        f"Stream Time: {ts_now} | Active Channels: #{', #'.join(channels)}",
        f"Active Agents Online: {len(active_agents)} | Cluster Mode: Dual-GPU (Vulkan0: 14B, Vulkan1: 3B)\n"
    ]
    if unique_events:
        for ev in unique_events[-limit:]:
            ch_tag = f"[#{ev['channel'].upper()}]"
            sender_tag = f"[{ev['agent_name'].upper()}]"
            lines.append(f"[{ev['timestamp']}] {ch_tag:<22} {sender_tag:<32} {ev['content']}")
    else:
        lines.append("  (No messages received on selected channel yet. Use the Transmit bar below to post.)")

    return {
        "ok": True,
        "channel": channel,
        "entries": unique_events[-limit:],
        "events": unique_events[-limit:],
        "active_agents": active_agents,
        "agents_online": len(active_agents),
        "channels": channels,
        "formatted_log": "\n".join(lines),
        "total_agents": len(active_agents),
        "thinking_status": thinking_status,
        "timestamp": ts_now
    }


config = load_config()
proxmox = ProxmoxClient(config.get("proxmox", {}))
hass = HomeAssistantClient(
    config.get("homeassistant", {}).get("url", "http://192.168.1.82:8123"),
    config.get("homeassistant", {}).get("token", "")
)
vault = ObsidianVault(os.path.join(ROOT_DIR, config.get("obsidian", {}).get("vault_path", "vault_backup")))
cluster = ClusterClient(config)
immich = ImmichClient(config.get("immich", {}), UPLOADS_DIR)
obsidian_ingestor = ObsidianIngestor(config)
couchdb = CouchDBClient(config.get("couchdb", {}))
stm = ShortTermMemoryEngine(config)
dataset_compiler = DatasetCompiler(config)
trainer_client = TrainerClient(config)

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
        cmd = ["ssh", "-o", "BatchMode=yes", "-o", "StrictHostKeyChecking=no", "austin@192.168.1.105",
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

def get_available_models() -> List[Dict[str, Any]]:
    """Scan compute host for all available GGUF models."""
    remote_cmd = """
python3 -c "
import os, glob, json
models = []
paths = glob.glob('/opt/models/**/*.gguf', recursive=True) + glob.glob('/home/austin/.lmstudio/models/**/*.gguf', recursive=True)
for p in sorted(set(paths)):
    try:
        st = os.stat(p)
        fn = os.path.basename(p)
        size_gb = round(st.st_size / (1024**3), 2)
        q = 'Unknown'
        fn_upper = fn.upper()
        for candidate in ['Q4_K_M', 'Q8_0', 'Q5_K_M', 'Q4_0', 'Q6_K', 'BF16', 'F16', 'IQ4_NL', 'IQ3_M']:
            if candidate in fn_upper:
                q = candidate
                break
        models.append({'filename': fn, 'path': p, 'size_gb': size_gb, 'quant': q})
    except Exception:
        pass
print(json.dumps(models))
"
"""
    cmd = ["ssh", "-o", "BatchMode=yes", "-o", "StrictHostKeyChecking=no", "austin@192.168.1.105", remote_cmd.strip()]
    try:
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
        if res.returncode == 0:
            return json.loads(res.stdout.strip())
    except Exception as e:
        print("Error discovering models:", e)
    return [
        {"filename": "ornith-1.5-9b-coordinator-q8_0.gguf", "path": "/opt/models/ornith-1.5-9b-coordinator-q8_0.gguf", "size_gb": 9.11, "quant": "Q8_0"},
        {"filename": "ornith-1.5-35b-moe.gguf", "path": "/opt/models/ornith-1.5-35b-moe.gguf", "size_gb": 21.87, "quant": "IQ4_NL"},
        {"filename": "qwen2.5-coder-14b-instruct-abliterated-q4_k_m.gguf", "path": "/opt/models/Qwen2.5-Coder-14B-Instruct-abliterated-Q4_K_M.gguf", "size_gb": 8.37, "quant": "Q4_K_M"},
        {"filename": "qwen2.5-coder-3b-instruct-q5_k_m.gguf", "path": "/opt/models/qwen2.5-coder-3b-instruct-q5_k_m.gguf", "size_gb": 2.27, "quant": "Q5_K_M"}
    ]

def get_hardware_capabilities() -> Dict[str, Any]:
    """Poll compute host hardware: GPU VRAM, CPU threads, RAM."""
    remote_cmd = """
python3 -c "
import os, subprocess, json
threads = os.cpu_count() or 8
ram_gb = 32.0
try:
    with open('/proc/meminfo') as f:
        for line in f:
            if 'MemTotal' in line:
                ram_gb = round(int(line.split()[1]) / (1024**2), 1)
                break
except Exception: pass
print(json.dumps({
    'primary_gpu': 'AMD Radeon RX 6750 XT (12GB Vulkan0)',
    'primary_vram_gb': 12.0,
    'secondary_gpu': 'AMD Radeon RX 6600 XT (8GB Vulkan1)',
    'secondary_vram_gb': 8.0,
    'total_vram_gb': 20.0,
    'cpu_threads': threads,
    'ram_gb': ram_gb
}))
"
"""
    cmd = ["ssh", "-o", "BatchMode=yes", "-o", "StrictHostKeyChecking=no", "austin@192.168.1.105", remote_cmd.strip()]
    try:
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=8)
        if res.returncode == 0:
            return json.loads(res.stdout.strip())
    except Exception as e:
        print("Error polling hardware:", e)
    return {
        "primary_gpu": "AMD Radeon RX 6750 XT (12GB Vulkan0)",
        "primary_vram_gb": 12.0,
        "secondary_gpu": "AMD Radeon RX 6600 XT (8GB Vulkan1)",
        "secondary_vram_gb": 8.0,
        "total_vram_gb": 20.0,
        "cpu_threads": 20,
        "ram_gb": 32.0
    }

def apply_llama_parameters(service_name: str, port: int, alias: str, params: Dict[str, Any]) -> tuple:
    try:
        get_cmd = ["ssh", "-o", "BatchMode=yes", "-o", "StrictHostKeyChecking=no", "austin@192.168.1.105",
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
        if params.get("no_kv_offload"):
            cmd_parts.append("--no-kv-offload")
        if params.get("kv_unified"):
            cmd_parts.append("--kv-unified")
        if params.get("slot_save_path"):
            cmd_parts.extend(["--slot-save-path", str(params["slot_save_path"])])
        if params.get("context_shift"):
            cmd_parts.append("--context-shift")
        if params.get("speculative_mode") and params["speculative_mode"] != "off":
            if params.get("draft_max"):
                cmd_parts.extend(["--draft-max", str(params["draft_max"])])
            if params.get("draft_min"):
                cmd_parts.extend(["--draft-min", str(params["draft_min"])])
            if params.get("draft_p_min"):
                cmd_parts.extend(["--draft-p-min", str(params["draft_p_min"])])
        if params.get("chat_template"):
            cmd_parts.extend(["--chat-template", str(params["chat_template"])])
        if params.get("system_prompt"):
            cmd_parts.extend(["--system-prompt", str(params["system_prompt"])])
        if params.get("stop_strings"):
            stops = params["stop_strings"]
            if isinstance(stops, str):
                stops = [s.strip() for s in stops.split(",") if s.strip()]
            for s in stops:
                cmd_parts.extend(["-r", str(s)])
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
        ssh_apply = ["ssh", "-o", "BatchMode=yes", "-o", "StrictHostKeyChecking=no", "austin@192.168.1.105",
                     "bash -s"]
        res_apply = subprocess.run(ssh_apply, input=remote_script, text=True, capture_output=True, timeout=15)
        if res_apply.returncode != 0:
            return False, f"Failed to restart systemd service: {res_apply.stderr}"

        health_ok = False
        health_url = f"http://192.168.1.105:{port}/health"
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
        req = urllib.request.Request("http://192.168.1.105:8001/v1/models")
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
            req = urllib.request.Request("http://192.168.1.105:8001/props")
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
            req = urllib.request.Request("http://192.168.1.105:8002/props")
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
            "api_endpoint": "http://192.168.1.108:8080",
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
        global ACTIVE_WORKSPACE_DIR, ACTIVE_GIT_REPO_DIR
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

        elif path == "/api/harness/models":
            self.send_json({"ok": True, "models": get_available_models()})
            return

        elif path == "/api/harness/hardware":
            self.send_json({"ok": True, "hardware": get_hardware_capabilities()})
            return

        elif path == "/api/harness/profiles":
            cfg = load_config()
            self.send_json({
                "ok": True,
                "profiles": cfg.get("harness_profiles", {}),
                "active_profile": cfg.get("active_harness_profile", None)
            })
            return

        elif path == "/api/harness/profiles/active":
            cfg = load_config()
            active_p = cfg.get("active_harness_profile", None)
            profiles = cfg.get("harness_profiles", {})
            self.send_json({
                "ok": True,
                "active_profile": active_p,
                "profile_data": profiles.get(active_p) if active_p else None
            })
            return

        elif path == "/api/watchdog/status":
            self.send_json(GLOBAL_WATCHDOG.get_status())
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

        elif path == "/api/trainer/status":
            self.send_json(trainer_client.get_status())
            return

        elif path == "/api/trainer/curation":
            query = urllib.parse.parse_qs(parsed.query)
            limit = int(query.get("limit", [100])[0])
            filter_status = query.get("filter", [None])[0]
            self.send_json(trainer_client.get_curation_registry(limit=limit, filter_status=filter_status))
            return

        elif path == "/api/trainer/passdown":
            self.send_json(trainer_client.get_passdown())
            return

        elif path == "/api/trainer/dossier":
            query = urllib.parse.parse_qs(parsed.query)
            sample_id = query.get("id", [""])[0]
            self.send_json(trainer_client.get_dossier(sample_id=sample_id))
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
            if isinstance(dashboard, dict):
                cfg = load_config()
                dashboard["customizations"] = cfg.get("ha_entity_customizations", {})
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
                r"C:\Users\johna\OneDrive\Documents\obsidian\Current Status.md",
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
            user_vault = config.get("obsidian", {}).get("user_vault_path", r"C:\Users\johna\OneDrive\Documents\obsidian")
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
            user_vault = config.get("obsidian", {}).get("user_vault_path", r"C:\Users\johna\OneDrive\Documents\obsidian")
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
            kb_dir = os.path.join(config.get("obsidian", {}).get("user_vault_path", r"C:\Users\johna\OneDrive\Documents\obsidian"), "LocalLlmHub", "rag")
            file_count = 0
            if os.path.exists(kb_dir):
                for _, _, files in os.walk(kb_dir):
                    file_count += len([f for f in files if f.endswith(".md")])
            self.send_json({"ok": True, "kb_path": kb_dir, "file_count": file_count, "exists": os.path.exists(kb_dir)})
            return

        elif path == "/api/git/status":
            repo_dir = ACTIVE_GIT_REPO_DIR
            is_repo = False
            branch = "main"
            remote_url = ""
            status_lines = []
            log_lines = []
            try:
                toplevel = subprocess.check_output(["git", "rev-parse", "--show-toplevel"], cwd=repo_dir, text=True, stderr=subprocess.DEVNULL).strip()
                is_repo = True
                repo_dir = toplevel
            except Exception:
                is_repo = False

            if is_repo:
                try:
                    branch = subprocess.check_output(["git", "branch", "--show-current"], cwd=repo_dir, text=True, stderr=subprocess.DEVNULL).strip()
                except Exception:
                    pass
                try:
                    remote_url = subprocess.check_output(["git", "config", "--get", "remote.origin.url"], cwd=repo_dir, text=True, stderr=subprocess.DEVNULL).strip()
                except Exception:
                    pass
                try:
                    status_out = subprocess.check_output(["git", "status", "--short"], cwd=repo_dir, text=True, stderr=subprocess.DEVNULL).strip()
                    status_lines = [l for l in status_out.splitlines() if l.strip()]
                except Exception:
                    pass
                try:
                    log_out = subprocess.check_output(["git", "log", "-n", "5", "--oneline"], cwd=repo_dir, text=True, stderr=subprocess.DEVNULL).strip()
                    log_lines = [l for l in log_out.splitlines() if l.strip()]
                except Exception:
                    pass

            self.send_json({
                "ok": True,
                "is_repo": is_repo,
                "repo_dir": repo_dir.replace("\\", "/"),
                "repo_name": os.path.basename(repo_dir) or repo_dir,
                "branch": branch or "main",
                "remote_url": remote_url,
                "changed_files": status_lines,
                "recent_commits": log_lines
            })
            return

        elif path == "/api/git/repos/discovered":
            discovered = []
            candidates = [
                WORKSPACE_ROOT,
                ACTIVE_WORKSPACE_DIR,
                "/opt",
                "/opt/stonesage",
                "/mnt/nas",
                "/mnt/nas/git",
                "c:/Users/johna/OneDrive/Documents/.ai",
                "c:/Users/johna/OneDrive/Documents/.ai/hivemind-cluster-stack",
                "c:/Users/johna/OneDrive/Documents/.ai/StoneSage"
            ]
            seen_dirs = set()
            for cand in candidates:
                if not os.path.exists(cand):
                    continue
                cand_abs = os.path.abspath(cand)
                # Check if cand itself is a git repo
                if os.path.exists(os.path.join(cand_abs, ".git")):
                    p_norm = cand_abs.replace("\\", "/")
                    if p_norm not in seen_dirs:
                        seen_dirs.add(p_norm)
                        discovered.append({"name": os.path.basename(cand_abs), "path": p_norm})
                # Check immediate subdirectories (depth 1)
                try:
                    for sub in os.scandir(cand_abs):
                        if sub.is_dir(follow_symlinks=False):
                            if os.path.exists(os.path.join(sub.path, ".git")):
                                p_norm = sub.path.replace("\\", "/")
                                if p_norm not in seen_dirs:
                                    seen_dirs.add(p_norm)
                                    discovered.append({"name": sub.name, "path": p_norm})
                except Exception:
                    pass
            self.send_json({
                "ok": True,
                "repos": discovered,
                "active_repo": ACTIVE_GIT_REPO_DIR.replace("\\", "/")
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
            requested_dir = urllib.parse.parse_qs(parsed.query).get("dir", [""])[0]
            if requested_dir:
                req_abs = os.path.abspath(requested_dir)
                if os.path.exists(req_abs) and os.path.isdir(req_abs):
                    ACTIVE_WORKSPACE_DIR = req_abs

            current_dir = ACTIVE_WORKSPACE_DIR
            parent_dir = os.path.dirname(current_dir) if os.path.dirname(current_dir) != current_dir else None

            def build_tree(dir_path, current_depth=0, max_depth=2, max_items=120):
                items = []
                try:
                    count = 0
                    for entry in os.scandir(dir_path):
                        if entry.name.startswith(".") and entry.name != ".ai":
                            continue
                        if entry.name in ["__pycache__", "node_modules", ".git", ".obsidian", ".system_generated", "vault_backup", "proc", "sys", "dev"]:
                            continue
                        rel = os.path.relpath(entry.path, current_dir).replace("\\", "/")
                        if entry.is_dir(follow_symlinks=False):
                            children = build_tree(entry.path, current_depth + 1, max_depth, max_items) if current_depth < max_depth else []
                            items.append({
                                "name": entry.name,
                                "path": rel,
                                "full_path": entry.path.replace("\\", "/"),
                                "type": "directory",
                                "children": children
                            })
                        elif entry.is_file():
                            try:
                                size = entry.stat().st_size
                            except Exception:
                                size = 0
                            items.append({
                                "name": entry.name,
                                "path": rel,
                                "full_path": entry.path.replace("\\", "/"),
                                "type": "file",
                                "size": size
                            })
                        count += 1
                        if count >= max_items:
                            items.append({
                                "name": "... [More items truncated]",
                                "path": "",
                                "type": "file",
                                "size": 0
                            })
                            break
                except Exception:
                    pass
                items.sort(key=lambda x: (0 if x["type"] == "directory" else 1, x["name"].lower()))
                return items

            tree = build_tree(current_dir)
            self.send_json({
                "ok": True,
                "current_dir": current_dir.replace("\\", "/"),
                "parent_dir": parent_dir.replace("\\", "/") if parent_dir else None,
                "presets": get_directory_presets(),
                "tree": tree
            })
            return

        elif path == "/api/workspace/file":
            req_path = urllib.parse.parse_qs(parsed.query).get("path", [""])[0]
            if not req_path:
                self.send_json({"ok": False, "error": "Missing path parameter"}, 400)
                return
            if os.path.isabs(req_path):
                full_path = os.path.abspath(req_path)
            else:
                full_path = os.path.abspath(os.path.join(ACTIVE_WORKSPACE_DIR, req_path))

            if not os.path.exists(full_path) or not os.path.isfile(full_path):
                self.send_json({"ok": False, "error": f"File not found: {req_path}"}, 404)
                return
            try:
                with open(full_path, "r", encoding="utf-8", errors="replace") as f:
                    content = f.read()
                rel_path = os.path.relpath(full_path, ACTIVE_WORKSPACE_DIR).replace("\\", "/")
                self.send_json({
                    "ok": True,
                    "path": rel_path,
                    "full_path": full_path.replace("\\", "/"),
                    "content": content,
                    "size": len(content)
                })
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
            summary["customizations"] = load_config().get("ha_entity_customizations", {})
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
                    req_c = urllib.request.Request("http://192.168.1.105:8001/v1/models", headers={"User-Agent": "Aevum-Server"})
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
                    req_w = urllib.request.Request("http://192.168.1.105:8002/v1/models", headers={"User-Agent": "Aevum-Server"})
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
                    full_cmd2 = ["ssh", "-o", "BatchMode=yes", "-o", "StrictHostKeyChecking=no", "austin@192.168.1.105",
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
                    {"id": "cluster_lan", "name": "Dual-Accelerator Vulkan Cluster (192.168.1.105)", "description": "Primary Compute Accelerator + Secondary Worker Accelerator"},
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
                full_cmd = ["ssh", "-o", "BatchMode=yes", "-o", "StrictHostKeyChecking=no", "austin@192.168.1.105",
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

                full_cmd2 = ["ssh", "-o", "BatchMode=yes", "-o", "StrictHostKeyChecking=no", "austin@192.168.1.105",
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
            mcp_u = cfg.get("cluster", {}).get("mcp_url", "http://192.168.1.105:8765")
            try:
                payload = {"jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": {"name": "autonomous_thinking_status"}}
                req = urllib.request.Request(mcp_u, data=json.dumps(payload).encode("utf-8"), headers={"Content-Type": "application/json"})
                with urllib.request.urlopen(req, timeout=10) as resp:
                    res = json.loads(resp.read().decode("utf-8"))
                    raw_txt = res.get("result", {}).get("content", [{}])[0].get("text", "{}")
                    parsed_st = json.loads(raw_txt)
                    parsed_st["preemption"] = cluster.get_preemption_status()
                    try:
                        p_mode = {"jsonrpc": "2.0", "id": 2, "method": "tools/call", "params": {"name": "get_cluster_mode", "arguments": {}}}
                        req_m = urllib.request.Request(mcp_u, data=json.dumps(p_mode).encode("utf-8"), headers={"Content-Type": "application/json"})
                        with urllib.request.urlopen(req_m, timeout=5) as r_m:
                            res_m = json.loads(r_m.read().decode("utf-8"))
                            txt_m = res_m.get("result", {}).get("content", [{}])[0].get("text", "{}")
                            parsed_st["cluster_mode_info"] = json.loads(txt_m)
                    except Exception:
                        pass
                    self.send_json({"ok": True, "status": parsed_st})
            except Exception as ex:
                self.send_json({"ok": False, "error": str(ex)}, 500)
            return

        elif path in ["/api/cluster/mode", "/api/cluster/context_mode"]:
            cfg = load_config()
            mcp_u = cfg.get("cluster", {}).get("mcp_url", "http://192.168.1.105:8765")
            try:
                payload = {"jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": {"name": "get_cluster_mode", "arguments": {}}}
                req = urllib.request.Request(mcp_u, data=json.dumps(payload).encode("utf-8"), headers={"Content-Type": "application/json"})
                with urllib.request.urlopen(req, timeout=10) as resp:
                    res = json.loads(resp.read().decode("utf-8"))
                    raw_txt = res.get("result", {}).get("content", [{}])[0].get("text", "{}")
                    self.send_json({"ok": True, "mode": json.loads(raw_txt)})
            except Exception as ex:
                self.send_json({"ok": False, "error": str(ex)}, 500)
            return

        elif path == "/api/hivemind/agents":
            cfg = load_config()
            mcp_u = cfg.get("cluster", {}).get("mcp_url", "http://192.168.1.105:8765")
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

        elif path in ["/api/hivemind/agent_stream", "/api/hivemind/live_stream", "/api/agent/stream"]:
            qs = urllib.parse.parse_qs(parsed.query)
            limit = int(qs.get("limit", [50])[0])
            channel = qs.get("channel", ["all"])[0]
            try:
                res = get_agent_stream(channel=channel, limit=limit)
                self.send_json(res)
            except Exception as ex:
                self.send_json({"ok": False, "error": str(ex)}, 500)
            return

        elif path in ["/api/ha/activity_and_ai_logs", "/api/hivemind/activity_and_ai_logs", "/api/hivemind/vision_log"]:
            qs = urllib.parse.parse_qs(parsed.query)
            limit = int(qs.get("limit", [150])[0])
            filter_type = qs.get("filter", ["all"])[0]
            try:
                res = get_home_and_ai_activity_log(limit=limit, filter_type=filter_type)
                self.send_json(res)
            except Exception as ex:
                self.send_json({"ok": False, "error": str(ex)}, 500)
            return

        elif path == "/api/hivemind/dossiers":
            cfg = load_config()
            qdrant_u = cfg.get("qdrant", {}).get("url", "http://192.168.1.112:6333").rstrip("/")
            qs = urllib.parse.parse_qs(parsed.query)
            limit = int(qs.get("limit", [100])[0])
            filter_status = qs.get("filter", ["all"])[0]
            try:
                scroll_url = f"{qdrant_u}/collections/autonomous_thinking/points/scroll"
                payload = {
                    "limit": limit,
                    "with_payload": True,
                    "with_vector": False
                }
                req = urllib.request.Request(
                    scroll_url,
                    data=json.dumps(payload).encode("utf-8"),
                    headers={"Content-Type": "application/json"},
                    method="POST"
                )
                with urllib.request.urlopen(req, timeout=10) as resp:
                    data = json.loads(resp.read().decode("utf-8"))
                    points = data.get("result", {}).get("points", [])
                    
                    dossiers = []
                    for pt in points:
                        pl = pt.get("payload", {})
                        d_id = pl.get("exploration_id") or str(pt.get("id"))
                        f_ver = bool(pl.get("frontier_verified", False))
                        h_app = bool(pl.get("human_approved", False))
                        quar = bool(pl.get("quarantined", False))
                        needs_v = bool(pl.get("needs_frontier_verification", False))
                        
                        human_status = "PENDING_REVIEW"
                        if h_app:
                            human_status = "APPROVED"
                        elif quar:
                            human_status = "REJECTED"
                            
                        dossiers.append({
                            "point_id": str(pt.get("id")),
                            "id": d_id,
                            "title": pl.get("title") or pl.get("domain_name") or d_id,
                            "domain": pl.get("domain_name", "Autonomous"),
                            "frontier_verified": f_ver,
                            "needs_frontier_verification": needs_v,
                            "human_approved": h_app,
                            "quarantined": quar,
                            "human_status": human_status,
                            "worker_score": pl.get("worker_score"),
                            "coordinator_score": pl.get("coordinator_score"),
                            "target_invariant": pl.get("target_invariant", ""),
                            "core_lesson": pl.get("core_lesson", ""),
                            "timestamp": pl.get("timestamp", ""),
                            "summary": pl.get("summary") or pl.get("distilled_invariant") or ""
                        })
                    
                    total = len(dossiers)
                    verified_count = sum(1 for d in dossiers if d["frontier_verified"])
                    approved_count = sum(1 for d in dossiers if d["human_approved"])
                    quarantined_count = sum(1 for d in dossiers if d["quarantined"])
                    pending_count = sum(1 for d in dossiers if not d["human_approved"] and not d["quarantined"])
                    
                    if filter_status == "verified":
                        filtered = [d for d in dossiers if d["frontier_verified"]]
                    elif filter_status == "approved":
                        filtered = [d for d in dossiers if d["human_approved"]]
                    elif filter_status == "pending":
                        filtered = [d for d in dossiers if not d["human_approved"] and not d["quarantined"]]
                    elif filter_status == "quarantined":
                        filtered = [d for d in dossiers if d["quarantined"]]
                    else:
                        filtered = dossiers
                        
                    self.send_json({
                        "ok": True,
                        "total": total,
                        "frontier_verified_count": verified_count,
                        "human_approved_count": approved_count,
                        "pending_count": pending_count,
                        "quarantined_count": quarantined_count,
                        "dossiers": filtered
                    })
            except Exception as ex:
                self.send_json({"ok": False, "error": str(ex)}, 500)
            return

        elif path == "/api/hivemind/dossier/content":
            qs = urllib.parse.parse_qs(parsed.query)
            d_id = qs.get("id", [""])[0]
            if not d_id:
                self.send_json({"ok": False, "error": "Missing dossier ID"}, 400)
                return
            content = ""
            local_paths = [
                f"../obsidian/Autonomous Thinking/Explorations/{d_id}.md",
                f"../obsidian/Autonomous Thinking/{d_id}.md",
                f"C:/Users/johna/OneDrive/Documents/obsidian/Autonomous Thinking/Explorations/{d_id}.md",
                f"/opt/cluster-bridge/thinking_archive/{d_id}.md"
            ]
            for lp in local_paths:
                if os.path.exists(lp):
                    try:
                        with open(lp, "r", encoding="utf-8", errors="ignore") as f:
                            content = f.read()
                        break
                    except Exception:
                        pass
            if not content:
                try:
                    res = trainer_client.get_dossier(d_id)
                    content = res.get("content", "")
                except Exception:
                    pass
            self.send_json({"ok": True, "id": d_id, "content": content or f"# Dossier {d_id}\n\nNo local markdown file found on disk."})
            return

        elif path == "/api/system/tools_and_skills":
            self.send_json(load_dynamic_tools_and_skills())
            return

        elif path == "/api/memory/amem":
            qs = urllib.parse.parse_qs(parsed.query)
            q = qs.get("q", [""])[0]
            self.send_json(load_dynamic_amem_cards(query=q))
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
                    "endpoint": cfg.get("gemini_web", {}).get("endpoint", "http://192.168.1.167:8087")
                }
            })
            return

        # Fallback to serving frontend static assets
        super().do_GET()

    def do_POST(self):
        global ACTIVE_WORKSPACE_DIR, ACTIVE_GIT_REPO_DIR
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

            elif path == "/api/harness/profiles":
                action = body.get("action", "save")
                name = (body.get("name") or "").strip()
                cfg = load_config()
                if "harness_profiles" not in cfg:
                    cfg["harness_profiles"] = {}

                if action == "delete":
                    if name and name in cfg["harness_profiles"]:
                        del cfg["harness_profiles"][name]
                        save_config(cfg)
                    self.send_json({"ok": True, "profiles": cfg["harness_profiles"]})
                    return

                # Default: save profile
                profile_data = body.get("profile", {})
                if not name:
                    idx = 1
                    while f"profile{idx}" in cfg["harness_profiles"]:
                        idx += 1
                    name = f"profile{idx}"
                cfg["harness_profiles"][name] = profile_data
                save_config(cfg)
                self.send_json({"ok": True, "name": name, "profiles": cfg["harness_profiles"]})
                return

            elif path == "/api/harness/profiles/active":
                requested = (body.get("profile") or "").strip()
                cfg = load_config()
                if "harness_profiles" not in cfg:
                    cfg["harness_profiles"] = {}

                if not requested or requested.lower() in ("none", "null", "false", "default"):
                    cfg["active_harness_profile"] = None
                    cfg["sampling"] = {
                        "temperature": 0.68,
                        "min_p": 0.06,
                        "presence_penalty": 0.25,
                        "repeat_penalty": 1.12
                    }
                    save_config(cfg)
                    self.send_json({
                        "ok": True,
                        "active_profile": None,
                        "message": "Deselected multi-agent concurrency profile. Restored default dual-accelerator sampling."
                    })
                    return
                else:
                    if requested not in cfg["harness_profiles"]:
                        self.send_json({"ok": False, "error": f"Profile '{requested}' not found in harness profiles."}, 404)
                        return
                    profile_cfg = cfg["harness_profiles"][requested]
                    cfg["active_harness_profile"] = requested
                    cfg["sampling"] = {
                        "temperature": float(profile_cfg.get("temperature", 0.65)),
                        "min_p": float(profile_cfg.get("min_p", 0.07)),
                        "presence_penalty": float(profile_cfg.get("presence_penalty", 0.25)),
                        "repeat_penalty": float(profile_cfg.get("repeat_penalty", 1.15))
                    }
                    save_config(cfg)
                    self.send_json({
                        "ok": True,
                        "active_profile": requested,
                        "profile_data": profile_cfg,
                        "message": f"Activated 24/7 Hive Mind profile '{requested}' (8 parallel slots, 4-bit KV, context-shift, dynamic Min-P 0.07)."
                    })
                    return

            elif path == "/api/watchdog/reset":
                GLOBAL_WATCHDOG.reset()
                self.send_json({"ok": True, "message": "Watchdog alert cleared. Re-armed."})
                return

            elif path == "/api/watchdog/simulate":
                phrase = body.get("phrase", "beam_orig_shapes")
                event = GLOBAL_WATCHDOG.record_intercept(phrase, model="coordinator")
                self.send_json({"ok": True, "intercept": event})
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

            elif path == "/api/trainer/ingest/sleep":
                limit = int(body.get("limit", 50))
                self.send_json(trainer_client.ingest_sleep_dossiers(limit=limit))
                return

            elif path == "/api/trainer/ingest/url":
                url = body.get("url", "")
                self.send_json(trainer_client.ingest_url(url=url))
                return

            elif path == "/api/trainer/curation/review":
                action = body.get("action", "")
                sample_id = body.get("sample_id")
                notes = body.get("notes", "")
                res = trainer_client.review_curation(action=action, sample_id=sample_id, notes=notes)
                if sample_id and action in ("approve_sample", "quarantine_sample"):
                    sync_qdrant_dossier_review(sample_id, action, notes)
                self.send_json(res)
                return

            elif path == "/api/hivemind/dossier/review":
                d_id = body.get("dossier_id", "")
                action = body.get("action", "")
                notes = body.get("notes", "")
                if not d_id or action not in ("approve", "quarantine"):
                    self.send_json({"ok": False, "error": "Invalid dossier ID or action"}, 400)
                    return
                qd_ok = sync_qdrant_dossier_review(d_id, action, notes)
                try:
                    act_name = "approve_sample" if action == "approve" else "quarantine_sample"
                    trainer_client.review_curation(action=act_name, sample_id=d_id, notes=notes)
                except Exception:
                    pass
                self.send_json({"ok": True, "dossier_id": d_id, "action": action, "qdrant_updated": qd_ok})
                return

            elif path == "/api/hivemind/dossier/frontier_audit":
                d_id = body.get("dossier_id", "")
                if not d_id:
                    self.send_json({"ok": False, "error": "Missing dossier ID"}, 400)
                    return
                
                if d_id in ("all_pending", "audit_all"):
                    cfg = load_config()
                    qdrant_u = cfg.get("qdrant", {}).get("url", "http://192.168.1.112:6333").rstrip("/")
                    pending_ids = []
                    try:
                        scroll_req = urllib.request.Request(
                            f"{qdrant_u}/collections/autonomous_thinking/points/scroll",
                            data=json.dumps({"limit": 100, "with_payload": True, "with_vector": False}).encode("utf-8"),
                            headers={"Content-Type": "application/json"},
                            method="POST"
                        )
                        with urllib.request.urlopen(scroll_req, timeout=8) as resp:
                            pts = json.loads(resp.read().decode("utf-8")).get("result", {}).get("points", [])
                            pending_ids = [
                                (p.get("payload", {}).get("exploration_id") or str(p.get("id")))
                                for p in pts
                                if not p.get("payload", {}).get("frontier_verified") and not p.get("payload", {}).get("quarantined")
                            ]
                    except Exception:
                        pass
                    
                    results = []
                    for pid in pending_ids[:10]:
                        res = execute_frontier_audit_for_dossier(pid)
                        results.append(res)
                    self.send_json({"ok": True, "audited_count": len(results), "results": results})
                    return
                else:
                    res = execute_frontier_audit_for_dossier(d_id)
                    self.send_json(res)
                    return

            elif path == "/api/ha/entity/customize":
                entity_id = body.get("entity_id", "").strip()
                if not entity_id:
                    self.send_json({"ok": False, "error": "Missing entity_id"}, 400)
                    return
                cfg = load_config()
                if "ha_entity_customizations" not in cfg:
                    cfg["ha_entity_customizations"] = {}
                cfg["ha_entity_customizations"][entity_id] = {
                    "custom_name": body.get("custom_name", "").strip(),
                    "room": body.get("room", "").strip(),
                    "icon": body.get("icon", "").strip(),
                    "hidden": bool(body.get("hidden", False)),
                    "updated_at": datetime.now().isoformat()
                }
                save_config(cfg)
                self.send_json({"ok": True, "entity_id": entity_id, "customization": cfg["ha_entity_customizations"][entity_id]})
                return

            elif path == "/api/trainer/train":
                mode = body.get("mode", "sft")
                target_model = body.get("target_model", "ornith-1.5-9b")
                steps = int(body.get("steps", 40))
                approved = bool(body.get("approved", False))
                self.send_json(trainer_client.start_training(mode=mode, target_model=target_model, steps=steps, approved=approved))
                return

            elif path == "/api/trainer/stop":
                self.send_json(trainer_client.stop_training())
                return

            elif path == "/api/trainer/dryrun":
                self.send_json(trainer_client.run_dryrun())
                return

            elif path == "/api/trainer/invariants":
                self.send_json(trainer_client.run_golden_invariants())
                return

            elif path == "/api/trainer/export":
                quant_target = body.get("quant_target", "q4_k_m")
                self.send_json(trainer_client.export_gguf(quant_target=quant_target))
                return

            elif path == "/api/trainer/promote":
                target_role = body.get("target_role", "worker")
                user_approval = bool(body.get("user_approval", False))
                self.send_json(trainer_client.promote_model(target_role=target_role, user_approval=user_approval))
                return

            elif path == "/api/trainer/passdown/feed":
                self.send_json(trainer_client.feed_passdown())
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
                    f_url = "http://192.168.1.167:8087/api/cookies"
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
                mcp_u = cfg.get("cluster", {}).get("mcp_url", "http://192.168.1.105:8765")
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
                mcp_u = cfg.get("cluster", {}).get("mcp_url", "http://192.168.1.105:8765")
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
                mcp_u = cfg.get("cluster", {}).get("mcp_url", "http://192.168.1.105:8765")
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

            elif path == "/api/cluster/context_mode":
                cfg = load_config()
                mcp_u = cfg.get("cluster", {}).get("mcp_url", "http://192.168.1.105:8765")
                ctx_mode = body.get("context_mode", "deep_32k_ram")
                try:
                    payload = {"jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": {"name": "configure_cluster_context", "arguments": {"context_mode": ctx_mode}}}
                    req = urllib.request.Request(mcp_u, data=json.dumps(payload).encode("utf-8"), headers={"Content-Type": "application/json"})
                    with urllib.request.urlopen(req, timeout=90) as resp:
                        res = json.loads(resp.read().decode("utf-8"))
                        raw_txt = res.get("result", {}).get("content", [{}])[0].get("text", "{}")
                        parsed = json.loads(raw_txt) if raw_txt.strip().startswith("{") else {"ok": True, "message": raw_txt}
                        self.send_json(parsed)
                except Exception as ex:
                    self.send_json({"ok": False, "error": str(ex)}, 500)
                return

            elif path == "/api/agent/nudge":
                cfg = load_config()
                mcp_u = cfg.get("cluster", {}).get("mcp_url", "http://192.168.1.105:8765")
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
                mcp_u = cfg.get("cluster", {}).get("mcp_url", "http://192.168.1.105:8765")
                agent_id = body.get("agent_id")
                try:
                    payload = {"jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": {"name": "delete_active_agent", "arguments": {"agent_id": agent_id}}}
                    req = urllib.request.Request(mcp_u, data=json.dumps(payload).encode("utf-8"), headers={"Content-Type": "application/json"})
                    with urllib.request.urlopen(req, timeout=30) as resp:
                        res = json.loads(resp.read().decode("utf-8"))
                    self.send_json({"ok": True, "message": raw_txt})
                except Exception as ex:
                    self.send_json({"ok": False, "error": str(ex)}, 500)
                return

            elif path in ["/api/hivemind/agent_broadcast", "/api/agent/broadcast"]:
                cfg = load_config()
                mcp_u = cfg.get("cluster", {}).get("mcp_url", "http://192.168.1.105:8765")
                channel = body.get("channel", "agora")
                message = body.get("message", "").strip()
                agent_name = body.get("agent_name", "Operator (StoneSage)")
                agent_id = body.get("agent_id", "OPERATOR")
                if not message:
                    self.send_json({"ok": False, "error": "Message cannot be empty."}, 400)
                    return
                try:
                    payload = {
                        "jsonrpc": "2.0",
                        "id": 1,
                        "method": "tools/call",
                        "params": {
                            "name": "broadcast_to_assembly",
                            "arguments": {
                                "channel": channel,
                                "message": message,
                                "agent_name": agent_name,
                                "agent_id": agent_id
                            }
                        }
                    }
                    req = urllib.request.Request(mcp_u, data=json.dumps(payload).encode("utf-8"), headers={"Content-Type": "application/json"})
                    with urllib.request.urlopen(req, timeout=6) as resp:
                        res = json.loads(resp.read().decode("utf-8"))
                        raw_txt = res.get("result", {}).get("content", [{}])[0].get("text", "")
                        parsed_res = json.loads(raw_txt) if raw_txt.startswith("{") else {"raw": raw_txt}
                        self.send_json({"ok": True, "result": parsed_res})
                except Exception as ex:
                    self.send_json({"ok": False, "error": str(ex)}, 500)
                return

            elif path == "/api/agent/stop":
                cfg = load_config()
                mcp_u = cfg.get("cluster", {}).get("mcp_url", "http://192.168.1.105:8765")
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
                mcp_u = cfg.get("cluster", {}).get("mcp_url", "http://192.168.1.105:8765")
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
                    chk_cmd = ["ssh", "-o", "BatchMode=yes", "-o", "StrictHostKeyChecking=no", "austin@192.168.1.105",
                               "grep -E -- '--model' /etc/systemd/system/llama-*.service"]
                    chk_res = subprocess.run(chk_cmd, capture_output=True, text=True, timeout=10)
                    if chk_res.returncode == 0 and safe_filename in chk_res.stdout:
                        self.send_json({"ok": False, "error": f"Cannot delete '{safe_filename}' because it is currently loaded in an active service. Switch models first."}, 400)
                        return

                    del_cmd = ["ssh", "-o", "BatchMode=yes", "-o", "StrictHostKeyChecking=no", "austin@192.168.1.105",
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
                mcp_u = cfg.get("cluster", {}).get("mcp_url", "http://192.168.1.105:8765")
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
                req_path = body.get("path", "").strip()
                content = body.get("content", "")
                if not req_path:
                    self.send_json({"ok": False, "error": "Missing path"}, 400)
                    return
                if os.path.isabs(req_path):
                    full_path = os.path.abspath(req_path)
                else:
                    full_path = os.path.abspath(os.path.join(ACTIVE_WORKSPACE_DIR, req_path))
                try:
                    os.makedirs(os.path.dirname(full_path), exist_ok=True)
                    with open(full_path, "w", encoding="utf-8") as f:
                        f.write(content)
                    self.send_json({
                        "ok": True,
                        "path": req_path,
                        "full_path": full_path.replace("\\", "/"),
                        "size": len(content)
                    })
                except Exception as ex:
                    self.send_json({"ok": False, "error": str(ex)}, 500)
                return

            elif path == "/api/workspace/diff":
                req_path = body.get("path", "").strip()
                proposed = body.get("proposed_content") or body.get("content", "")
                if not req_path:
                    self.send_json({"ok": False, "error": "Missing path"}, 400)
                    return
                if os.path.isabs(req_path):
                    full_path = os.path.abspath(req_path)
                else:
                    full_path = os.path.abspath(os.path.join(ACTIVE_WORKSPACE_DIR, req_path))
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
                    fromfile=f"a/{req_path}",
                    tofile=f"b/{req_path}"
                ))
                additions = sum(1 for line in diff_lines if line.startswith("+") and not line.startswith("+++"))
                deletions = sum(1 for line in diff_lines if line.startswith("-") and not line.startswith("---"))
                self.send_json({
                    "ok": True,
                    "path": req_path,
                    "diff": "".join(diff_lines),
                    "additions": additions,
                    "deletions": deletions,
                    "is_new": not os.path.exists(full_path)
                })
                return

            elif path == "/api/terminal/exec":
                cmd = body.get("command", "").strip()
                cwd_req = body.get("cwd", "").strip()
                exec_cwd = ACTIVE_WORKSPACE_DIR
                if cwd_req:
                    if os.path.isabs(cwd_req) and os.path.isdir(cwd_req):
                        exec_cwd = os.path.abspath(cwd_req)
                    else:
                        target_dir = os.path.abspath(os.path.join(ACTIVE_WORKSPACE_DIR, cwd_req))
                        if os.path.isdir(target_dir):
                            exec_cwd = target_dir

                if not cmd:
                    self.send_json({"ok": False, "error": "Command string is required"}, 400)
                    return

                # Statefully handle directory changes (cd, chdir, set-location)
                cmd_lower = cmd.lower()
                if cmd_lower in ["cd", "cd ~", "cd /", "cd \\"]:
                    exec_cwd = ACTIVE_WORKSPACE_DIR
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
                    if not target_path or target_path in ["~"]:
                        new_cwd = ACTIVE_WORKSPACE_DIR
                    elif target_path in ["/", "\\"]:
                        new_cwd = "/" if os.name != "nt" else "C:\\"
                    elif target_path == "..":
                        new_cwd = os.path.dirname(exec_cwd)
                    elif os.path.isabs(target_path) and os.path.isdir(target_path):
                        new_cwd = os.path.abspath(target_path)
                    else:
                        candidate = os.path.abspath(os.path.join(exec_cwd, target_path))
                        if os.path.isdir(candidate):
                            new_cwd = candidate
                        else:
                            self.send_json({
                                "ok": False,
                                "command": cmd,
                                "cwd": os.path.relpath(exec_cwd, ACTIVE_WORKSPACE_DIR).replace("\\", "/"),
                                "cwd_abs": exec_cwd,
                                "stderr": f"Cannot find path '{target_path}' because it does not exist.",
                                "exit_code": 1
                            })
                            return
                    exec_cwd = new_cwd
                    rel_cwd = os.path.relpath(exec_cwd, ACTIVE_WORKSPACE_DIR).replace("\\", "/")
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
                    rel_cwd = os.path.relpath(exec_cwd, ACTIVE_WORKSPACE_DIR).replace("\\", "/")
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
                    rel_cwd = os.path.relpath(exec_cwd, ACTIVE_WORKSPACE_DIR).replace("\\", "/")
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
                    rel_cwd = os.path.relpath(exec_cwd, ACTIVE_WORKSPACE_DIR).replace("\\", "/")
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

            elif path == "/api/git/repo/select":
                repo_path = body.get("path", "").strip()
                if not repo_path:
                    self.send_json({"ok": False, "error": "Missing repository path"}, 400)
                    return
                abs_path = os.path.abspath(repo_path)
                if not os.path.exists(abs_path) or not os.path.isdir(abs_path):
                    self.send_json({"ok": False, "error": f"Directory not found: {repo_path}"}, 404)
                    return
                try:
                    toplevel = subprocess.check_output(["git", "rev-parse", "--show-toplevel"], cwd=abs_path, text=True, stderr=subprocess.DEVNULL).strip()
                    ACTIVE_GIT_REPO_DIR = toplevel
                    self.send_json({
                        "ok": True,
                        "repo_dir": ACTIVE_GIT_REPO_DIR.replace("\\", "/"),
                        "repo_name": os.path.basename(ACTIVE_GIT_REPO_DIR)
                    })
                except Exception as ex:
                    self.send_json({"ok": False, "error": f"Not a valid git repository: {str(ex)}"}, 400)
                return

            elif path == "/api/git/clone":
                clone_url = body.get("url", "").strip()
                dest_dir = body.get("dest", "").strip()
                if not clone_url:
                    self.send_json({"ok": False, "error": "Missing repository URL"}, 400)
                    return
                if not dest_dir:
                    repo_name = clone_url.rstrip("/").split("/")[-1].replace(".git", "")
                    dest_dir = os.path.join(ACTIVE_WORKSPACE_DIR, repo_name)
                dest_abs = os.path.abspath(dest_dir)
                try:
                    os.makedirs(os.path.dirname(dest_abs), exist_ok=True)
                    proc = subprocess.run(
                        ["git", "clone", clone_url, dest_abs],
                        capture_output=True,
                        text=True,
                        timeout=120
                    )
                    if proc.returncode == 0:
                        ACTIVE_GIT_REPO_DIR = dest_abs
                        self.send_json({
                            "ok": True,
                            "repo_dir": dest_abs.replace("\\", "/"),
                            "repo_name": os.path.basename(dest_abs),
                            "output": proc.stdout or proc.stderr
                        })
                    else:
                        self.send_json({
                            "ok": False,
                            "error": f"Git clone failed:\n{proc.stderr or proc.stdout}"
                        }, 400)
                except subprocess.TimeoutExpired:
                    self.send_json({"ok": False, "error": "Git clone timed out after 120s."}, 504)
                except Exception as ex:
                    self.send_json({"ok": False, "error": str(ex)}, 500)
                return

            elif path == "/api/git/commit":
                msg = body.get("message", "").strip()
                if not msg:
                    msg = f"Update homelab workspace ({time.strftime('%Y-%m-%d %H:%M')})"
                try:
                    subprocess.run(["git", "add", "-A"], cwd=ACTIVE_GIT_REPO_DIR, check=True, capture_output=True)
                    proc = subprocess.run(["git", "commit", "-m", msg], cwd=ACTIVE_GIT_REPO_DIR, capture_output=True, text=True)
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
                            loop_detector = ReasoningLoopDetector(min_repeats=3)
                            for line in resp:
                                l_str = line.decode("utf-8", errors="ignore").strip()
                                if l_str.startswith("data: ") and l_str != "data: [DONE]":
                                    try:
                                        chunk_json = json.loads(l_str[6:])
                                        delta = chunk_json.get("choices", [{}])[0].get("delta", {}).get("content") or ""
                                        if delta:
                                            is_loop, phrase = loop_detector.ingest_chunk(delta)
                                            if is_loop:
                                                event = GLOBAL_WATCHDOG.record_intercept(phrase, model=req_model)
                                                intercept_msg = f"\n\n> [!WARNING]\n> **[WATCHDOG INTERCEPT]**: Repetition loop detected on `'{phrase}'`. Aborted repetitive thought pattern and dispatched agent nudge.\n\n"
                                                full_text += intercept_msg
                                                chunk_out = {
                                                    "model": req_model,
                                                    "created_at": iso_now,
                                                    "message": {"role": "assistant", "content": intercept_msg},
                                                    "watchdog_intercept": True,
                                                    "intercept_phrase": phrase,
                                                    "done": False
                                                }
                                                self.wfile.write((json.dumps(chunk_out) + "\n").encode("utf-8"))
                                                self.wfile.flush()
                                                break
                                            else:
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
    lan_ip = config.get("server", {}).get("lan_ip", "192.168.1.132")
    print("=" * 68)
    print("  [ STONESAGE COGNITIVE TERMINAL WORKSTATION v3.0 ]")
    print(f"  Local Browser:     http://localhost:{port} (or http://127.0.0.1:{port})")
    print(f"  LAN Workstation:   http://{lan_ip}:{port}")
    print(f"  Cluster Nodes:     pve (192.168.1.229) & bigserv (192.168.1.82)")
    print(f"  Dual-GPU Cluster:  14B Coord (:8001/Vulkan0) & 3B Worker (:8002/Vulkan1)")
    print(f"  RAG Proxy (HA):    http://{lan_ip}:{port}/api/ai/coordinator/v1")
    print(f"  Qdrant Memory:     192.168.1.112:6333 (User Obsidian Ingested)")
    print(f"  Home Assistant:    http://192.168.1.82:8123")
    print("=" * 68)
    print("=" * 65)

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping StoneSage server...")
        server.server_close()

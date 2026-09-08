#!/usr/bin/env python3
"""
Homelab Knowledge & Skill Vector Database Exporter
Indexes all usable skills, workspace documentation, architecture invariants,
and conversation summaries into Qdrant (LXC 117 - 127.0.0.1:6333) using
hardware-accelerated BGE embeddings (127.0.0.1:8003).

Strict Invariant: Text chunks must not exceed 800 characters to prevent
BGE embedder (512 tokens max) HTTP 500 crashes.
"""

import os
import sys
import re
import glob
import json
import uuid
import time
import argparse
import urllib.request
import urllib.error
from pathlib import Path

# Force UTF-8 on Windows consoles
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

# Configuration Endpoints
EMBEDDER_URL = "http://127.0.0.1:8003/v1/embeddings"
QDRANT_URL = "http://127.0.0.1:6333"
WORKSPACE_DIR = r"c:\Users\admin\OneDrive\Documents\.ai"
USER_PROFILE_DIR = r"C:\Users\admin"
OBSIDIAN_VAULT_DIR = r"C:\Users\admin\OneDrive\Documents\obsidian"

# Skill Search Directories
SKILL_PATHS = [
    r"c:\Users\admin\OneDrive\Documents\.ai\.agents\skills",
    r"C:\Users\admin\.gemini\antigravity\builtin\skills",
    r"C:\Users\admin\.gemini\config\plugins",
    r"C:\Users\admin\.gemini\config\skills",
]

# Workspace Key Documents
WORKSPACE_DOCS = [
    r"c:\Users\admin\OneDrive\Documents\.ai\GEMINI.md",
    r"c:\Users\admin\OneDrive\Documents\.ai\server setup\NETWORK_DEVICE_REGISTRY.md",
    r"c:\Users\admin\OneDrive\Documents\.ai\server setup\COMPANION_MANIFESTO.md",
    r"c:\Users\admin\OneDrive\Documents\.ai\server setup\NEST_THERMOSTAT_GUIDE.md",
]

MAX_CHUNK_CHARS = 750

def chunk_text(text: str, max_chars: int = MAX_CHUNK_CHARS) -> list[str]:
    """Splits text into chunks strictly under max_chars, respecting paragraphs/lines."""
    if not text or not text.strip():
        return []
    
    paragraphs = text.replace('\r\n', '\n').split('\n\n')
    chunks = []
    current_chunk = ""
    
    for p in paragraphs:
        p = p.strip()
        if not p:
            continue
        
        # If single paragraph exceeds max_chars, split by lines or sentences
        if len(p) > max_chars:
            lines = p.split('\n')
            for line in lines:
                line = line.strip()
                if not line:
                    continue
                if len(line) > max_chars:
                    # Hard truncate on word boundaries
                    words = line.split(' ')
                    temp = ""
                    for w in words:
                        if len(temp) + len(w) + 1 <= max_chars:
                            temp = f"{temp} {w}".strip()
                        else:
                            if temp:
                                chunks.append(temp)
                            temp = w
                    if temp:
                        chunks.append(temp)
                else:
                    if len(current_chunk) + len(line) + 1 <= max_chars:
                        current_chunk = f"{current_chunk}\n{line}".strip()
                    else:
                        if current_chunk:
                            chunks.append(current_chunk)
                        current_chunk = line
        else:
            if len(current_chunk) + len(p) + 2 <= max_chars:
                current_chunk = f"{current_chunk}\n\n{p}".strip()
            else:
                if current_chunk:
                    chunks.append(current_chunk)
                current_chunk = p
                
    if current_chunk:
        chunks.append(current_chunk)
        
    return [c[:max_chars] for c in chunks if c.strip()]


def get_embedding(text: str) -> list[float]:
    """Retrieves 1024-d embedding from bge-large-en-v1.5 at :8003."""
    clean_text = text[:MAX_CHUNK_CHARS]
    payload = json.dumps({"input": clean_text, "model": "embedder"}).encode('utf-8')
    req = urllib.request.Request(
        EMBEDDER_URL,
        data=payload,
        headers={"Content-Type": "application/json"}
    )
    with urllib.request.urlopen(req, timeout=10) as resp:
        res = json.loads(resp.read().decode('utf-8'))
        return res["data"][0]["embedding"]


def upsert_points(collection: str, points: list[dict]):
    """Upserts a list of points into a Qdrant collection."""
    if not points:
        return
    url = f"{QDRANT_URL}/collections/{collection}/points?wait=true"
    payload = json.dumps({"points": points}).encode('utf-8')
    req = urllib.request.Request(
        url,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="PUT"
    )
    with urllib.request.urlopen(req, timeout=15) as resp:
        return json.loads(resp.read().decode('utf-8'))


def index_skills():
    """Finds all SKILL.md files and indexes them into codebase_knowledge."""
    print("\n--- [1/4] Indexing Usable Skills ---")
    skill_files = []
    for root in SKILL_PATHS:
        if os.path.exists(root):
            for path in Path(root).rglob("SKILL.md"):
                skill_files.append(str(path))
                
    print(f"Found {len(skill_files)} skill definition files.")
    total_indexed = 0
    
    for sf in skill_files:
        try:
            with open(sf, "r", encoding="utf-8", errors="replace") as f:
                content = f.read()
            
            # Extract basic metadata
            skill_dir = os.path.dirname(sf)
            skill_name = os.path.basename(skill_dir)
            
            # Simple header extraction
            desc = ""
            for line in content.split('\n')[:20]:
                if line.lower().startswith("description:"):
                    desc = line.split(":", 1)[1].strip()
                    break
                    
            chunks = chunk_text(content)
            points = []
            for idx, c in enumerate(chunks):
                header = f"[SKILL: {skill_name} | Chunk {idx+1}/{len(chunks)}]\n"
                final_text = (header + c)[:MAX_CHUNK_CHARS]
                emb = get_embedding(final_text)
                pt_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, f"{skill_name}_{idx}_{final_text[:30]}"))
                points.append({
                    "id": pt_id,
                    "vector": emb,
                    "payload": {
                        "type": "skill",
                        "skill_name": skill_name,
                        "description": desc,
                        "path": sf,
                        "chunk_index": idx,
                        "total_chunks": len(chunks),
                        "text": final_text,
                        "content": final_text
                    }
                })
            
            # Batch upsert
            upsert_points("codebase_knowledge", points)
            print(f"  [OK] Skill '{skill_name}': {len(points)} chunks indexed.")
            total_indexed += len(points)
            time.sleep(0.02)
        except Exception as e:
            print(f"  [ERR] Failed indexing skill at {sf}: {e}")
            
    print(f"Total skill chunks indexed: {total_indexed}")
    return total_indexed


def index_workspace_docs():
    """Indexes core architecture, topology, and guides into codebase_knowledge."""
    print("\n--- [2/4] Indexing Workspace Architecture & Topology Documents ---")
    total_indexed = 0
    for doc in WORKSPACE_DOCS:
        if not os.path.exists(doc):
            continue
        try:
            with open(doc, "r", encoding="utf-8", errors="replace") as f:
                content = f.read()
            
            title = os.path.basename(doc)
            chunks = chunk_text(content)
            points = []
            for idx, c in enumerate(chunks):
                header = f"[DOC: {title} | Section {idx+1}/{len(chunks)}]\n"
                final_text = (header + c)[:MAX_CHUNK_CHARS]
                emb = get_embedding(final_text)
                pt_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, f"{title}_{idx}_{final_text[:30]}"))
                points.append({
                    "id": pt_id,
                    "vector": emb,
                    "payload": {
                        "type": "workspace_doc",
                        "title": title,
                        "path": doc,
                        "chunk_index": idx,
                        "total_chunks": len(chunks),
                        "text": final_text,
                        "content": final_text
                    }
                })
            upsert_points("codebase_knowledge", points)
            print(f"  [OK] Doc '{title}': {len(points)} chunks indexed.")
            total_indexed += len(points)
            time.sleep(0.02)
        except Exception as e:
            print(f"  [ERR] Failed indexing {doc}: {e}")
            
    print(f"Total workspace doc chunks indexed: {total_indexed}")
    return total_indexed


def index_system_invariants_and_memories():
    """Indexes critical hardware, credentials patterns, ports, and operational rules into agent_memories."""
    print("\n--- [3/5] Indexing Core System Invariants & Operational Memories ---")
    invariants = [
        ("vulkan_naming", "Vulkan Device Naming Invariant: llama-server requires explicit strings '--device Vulkan0' and '--device Vulkan1'. Passing integer indices crashes the argument parser."),
        ("flash_attn_value", "Flash Attention Invariant: --flash-attn requires an explicit value ('on', 'off', 'auto'). Never omit the flag argument."),
        ("kv_cache_coordinator", "KV Cache Quantization: Coordinator 14B on RX 6750 XT 12GB uses '-ctk q4_0 -ctv q4_0' allowing a 12k context window without VRAM spill."),
        ("bge_context_limit", "BGE Embedder Context Limit (< 512 Tokens): Port 8003 (bge-large-en-v1.5) strictly bounds prompts/chunks to < 800-1000 characters. Exceeding causes HTTP 500."),
        ("host_ip_binding", "Host LAN IP Binding Reality: The Windows workstation is 127.0.0.1. StoneSage listens on 0.0.0.0:8080. Proxmox VIP is 127.0.0.1:8006."),
        ("ha_server_safety", "Home Assistant Switch Safety Invariant: NEVER toggle switch.server (powers the physical cluster node). switch.luna_s_feeder is vacation-only."),
        ("model_sampling_texture", "Quantized Model Texture Invariant: Use min_p: 0.05-0.08, temperature: 0.65-0.78, presence_penalty: 0.20-0.30 on local Qwen models to prevent collapse."),
        ("destructive_commands_gate", "Destructive Command Safety Rule: rm -rf, disk wiping, or volume deletion strictly requires explicit user interactive confirmation."),
        ("evaluator_blindspot", "Evaluator Lexical Leniency Bias: Sub-14B models score flawed code highly if syntax is clean. Deterministic tests or Tier-1 Frontier arbitration required.")
    ]
    points = []
    for key, text in invariants:
        emb = get_embedding(text)
        pt_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, f"invariant_{key}"))
        points.append({
            "id": pt_id,
            "vector": emb,
            "payload": {
                "type": "decision",
                "invariant_key": key,
                "title": key.replace('_', ' ').title(),
                "text": text,
                "content": text
            }
        })
    upsert_points("agent_memories", points)
    print(f"  [OK] Indexed {len(points)} operational invariants into 'agent_memories'.")
    return len(points)


def index_recent_conversations():
    """Indexes summary of recent conversation sessions into session_transcripts."""
    print("\n--- [4/5] Indexing Session Summaries & Transcripts ---")
    conv_logs = glob.glob(r"C:\Users\admin\.gemini\antigravity\brain\*\.system_generated\logs\transcript.jsonl")
    total_indexed = 0
    for log_file in conv_logs[:5]:  # Index top 5 recent sessions
        conv_id = log_file.split("brain")[1].split(".system_generated")[0].strip("\\/")
        user_prompts = []
        try:
            with open(log_file, "r", encoding="utf-8", errors="replace") as f:
                for line in f:
                    if '"type":"USER_INPUT"' in line:
                        try:
                            obj = json.loads(line)
                            content = obj.get("content", "")
                            if content and len(content.strip()) > 5:
                                user_prompts.append(content.strip()[:150])
                        except Exception:
                            pass
            if user_prompts:
                summary_text = f"Session {conv_id} Topics & Requests: " + " | ".join(user_prompts[-6:])
                summary_text = summary_text[:MAX_CHUNK_CHARS]
                emb = get_embedding(summary_text)
                pt_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, f"session_{conv_id}"))
                point = {
                    "id": pt_id,
                    "vector": emb,
                    "payload": {
                        "type": "transcript_summary",
                        "conversation_id": conv_id,
                        "text": summary_text,
                        "content": summary_text
                    }
                }
                upsert_points("session_transcripts", [point])
                print(f"  [OK] Session {conv_id[:8]}... summary indexed into 'session_transcripts'.")
                total_indexed += 1
        except Exception as e:
            print(f"  [ERR] Failed indexing transcript {conv_id}: {e}")
            
    print(f"Total session summaries indexed: {total_indexed}")
    return total_indexed


def index_obsidian_vault():
    """Indexes all notes from ClusterAdmin's primary Obsidian vault into Qdrant."""
    print("\n--- [5/5] Indexing ClusterAdmin's Primary Obsidian Vault Notes ---")
    vault_path = OBSIDIAN_VAULT_DIR
    if not os.path.exists(vault_path):
        print(f"  [WARN] Vault directory '{vault_path}' not found.")
        return 0

    md_files = []
    for root, dirs, files in os.walk(vault_path):
        # Ignore hidden/system dirs
        dirs[:] = [d for d in dirs if not d.startswith(".") and d not in ["node_modules", "smart_blocks", "smart_sources", ".trash"]]
        for f in files:
            if f.endswith(".md"):
                md_files.append(os.path.join(root, f))

    print(f"Found {len(md_files)} markdown notes in vault.")
    total_indexed = 0

    for note_path in md_files:
        try:
            rel_path = os.path.relpath(note_path, vault_path).replace("\\", "/")
            title = os.path.splitext(os.path.basename(note_path))[0]
            with open(note_path, "r", encoding="utf-8", errors="replace") as fh:
                raw_content = fh.read()

            # Clean frontmatter
            clean_content = re.sub(r"^---\n[\s\S]*?\n---\n", "", raw_content)
            if not clean_content.strip() or len(clean_content.strip()) < 15:
                continue

            # Determine routing category
            lower_rel = rel_path.lower()
            lower_cnt = clean_content.lower()
            if any(k in lower_rel or k in lower_cnt for k in ["bmw", "home info", "wedding", "accounting", "wgu", "degree", "clusteradmin", "f30"]):
                category = "companion_profile"
            elif any(k in lower_rel for k in ["todo", "task", "idea", "jot", "invariants"]):
                category = "agent_memories"
            else:
                category = "codebase_knowledge"

            chunks = chunk_text(clean_content)
            if not chunks:
                continue

            category_points = []
            vault_points = []

            for idx, c in enumerate(chunks):
                header = f"[{title} | Note Chunk {idx+1}/{len(chunks)}]\n"
                final_text = (header + c)[:MAX_CHUNK_CHARS]
                emb = get_embedding(final_text)
                pt_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, f"obsidian_{rel_path}_{idx}"))

                payload = {
                    "type": "obsidian_note",
                    "source": "obsidian",
                    "title": title,
                    "path": rel_path,
                    "category": category,
                    "chunk_index": idx,
                    "total_chunks": len(chunks),
                    "content": final_text,
                    "text": final_text,
                    "timestamp": time.time()
                }

                # 1. For category collection (companion_profile / codebase_knowledge / agent_memories)
                category_points.append({
                    "id": pt_id,
                    "vector": emb,
                    "payload": payload
                })

                # 2. For obsidian_vault hybrid collection (named vector 'dense')
                vault_points.append({
                    "id": pt_id,
                    "vector": {"dense": emb},
                    "payload": payload
                })

            if category_points:
                upsert_points(category, category_points)
            if vault_points:
                upsert_points("obsidian_vault", vault_points)

            print(f"  [OK] Note '{rel_path}': {len(chunks)} chunks -> {category} & obsidian_vault")
            total_indexed += len(chunks)
            time.sleep(0.02)
        except Exception as e:
            print(f"  [ERR] Failed indexing note at {note_path}: {e}")

    print(f"Total Obsidian vault chunks indexed: {total_indexed}")
    return total_indexed


def main():
    parser = argparse.ArgumentParser(description="Export homelab knowledge to Qdrant")
    parser.add_argument("--skills-only", action="store_true", help="Index only skills")
    parser.add_argument("--vault-only", action="store_true", help="Index only Obsidian vault notes")
    parser.add_argument("--all", action="store_true", default=True, help="Index skills, docs, invariants, sessions, and vault")
    args = parser.parse_args()

    print("==================================================================")
    print("🚀 HOMELAB VECTOR DATABASE SYNCHRONIZER (BGE-Large + Qdrant)")
    print("==================================================================")
    
    t0 = time.time()
    total_points = 0
    
    if args.vault_only:
        total_points += index_obsidian_vault()
    elif args.skills_only:
        total_points += index_skills()
    else:
        total_points += index_skills()
        total_points += index_workspace_docs()
        total_points += index_system_invariants_and_memories()
        total_points += index_recent_conversations()
        total_points += index_obsidian_vault()
        
    duration = time.time() - t0
    print("\n==================================================================")
    print(f"✅ EXPORT COMPLETE: {total_points} total vectors generated and upserted.")
    print(f"⏱️ Total Execution Time: {duration:.2f}s")
    print("==================================================================")

if __name__ == "__main__":
    main()

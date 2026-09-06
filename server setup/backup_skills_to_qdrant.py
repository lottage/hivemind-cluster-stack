#!/usr/bin/env python3
"""
Antigravity Skills Vector Brain Backup Engine
Scans all built-in, plugin, and workspace agent skills across the system,
generates 1024-dimensional BGE embeddings on the local RX 6600 XT,
and indexes them into Qdrant ('codebase_knowledge' & 'agent_memories').
"""

import os
import sys
import re
import uuid
import time
import requests
from typing import Dict, Any, List, Tuple

EMBED_URL = os.getenv("EMBED_URL", "http://192.168.1.105:8003")
QDRANT_URL = os.getenv("QDRANT_URL", "http://192.168.1.112:6333")

SKILL_ROOTS = [
    r"c:\Users\johna\OneDrive\Documents\.ai\.agents\skills",
    r"C:\Users\johna\.gemini\antigravity\builtin\skills",
    r"C:\Users\johna\.gemini\config\plugins"
]

def get_embedding(text: str) -> List[float]:
    """Fetch 1024-dimensional embedding from the RX 6600 XT BGE-Large engine."""
    resp = requests.post(
        f"{EMBED_URL}/v1/embeddings",
        json={"input": text, "model": "embedder"},
        timeout=30
    )
    resp.raise_for_status()
    return resp.json()["data"][0]["embedding"]

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
    resp = requests.put(
        f"{QDRANT_URL}/collections/{collection_name}/points",
        json=payload,
        timeout=15
    )
    resp.raise_for_status()
    return point_id

def chunk_text(text: str, max_chars: int = 850) -> List[str]:
    """Split markdown / instructions into digestible chunks that fit BGE 512-token limit."""
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

def parse_skill_md(file_path: str) -> Tuple[str, str, str]:
    """Parse frontmatter name, description, and markdown body from SKILL.md."""
    try:
        with open(file_path, "r", encoding="utf-8", errors="replace") as f:
            content = f.read()
    except Exception as e:
        return "", "", ""

    name = os.path.basename(os.path.dirname(file_path))
    desc = ""
    body = content

    # Check for YAML frontmatter
    fm_match = re.match(r"^---\s*\n(.*?)\n---\s*\n(.*)$", content, re.DOTALL)
    if fm_match:
        frontmatter = fm_match.group(1)
        body = fm_match.group(2).strip()

        name_match = re.search(r"^name:\s*(.+)$", frontmatter, re.MULTILINE)
        if name_match:
            name = name_match.group(1).strip().strip("'\"")

        desc_match = re.search(r"^description:\s*(?:>-\s*|\|-\s*|>\s*|\|\s*)?\n?(.*?)(?=\n[a-zA-Z0-9_-]+:|\Z)", frontmatter, re.DOTALL)
        if desc_match:
            desc = " ".join(line.strip() for line in desc_match.group(1).split("\n") if line.strip())

    if not desc:
        # Fallback to first non-heading paragraph
        paragraphs = [p.strip() for p in body.split("\n\n") if p.strip() and not p.strip().startswith("#")]
        if paragraphs:
            desc = paragraphs[0][:300]

    return name, desc, body

def backup_all_skills():
    print("=" * 70)
    print("  Antigravity Skills Vector Brain Backup Engine")
    print(f"  Embedder Engine: {EMBED_URL}")
    print(f"  Qdrant Storage:  {QDRANT_URL}")
    print("=" * 70)

    # 1. Discover all SKILL.md files
    all_skill_files = []
    for root_dir in SKILL_ROOTS:
        if not os.path.exists(root_dir):
            continue
        for root, dirs, files in os.walk(root_dir):
            for file in files:
                if file.lower() == "skill.md":
                    all_skill_files.append(os.path.join(root, file))

    print(f"\n[Discovery] Found {len(all_skill_files)} active skills across system.\n")

    total_chunks_indexed = 0
    catalog_entries_saved = 0

    for idx, skill_path in enumerate(all_skill_files):
        skill_name, skill_desc, skill_body = parse_skill_md(skill_path)
        if not skill_name:
            continue

        print(f"[{idx+1}/{len(all_skill_files)}] Indexing Skill: '{skill_name}'...")

        # A. Store Catalog Card in 'agent_memories'
        catalog_card = (
            f"### Agent Skill: {skill_name}\n"
            f"**Description**: {skill_desc}\n"
            f"**File Location**: {skill_path}\n\n"
            f"**Overview & Instructions**:\n{skill_body[:600]}"
        )
        cat_meta = {
            "project": "agent_skills",
            "skill_name": skill_name,
            "category": "skills_catalog",
            "doc_type": "skill_catalog_entry",
            "source_path": skill_path,
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")
        }
        try:
            upsert_point("agent_memories", catalog_card, cat_meta)
            catalog_entries_saved += 1
        except Exception as e:
            print(f"  [WARN] Failed to upsert catalog card: {e}")

        # B. Chunk and Index Full Instructions in 'codebase_knowledge'
        chunks = chunk_text(skill_body, max_chars=850)
        for c_idx, chunk in enumerate(chunks):
            chunk_content = (
                f"### Skill Documentation: {skill_name} (Section {c_idx+1}/{len(chunks)})\n"
                f"**Skill Overview**: {skill_desc}\n\n"
                f"{chunk}"
            )
            chunk_meta = {
                "project": "agent_skills",
                "skill_name": skill_name,
                "doc_type": "skill_procedure",
                "source_path": skill_path,
                "chunk_index": c_idx + 1,
                "total_chunks": len(chunks),
                "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")
            }
            try:
                upsert_point("codebase_knowledge", chunk_content, chunk_meta)
                total_chunks_indexed += 1
            except Exception as e:
                print(f"  [WARN] Chunk {c_idx+1} error: {e}")

    print("\n" + "=" * 70)
    print(f"  Backup Complete!")
    print(f"  Total Skills Processed:     {len(all_skill_files)}")
    print(f"  Catalog Cards in Memories: {catalog_entries_saved}")
    print(f"  Procedure Chunks in Knowledge: {total_chunks_indexed}")
    print("=" * 70)

    # Verification Tests
    print("\n[Verification 1] Testing Semantic Search: 'homelab passwordless ssh keys'...")
    vec1 = get_embedding("homelab passwordless ssh keys to linux and proxmox")
    payload1 = {"vector": vec1, "limit": 2, "with_payload": True}
    res1 = requests.post(f"{QDRANT_URL}/collections/codebase_knowledge/points/search", json=payload1, timeout=10)
    hits1 = res1.json().get("result", [])
    for h in hits1:
        name = h.get("payload", {}).get("metadata", {}).get("skill_name", "Unknown")
        score = h.get("score", 0)
        print(f"  Top Match (Score {score:.4f}): Skill '{name}'")

    print("\n[Verification 2] Testing Semantic Search: 'protein 3D structures and alphafold'...")
    vec2 = get_embedding("protein 3D structures and alphafold database analysis")
    payload2 = {"vector": vec2, "limit": 2, "with_payload": True}
    res2 = requests.post(f"{QDRANT_URL}/collections/agent_memories/points/search", json=payload2, timeout=10)
    hits2 = res2.json().get("result", [])
    for h in hits2:
        name = h.get("payload", {}).get("metadata", {}).get("skill_name", "Unknown")
        score = h.get("score", 0)
        print(f"  Top Match (Score {score:.4f}): Skill '{name}'")

if __name__ == "__main__":
    backup_all_skills()

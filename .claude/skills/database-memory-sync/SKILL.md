# Database Memory & Skill Synchronizer

name: database-memory-sync
description: Exports and indexes every usable skill, memory, architectural invariant, workspace documentation item, device registry, and conversation transcript into the homelab Qdrant vector database (LXC 117). Ensures models can retrieve specialized skills and procedural knowledge on-demand via vector search at minimal token cost.

---

## Overview

This skill indexes the entire operational fabric of the homelab AI ecosystem into Qdrant. Rather than cramming dozens of skill manuals and device tables into prompt contexts (burning thousands of tokens per turn), agents query `codebase_knowledge` and `agent_memories` using concise semantic queries to pull only relevant procedural blocks (< 800 chars).

## When to Use

- When new skills, tools, or plugins are created or modified
- When infrastructure topology, IPs, ports, or hardware change
- When synchronizing recent conversation session transcripts into persistent memory
- When refreshing the database summary note in Obsidian

## Qdrant Collections Target Matrix

| Collection | Target Content | Payload Schema |
| :--- | :--- | :--- |
| **`codebase_knowledge`** | Usable skills, workspace guides, architecture invariants, device registry | `{"type": "skill"\|"workspace_doc", "name": str, "chunk": int, "text": str}` |
| **`agent_memories`** | Key operational decisions, calibrated sampling profiles, verified rules | `{"type": "decision"\|"rule", "title": str, "text": str}` |
| **`session_transcripts`** | Summarized conversation trajectories and critical tool runs | `{"type": "transcript_summary", "conversation_id": str, "text": str}` |
| **`companion_profile`** | Topology parameters, hardware specifications, user preferences | `{"type": "system_profile", "key": str, "text": str}` |

## Embedding Invariant (Strict Constraint)

- **Port 8003 Context Limit**: `bge-large-en-v1.5` on RX 6600 XT (`127.0.0.1:8003`) has a strict 512-token context limit.
- **Rule**: All chunks MUST be strictly bounded to **< 800 characters** before calling `/v1/embeddings`. Any payload exceeding this will cause `llama-server` HTTP 500 errors.

## CLI Usage

### Full Export / Re-indexing
```bash
python .agents/skills/database-memory-sync/export_all_to_database.py --all
```

### Sync Skills Only
```bash
python .agents/skills/database-memory-sync/export_all_to_database.py --skills-only
```

### Sync Database Summary to Obsidian
```bash
python .agents/skills/database-memory-sync/sync_db_to_obsidian.py
```

## Minimal-Token Retrieval Pattern for Agents

To retrieve a skill without inflating context:
```python
# Call search_memory with concise keywords:
results = call_mcp_tool(
    ServerName="pve-cluster",
    ToolName="search_memory",
    Arguments={
        "collection_name": "codebase_knowledge",
        "query": "ha voice triggers movie night syntax",
        "limit": 2
    }
)
```
Only the specific execution instructions are returned, keeping prompt context light.

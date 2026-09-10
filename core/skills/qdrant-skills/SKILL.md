---
name: qdrant-skills
description: "Production Qdrant vector database engineering, Universal Query API, Hybrid Search (dense BGE + sparse BM25 with RRF), MMR diversity tuning, payload indexing, and search quality optimization for the local homelab brain on LXC 117 (skills.qdrant.tech)."
---

# Qdrant Skills & Vector Brain Optimization Guide

Directly derived from the official `skills.qdrant.tech` specification and tailored for the local dual-GPU cluster and vector brain running Qdrant 1.19.0 on LXC 117 (`127.0.0.1:6333`) with hardware-accelerated `bge-large-en-v1.5` embeddings on port 8003.

## 1. Local Vector Brain Topology
- **Host Endpoint**: `http://127.0.0.1:6333` (LXC 117)
- **Engine Version**: Qdrant `v1.19.0`
- **Dense Embeddings**: `bge-large-en-v1.5` (1024 dimensions, Cosine distance) on AMD Radeon RX 6600 XT (`:8003`)
- **Active Collections**:
  1. `companion_profile`: Operator's personal preferences, background, and companion directives.
  2. `home_automation_registry`: Device states, entities, Matter IDs, and HA blueprints.
  3. `codebase_knowledge`: Ingested workspace files, architectural invariants, and technical lessons.
  4. `agent_memories`: Episodic agent memories, task completions, and working insights.
  5. `session_transcripts`: Historical conversation turns and reasoning chains.
  6. `autonomous_thinking`: Autonomous cycle exploration dossiers, 14B invariants, and Frontier audit verdicts.

---

## 2. Core Architectural Upgrades from `skills.qdrant.tech`

### A. Universal Query API (`/collections/{name}/points/query`)
In Qdrant 1.19+, migrate from legacy `/points/search` to the unified Query API:
```json
{
  "query": [0.012, -0.045, 0.089],
  "limit": 5,
  "with_payload": true,
  "params": {
    "hnsw_ef": 128,
    "exact": false
  }
}
```

### B. Maximal Marginal Relevance (MMR) for Result Diversity
- **Problem**: In dense knowledge domains (Obsidian notes, codebase knowledge), standard vector search returns 5 redundant chunks from the exact same file.
- **Fix**: Add MMR diversity parameter (`diversity=0.5`):
```json
{
  "query": [0.012, -0.045, 0.089],
  "limit": 5,
  "with_payload": true,
  "params": {
    "diversity": 0.5
  }
}
```

### C. Hybrid Search (Dense + Lexical BM25 with Reciprocal Rank Fusion)
- **Problem**: Dense embeddings miss exact technical keywords, acronyms, or model identifiers (`RX 6750 XT`, `LXC 117`, `WGU C715`, `Vulkan0`).
- **Fix**: Run parallel prefetches combining dense vectors and sparse lexical tokens, then fuse using Reciprocal Rank Fusion (`rrf`):
```json
{
  "prefetch": [
    { "query": [0.012, -0.045], "using": "dense", "limit": 20 },
    { "query": { "values": [1.2, 0.8], "indices": [42, 108] }, "using": "sparse", "limit": 20 }
  ],
  "query": { "fusion": "rrf" },
  "limit": 5,
  "with_payload": true
}
```

### D. Payload Indexing for Fast Subgraph Traversal (ACORN)
- **Problem**: Filtering on payload fields (`category`, `source`, `filename`, `created_at`) without payload indexes forces full unindexed sequential scans across all points.
- **Fix**: Create keyword and integer payload indexes:
```json
PUT /collections/codebase_knowledge/index
{
  "field_name": "category",
  "field_schema": "keyword"
}
```

### E. Discovery & Relevance Feedback for Autonomous Cycles
- **Problem**: A static cosine cutoff (< 0.85) can be fooled by superficial paraphrasing while rejecting genuine conceptual breakthroughs.
- **Fix**: Use the Discovery API with positive and negative vector pairs to steer autonomous explorations into genuinely novel territory.

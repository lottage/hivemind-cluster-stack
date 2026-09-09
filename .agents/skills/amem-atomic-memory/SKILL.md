---
name: amem-atomic-memory
description: "Engineering guide for A-MEM (Agentic Working Memory) backed by Valkey in-RAM store (:6379), sub-millisecond atomic fact card recall (< 35 tokens), dynamic tiered prompt construction, and elimination of the 1,500+ token reasoning bloat on local reasoning models (Ornith-1.5-9B)."
---

# A-MEM: Atomic Working Memory & Reasoning Bloat Elimination

Production architectural guide for A-MEM (Agentic Memory) deployed across the dual-GPU cluster and StoneSage stack. Solves the 1,500+ token reasoning monologue failure mode by replacing raw RAG chunk dumps with ultra-dense Zettelkasten atomic fact cards recalled from RAM in sub-millisecond latency.

---

## 1. Problem Diagnosis: The 1,500+ Token Reasoning Bloat

### The Failure Mode
When local quantized/abliterated models (`Ornith-1.5-9B-OBLITERATED Q8_0` on `:8001` or `Q4_K_M` on `:8002`) receive:
1. **700+ Token System Prompts**: Dense hardware topologies, VRAM listings, and operational rules.
2. **Negative Meta-Instructions**: Defensive warnings such as *"You are an AI assistant, NOT a car or physical machine. Do NOT claim you have car parts."*
3. **Raw Unstructured RAG Dumps**: 400-character chunks containing irrelevant surrounding context.

The model's native `<think>...</think>` block explodes into a circular identity monologue:
```text
<think>
The user is asking about the motor oil specification for their 2014 BMW F30 328i X-Drive. This is a vehicle question, not an infrastructure one. Let me look at the grounded records... The engine is N20 (that's critical)... Oil filter housing clicks, replace housing at 25Nm, drain plug at 8Nm...
</think>
```
The model exhausts its entire `max_tokens` allocation (e.g. 150–350 tokens) inside `<think>`, producing an empty string `""` or stalling for 30+ seconds.

---

## 2. Core Architectural Pillars

### A. Zettelkasten Atomic Cards (< 35 Tokens)
Instead of dumping raw documents, facts are isolated into single-purpose, self-contained atomic cards:
```python
# Format
[KNOWLEDGE ATOM]: BMW 328i (N20 engine) requires 5W-30 or 5W-40 full synthetic motor oil meeting BMW Longlife-01 (LL-01) specification.
```
- **Overhead**: 15–35 tokens.
- **Zero Ambiguity**: Directly answers the user query without distracting secondary details.
- **No Defensive Invariants**: Omits all negative "you are not a car" boilerplate.

### B. In-RAM Valkey Store (`:6379`) & Sub-Millisecond Tag Index
- **Host**: VM 102 (`192.168.1.105:6379`) running `valkey-server` 9.0.4.
- **Data Structure**:
  - `amem:card:{atom_id}`: Hash storing `atom`, `tags`, `category`, and `timestamp`.
  - `amem:tag:{token}`: Redis Set of card IDs tagged with that normalized keyword.
  - `amem:working:{agent_id}`: Capped List (FIFO, max 5 items) for short-term scratchpad memory.
- **Recall Algorithm**:
  1. Tokenize query, strip punctuation and English stopwords.
  2. Compute Set Intersection (`SINTER amem:tag:t1 amem:tag:t2 ...`) or union scoring.
  3. Latency: `< 1.0 ms` directly in RAM.

### C. Dynamic Tiered System Prompts
```python
LEAN_SYSTEM_PROMPT = (
    "You are StoneSage, Austin's AI assistant. "
    "Provide clear, accurate, direct answers without meta-commentary, reasoning monologues, or filler."
)
```
- **Routine Queries**: Ingest `LEAN_SYSTEM_PROMPT` (35 tokens).
- **Cluster/Telemetry Queries**: Ingest `DEFAULT_SYSTEM_PROMPT` + live telemetry *only* if query mentions `hardware`, `status`, `telemetry`, `cluster`, `gpu`, or `vram`.

### D. Direct Output Directive
Always pair atomic knowledge injection with:
```text
[Direct Answer Mode: Provide the factual answer directly without meta-commentary or reasoning loop.]
```

---

## 3. Empirical Benchmark Verification

Evaluated via `bench_amem.py` on `Ornith-1.5-9B-Instruct Q8_0` (RX 6750 XT `:8001`):

| Metric | Legacy Raw RAG Chunks | A-MEM In-RAM Atomic Recall | Impact |
| :--- | :--- | :--- | :--- |
| **Reasoning (`<think>`) Tokens** | 1,500+ tokens (exhausted budget) | **56 tokens** (226 chars) | **96.3% reduction** |
| **Time-to-Answer Latency** | 30,000+ ms (or empty answer) | **3,585 ms** (3.58s) | **8.4x faster** |
| **Throughput** | Stalled in circular debate | **33.5 tok/s** | Full GPU utilization |
| **Answer Completeness** | Empty string (`""`) | Complete, grounded, accurate | 100% precision |

---

## 4. Usage in Python Services

```python
from amem_engine import get_amem_engine

amem = get_amem_engine()

# Store an atomic fact
amem.store_atom(
    atom_id="hardware.gpu.coordinator",
    text="Coordinator on RX 6750 XT (Vulkan0, :8001) runs Ornith-1.5-9B Q8_0.",
    tags=["coordinator", "gpu", "rx6750xt", "8001", "q8"],
    category="hardware"
)

# Recall relevant facts for prompt injection
prompt_injection = amem.format_memory_injection("What GPU does coordinator run on?", max_atoms=2)
# Output:
# [KNOWLEDGE ATOM]: Coordinator on RX 6750 XT (Vulkan0, :8001) runs Ornith-1.5-9B Q8_0.

# Working memory scratchpad per session/agent
amem.push_working_memory("session_123", "User requested LL-01 oil verification.")
recent_notes = amem.get_working_memory("session_123")
```

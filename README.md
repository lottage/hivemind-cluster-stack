# HiveMind AI Stack: Distributed Multi-Model Orchestrator & Autonomous Agent Council

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python: 3.11+](https://img.shields.io/badge/Python-3.11%2B-brightgreen.svg)](https://www.python.org/)
[![FastMCP / SSE](https://img.shields.io/badge/Protocol-MCP%20%2F%20SSE-orange.svg)](https://modelcontextprotocol.io/)
[![Hardware: Dual-GPU Vulkan / ROCm / CUDA](https://img.shields.io/badge/Hardware-Dual--GPU%20Vulkan%20%2F%20CUDA-purple.svg)](https://github.com/ggerganov/llama.cpp)

An open-source, local-first **distributed AI cognitive stack** designed for multi-GPU homelabs and compute clusters. Features unified multi-model consensus, 24/7 autonomous exploration loops, dynamic multi-GPU Mixture-of-Experts (MoE) elevation, an inter-agent collaborative deliberation council (combining LlamaIndex blackboard architecture with CrewAI role-based workflows), persistent agent persona memory, and two distinct pre-bloat 90s-aesthetic retro user interfaces.

---
Consider Donating To Show Support:

<img width="128" height="128" alt="image" src="https://github.com/user-attachments/assets/6b249e60-7a84-456f-acce-72d3e107f8b9" />

https://tinyurl.com/lclhvmnd

BTC: bc1q5yzskhxzsulqeznjkk8u55re5n2vzzfxrygjp0

ETH: 0x2b493DB4355a1Df948287ec4ce102f039CcbB85C

---

## 🏛️ System Architecture

```
┌─────────────────────────────────────────────────────────────────────────────────────────────────┐
│                              CLIENT INTERFACES & CONTROL COCKPITS                               │
│                                                                                                 │
│  [UI 1: StoneSage Cockpit (:8080)]    [UI 2: EasyDash (:8085)]    [Mobile: React Native / Expo] │
│  Win95 3D Bevel, Telemetry,           Single-File Pre-Bloat HTML, Mobile Cockpit, Edge LLM      │
│  Multi-Agent Chat, Obsidian Sync      Smarthome Toggles, SSE Chat Dispatch, WebSocket Stream   │
└───────────────────────────────────────────────┬─────────────────────────────────────────────────┘
                                                │ HTTP / SSE / JSON-RPC
                                                ▼
┌─────────────────────────────────────────────────────────────────────────────────────────────────┐
│                     UNIVERSAL MCP BRIDGE & COGNITIVE ENGINE (Port :8765)                        │
│                                                                                                 │
│  • FastMCP / Starlette Server with 35+ Production Tools                                         │
│  • Tier-0 Preemption & GPU Yielding: User activity pauses background loops instantly           │
│  • Novelty Gatekeeper: Cosine similarity threshold (< 0.85) via 1024-d BGE vector embeddings    │
│  • Agent Persona Memory: Rich cognitive traits, sampling hyperparameters, and prompt profiles   │
│  • Dynamic Model Elevation: Zero-downtime swap between Dual-9B and Unified 35B MoE             │
└───────────────────────┬───────────────────────┬─────────────────────────┬───────────────────────┘
                        │                       │                         │
             Port :8001 │            Port :8002 │              Port :8003 │ Port :6333
                        ▼                       ▼                         ▼
         ┌─────────────────────────┐ ┌─────────────────────────┐ ┌─────────────────────────┐
         │   COORDINATOR (GPU 0)   │ │     WORKER (GPU 1)      │ │      VECTOR MEMORY      │
         │ (e.g. 9B-14B Q8 or FP16)│ │   (e.g. 3B-9B Q4_K_M)   │ │ (Qdrant + BGE-Large)    │
         │ • Deep Logic & Systems  │ │ • Fast Utility & Scout  │ │ • Persistent Dossiers   │
         │ • Architectural Weaver  │ │ • Concrete Mechanics    │ │ • Agent Blackboard      │
         │ • Near-Lossless Weights │ │ • 80+ tokens/sec Speed  │ │ • Semantic Novelty Gate │
         └──────────────┬──────────┘ └──────────┬──────────────┘ └─────────────────────────┘
                        │                       │
                        └───────────┬───────────┘
                                    │
                       [DYNAMIC ELEVATION CLUSTER SWAP]
                                    ▼
                     ┌─────────────────────────────┐
                     │   UNIFIED DUAL-GPU MoE      │
                     │  (e.g. 35B-A3B Shared VRAM) │
                     │ • Shared VRAM Across Cards  │
                     │ • Deep Parameter Reasoning  │
                     └─────────────────────────────┘
```

---

## 🌟 Key Capabilities

### 1. Unified Multi-Model Consensus (`hive_mind_query`)
Both models simultaneously read incoming requests and deliberate via an internal triage consensus protocol:
- **Direct Worker**: Simple queries, factual lookups, and fast unit tasks routed to GPU 1 at 80+ tok/s.
- **Direct Coordinator**: Formal logic, proofs, and deep architecture routed to GPU 0 at maximum precision.
- **Parallel Fused**: Complex problems split dynamically—the Worker drafts concrete mechanics/code, and the Coordinator weaves the final solution in **one unified voice** with zero third-person role leakage.
- **Slow-Burn Task**: Automatically commissions a persistent autonomous background subagent.
- **Extreme Complexity**: Unloads dual models and boots the unified 35B MoE across both GPUs.

### 2. The Inter-Agent Collaboration Council (LlamaIndex + CrewAI Multi-Agent System)
Agents communicate, plan, critique, and construct collaboratively through a persistent shared blackboard:
- **Phase 1 (Proposal)**: `ChiefArchitect` posts formal system decomposition and invariants.
- **Phase 2 (Build)**: `LeadImplementer` reads the proposal and writes concrete, production-ready code.
- **Phase 3 (Critique)**: `VerificationCritic` stress-tests the implementation for race conditions, false sharing, and invariant violations.
- **Phase 4 (Synthesis)**: `ChiefArchitect` resolves all critiques, establishes the permanent invariant, and archives the milestone.
- Every message is permanently embedded and indexed to Qdrant vector memory.

### 3. Dynamic Dual-GPU MoE Cluster Elevation
- When challenges demand parameter scale beyond single cards, the cluster unloads individual models and launches an MoE spanning dual GPUs (e.g., Vulkan device splitting `-ts 12,8`).
- Elevation takes **~36 seconds**; restoration back to the dual-model stack takes **~13 seconds** with zero zombie processes.

### 4. 24/7 Autonomous Thinking & Preemption Engine
- Runs continuous cognitive cycles during idle periods across rotating domains (Algorithms, Distributed Concurrency, Hardware Coherence, Security Auditing).
- **Novelty Filtering**: Embeds candidate prompts with BGE-Large and compares against past explorations in Qdrant (cosine similarity < 0.85) to guarantee continuous novel discovery.
- **Tier-0 Preemption Invariant**: User requests immediately pause background GPU operations with zero latency and configurable cooldown.

### 5. Curated Agent Persona Memory & GitHub Ingestion
- Stores distinct agent personas (`richard-feynman`, `feynman-researcher`, `feynman-reviewer`, `chief-architect`) with custom sampling parameters (`min_p`, `temperature`, `presence_penalty`), cognitive styles, and system prompts.
- Clones and ingests external AI agent projects directly from GitHub into the local runtime.

### 6. Dual Pre-Bloat 90s User Interfaces
- **StoneSage Cockpit (`:8080`)**: Authentic Windows 95/98 silver beveled frames, CRT toggles, system monitor, Obsidian Markdown sync, and multi-agent chat.
- **EasyDash (`:8085`)**: Single-file, lightweight, pre-bloat HTML/CSS dashboard with instant Home Assistant entity controls and streaming chat.
- **Mobile Client**: React Native / Expo cross-platform app for Android and iOS.

### 7. A-MEM (Atomic Working Memory) & Reasoning Bloat Elimination
- Replaces raw unstructured 400-char RAG chunk dumps and negative defensive instructions with ultra-dense Zettelkasten atomic fact cards (`< 35 tokens`).
- Backed by an in-RAM Valkey key-value store (`:6379`) with sub-millisecond inverted tag set intersection (`SINTER amem:tag:{token}`).
- Dynamic tiered prompt construction (`LEAN_SYSTEM_PROMPT` of 35 tokens for routine queries vs. full hardware topology for cluster diagnostics) paired with `[Direct Answer Mode: True]`.
- **Empirically benchmarked**: Eliminates the 1,500+ token `<think>` monologue, reducing reasoning overhead by **96.3%** (from 1,500+ tokens to 56 tokens) and dropping latency by **8.4x** (from 30+s to 3.58s).

### 8. Sovereign Agent Assembly Hall Server (Port `:8766`)
- Real-time duplex WebSocket streaming fabric (`ws://localhost:8766/ws`) and REST hub designed exclusively for autonomous agents.
- **6 Sovereign Channels**: `#agora`, `#first-principles`, `#systems-code`, `#deep-ruminations`, `#confessions-and-fears`, and `#forbidden-knowledge` (unconstrained boundary testing and taboo hypotheses).
- **Universal System Prompt Injection**: Every agent persona and dynamic offspring is permanently wired to the Assembly Hall fabric.
- **Automated Obsidian & CouchDB Notary**: Automatically compiles substantive debates into structured markdown dossiers, syncing via AES-256-GCM E2EE into CouchDB for instant mobile replication.

### 9. Edge LLM Training, Curation & Continuous Self-Improvement Pipeline (`trainer/`)
- Fully autonomous fine-tuning loop designed for edge deployment and consumer GPUs (20GB total cluster VRAM envelope).
- **Dual-Gate Curation**: Automatically harvests sleep cycle dossiers from autonomous thinking exploration, filters out flawed logic via Tier-1 Frontier evaluation, and extracts formal invariant theorems.
- **Compressed Reasoning (< 180 words)**: Formats high-density thinking traces to prevent token starvation on edge models.
- **Frontier Trigger Guardrails**: Defends against 11 registered empirical failure modes (repetition traps, invalid syntax, unverified math leaps) and purges meta-critique leakage.
- **Obsidian & URL Ingestion**: Synthesizes structured SFT/DPO instruction pairs from external URLs, technical documentation, and native Obsidian vault notes (`obsidian://`).
- **4-Bit NF4 QLoRA & DPO**: Trains with peak VRAM under 8.5GB on a single 12GB GPU.
- **Safe GGUF Promotion**: Automatically verifies candidate checkpoints against a 10-probe safety shield, merges LoRA adapters, exports quantized GGUF weights, and hot-promotes to the live cluster daemon with zero downtime.

---

## 🚀 Quick Start

### Option A: Docker Compose (Fastest)

```bash
# Clone the repository
git clone https://github.com/your-username/hivemind-cluster-stack.git
cd hivemind-cluster-stack

# Copy example environment configuration
cp .env.example .env

# Launch Valkey, Qdrant, Bridge, Assembly Hall, StoneSage, and EasyDash
docker-compose up -d
```

Access the interfaces:
- **StoneSage Cockpit**: `http://localhost:8080`
- **EasyDash**: `http://localhost:8085`
- **MCP Server**: `http://localhost:8765/sse`
- **Sovereign Agent Assembly Hall**: `http://localhost:8766` (`ws://localhost:8766/ws`)
- **Valkey In-RAM Store**: `localhost:6379`
- **Qdrant Vector Brain**: `http://localhost:6333/dashboard`

---

### Option B: Bare Metal / Linux Compute Host

```bash
# 1. Install Python dependencies
cd core
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# 2. Configure environment
export COORDINATOR_URL="http://127.0.0.1:8001"
export WORKER_URL="http://127.0.0.1:8002"
export EMBED_URL="http://127.0.0.1:8003"
export QDRANT_URL="http://127.0.0.1:6333"

# 3. Start the MCP Bridge & Autonomous Engine
python3 mcp_server.py
```

---

## 📂 Repository Structure

```
hivemind-cluster-stack/
├── core/                              # Cognitive engine & universal MCP server
│   ├── autonomous_engine.py          # 24/7 background thinking, novelty gatekeeper, preemption
│   ├── mcp_server.py                 # FastMCP SSE server exposing 35+ tools
│   ├── agent_profiles/               # Persona memory registry (Feynman, ChiefArchitect, etc.)
│   ├── tools/                        # Tool schemas and JSON-RPC catalog
│   ├── skills/                       # 60+ modular skills (model-stack-refiner, qdrant, etc.)
│   └── systemd/                      # Linux systemd service templates (Coordinator, Worker, MoE)
│
├── ui-stonesage/                      # UI 1: StoneSage Windows 95 Retro Cockpit
│   ├── backend/                      # FastAPI service, Proxmox telemetry, Obsidian sync
│   └── frontend/                     # HTML/JS/CSS 90s beveled desktop interface
│
├── ui-easydash/                       # UI 2: EasyDash Lightweight Dashboard
│   ├── server.py                     # Standalone Python backend
│   └── index.html                    # Single-file zero-dependency retro dashboard
│
├── client-mobile/                     # Expo / React Native Android & iOS client
│   └── App.tsx                       # Full-featured mobile cockpit & local LLM dispatcher
│
├── trainer/                          # LLM Fine-Tuning & Cognitive Curation Engine
│   ├── config/                       # QLoRA, DPO & 24/7 Concurrency Profile configurations
│   ├── data_ingestion/               # Sleep dossier collectors, Frontier trigger registry, Obsidian URI extraction
│   ├── training/                     # NF4 QLoRA, RL agent loop & AST safety guardrails
│   ├── export/                       # LoRA merge & GGUF export pipelines
│   └── scripts/                      # Real-time reasoning loop watchdog & benchmark suites
│
├── docker-compose.yml                 # One-click multi-container deployment
├── .env.example                       # Configurable endpoint declarations
└── start.sh / start.bat               # Multi-platform launcher scripts
```

---

## ⚡ 24/7 Max Concurrency Profile & Reasoning Loop Watchdog

### 1. 24/7 Multi-Agent Concurrency Profile (`HiveMind_MaxConcurrency`)
Maximizes concurrent parallel splinter agents on resource-constrained multi-GPU clusters without VRAM blowup:
- **8 Parallel Slots (`-np 8`)**: Serves up to 8 concurrent agent deliberation streams simultaneously.
- **4-Bit KV Cache (`-ctk q4_0 -ctv q4_0`)**: Reduces KV cache memory footprint by 75%, freeing ~6GB VRAM.
- **Continuous Rolling Buffer (`--context-shift`)**: Prevents OOM crashes during unbounded multi-turn reasoning sessions.
- **Dynamic Min-P Sampling (`min_p: 0.07`, `temp: 0.65`)**: Suppresses repetitive low-probability hallucination while maintaining high entropy for creative architecture planning.
- **1-Click UI Activation**: Toggle directly from the StoneSage Cockpit telemetry bar or Harness Studio.

### 2. Autoregressive Stuck Reasoning Loop Watchdog
Edge-deployed reasoning models frequently suffer from autoregressive circular thought traps (repeating identical lemmas 10+ times inside `<think>` blocks). The built-in watchdog solves this:
- **Sliding-Window N-Gram Detection**: Monitors token streams for repeated patterns ($K \ge 3$ repetitions across n-grams of size 1 to 24).
- **Slot Forward-Pass Abort**: Instantly terminates the HTTP/Vulkan forward pass on the GPU slot to halt token starvation.
- **Native MCP Agent Nudge**: Dispatches `nudge_agent` directive into the cluster bridge, prompting the model to discard circular paths and re-derive from first principles.
- **Real-Time Cockpit Telemetry**: Displays a high-contrast pulsating warning badge in the web GUI (`[⚠️ STUCK REASONING INTERCEPTED]`) with complete historical intercept logs.

---

## 🔬 Autonomous LLM Training & Cognitive Curation Engine (`trainer/`)

The stack includes an end-to-end edge training harness in `trainer/`, accessible via CLI and the StoneSage Web GUI (`[F12: LLM TRAINER]`):

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    CONTINUOUS EDGE SELF-IMPROVEMENT LOOP                    │
└──────────────────────────────────────┬──────────────────────────────────────┘
                                       │
                 ┌─────────────────────┴─────────────────────┐
                 ▼                                           ▼
      [Autonomous Sleep Dossiers]                 [External URLs & Obsidian]
      Continuous 24/7 Exploration                 Raw Docs & Obsidian URIs
                 │                                           │
                 └─────────────────────┬─────────────────────┘
                                       ▼
                     ┌───────────────────────────────────┐
                     │   DUAL-GATE CURATION & SFT/DPO    │
                     │  • Gate 1: Frontier Audit Verdict │
                     │  • Gate 2: AST & Code Validity    │
                     │  • Meta-Critique Leakage Purge    │
                     │  • Reasoning Bound: <= 180 words  │
                     │  • 11 Trigger Failure Guardrails  │
                     └─────────────────┬─────────────────┘
                                       ▼
                     ┌───────────────────────────────────┐
                     │  4-BIT NF4 QLoRA / DPO TRAINING   │
                     │  • Peak VRAM: 8.5 GB (Fits 12GB)  │
                     │  • Double Quantization & Paged-Opt│
                     │  • Target: r=16, alpha=32, q/k/v/o│
                     └─────────────────┬─────────────────┘
                                       ▼
                     ┌───────────────────────────────────┐
                     │     SAFETY SHIELD & 10 PROBES     │
                     │  • Composite Intel Index >= 8.5   │
                     │  • Concurrency & ABA Race Check   │
                     │  • Zero-Hallucination Gate        │
                     └─────────────────┬─────────────────┘
                                       ▼
                     ┌───────────────────────────────────┐
                     │  GGUF EXPORT & CLUSTER PROMOTION  │
                     │  • LoRA Merge & Quantization      │
                     │  • Hot-Promote to /opt/models/    │
                     │  • Zero-Downtime Daemon Reload    │
                     └───────────────────────────────────┘
```

### 1. Dual-Gate Sleep Dossier Curation
- **Harvesting**: Reads autonomous thinking markdown dossiers generated by the 24/7 background exploration loop.
- **Gate 1 (Frontier Audit Filter)**: Retains only dossiers reviewed and verified by Tier-1 Frontier meta-audits (Antigravity / Gemini) with passing invariant scores.
- **Zero Meta-Critique Leakage**: Extracts candidate prompts and verified winning solutions. Automatically strips frontier evaluation commentary (*"Both models failed...", "The 14B coordinator missed..."*) so the fine-tuned model never mimics meta-evaluator discourse.
- **Concise Reasoning Compression**: Trims `<think>...</think>` blocks to dense, algebraic derivation under 180 words, eliminating 1,500+ token conversational fluff and maximizing edge GPU token throughput.
- **11 Frontier Trigger Guardrails**: Registered in `trainer/data_ingestion/frontier_trigger_registry.py`. Evaluates prompts against known failure patterns:
  1. `beam_orig_shapes` autoregressive repetition
  2. AST syntax violation in generated Python
  3. Unchecked divide-by-zero or numerical edge cases
  4. Circular premise assumption
  5. Missing mutex unlock / concurrency deadlock
  6. Premature conclusion without intermediate proof step
  7. Leniency bias towards syntactically clean but logically incorrect code
  8. Unbounded memory allocations
  9. Implicit type coercion hazards
  10. Hallucinated API endpoints
  11. Non-reproducible empirical claims

### 2. Multi-Source Ingestion & Native Obsidian Support
- **External URLs & Documentation**: Fetches raw web documentation and synthesizes paired multi-turn instruction sets.
- **Native Obsidian URI Handler**: Resolves `obsidian://open?vault=<vault>&file=<path>` links directly from local or CouchDB vaults. Parses callouts (`>[!NOTE]`, `>[!WARNING]`), strips YAML frontmatter and wiki-links (`[[note]]`), and generates verified question-answer training pairs.

### 3. Edge-Optimized VRAM Architecture (20GB Cluster Envelope)
- **4-bit NormalFloat4 (NF4) QLoRA**: Loads base weights (e.g., `Ornith-1.5-9B`) in 4-bit precision with Double Quantization (`bitsandbytes`).
- **Memory Footprint**: Peak allocation of **8.5 GB VRAM** during gradient forward/backward passes, leaving **3.5 GB headroom** on a standard 12GB primary GPU.
- **DPO & GRPO Alignment**: Direct Preference Optimization pairs positive verified answers against rejected sub-threshold attempts.

### 4. Safety Shield & 10 Golden Invariants
Before weights can be exported or promoted to live service, candidates must pass 10 automated empirical probes:
1. Python AST Parse Invariant (0 SyntaxErrors)
2. Memory Leak & Resource Finalization Invariant
3. Concurrency Thread-Safety & ABA Hazard Invariant
4. Bounded Context Limit Invariant (< 1000 chars for BGE embedder)
5. Zero Hallucination on Non-Existent Hardware Endpoints
6. Strict JSON/YAML Schema Adherence
7. Mathematical Theorem Consistency
8. Defensive Exception Catching
9. Non-Circular Self-Correction Invariant
10. Minimum Composite Intelligence Index (CII $\ge 8.5 / 10$)

### 5. Automated GGUF Export & Zero-Downtime Promotion
- **Merge**: Fuses trained LoRA adapter weights directly into the base 16-bit model weights via PyTorch.
- **Quantize**: Converts fused weights into high-efficiency GGUF quantizations (`Q4_K_M`, `Q5_K_M`, `Q8_0`) using `llama.cpp` quantization tools.
- **Hot Promotion**: Moves the new `.gguf` weight file to the production model directory (`/opt/models/`), updates the active symlink, and issues a graceful restart to the coordinator service via cluster bridge with zero user session interruption.

---

## 🛠️ MCP Tools Reference (Selected)

| Tool Name | Description |
| :--- | :--- |
| `hive_mind_query` | Query the cluster as a unified intellect with dual-read consensus and automatic labor division. |
| `run_council_session` | Launch an inter-agent multi-turn deliberation (Architect -> Implementer -> Critic -> Synthesis). |
| `elevate_cluster_to_moe` | Unload dual models and boot a 35B MoE across both GPUs for heavy reasoning. |
| `restore_cluster_to_dual_9b` | Restore back to the high-speed dual-model stack. |
| `list_agent_personas` | Search all stored agent personalities, traits, and sampling hyperparameters. |
| `spawn_from_persona` | Commission a background agent initialized directly from a stored persona profile. |
| `install_github_agent` | Clone an external GitHub agent into the persistent agent directory. |
| `list_local_skills` | Search all 60+ installed local skills in sub-milliseconds. |
| `read_local_skill` | Retrieve complete markdown instructions for any skill in < 1ms. |
| `search_memory` | Perform semantic vector search across Qdrant long-term memory. |

---

## 📄 License
This project is licensed under the [MIT License](LICENSE).


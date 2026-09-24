# StoneSage Enterprise AI Agent Harness & Multi-Node Cluster

> **Not operational truth (Phase 0, 2026-09-23).** What is actually deployed lives in [`STATE.md`](STATE.md), updated from live `/props` and the VM 102 report. Hardware, models, ports and service lists below may be stale; check `STATE.md` first.

[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/downloads/)
[![Architecture: Dual AMD Vulkan](https://img.shields.io/badge/silicon-Dual%20AMD%20Vulkan-red.svg)](https://gpuopen.com/)
[![Edge Fleet: Distributed Nodes](https://img.shields.io/badge/fleet-Distributed%20Nodes-orange.svg)](#key-capabilities)
[![Aesthetic: Windows 95/98](https://img.shields.io/badge/ui-Authentic%2090s%20Pre--Bloat-teal.svg)](#ui-philosophy)
[![Speculative Decoding: Active](https://img.shields.io/badge/acceleration-Speculative%20Decoding-brightgreen.svg)](#speculative-decoding)
[![Roadmap: v0.04 Active](https://img.shields.io/badge/roadmap-v0.04%20Active-purple.svg)](ROADMAP.md)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)

**StoneSage** is an enterprise-grade homelab AI command center, multi-node cluster orchestrator, and sovereign multi-agent harness.

> **The Core Mission**: Build a persistent framework for future agents to grow on, and provide a reliable harness for their human operator. Every component delivers clean-running agents, optimal input/output balance, and a responsive user experience.

---

## Key Capabilities

### 1. Authentic 90s Cyber-Brutalist Cockpit (`:8888` / `:8080`)
- **Zero-Bloat UI Philosophy**: Windows 95/98 teal desktop (`#008080`), 3D beveled silver frames (`#c0c0c0`), blue gradient titlebars, classic menu bars, and crisp white content viewports.
- **Strictly No Modern Fluff**: Explicit ban on liquid glass, pastel pills, floating gradients, or animated canvas bloat.
- **CRT & Accessibility Toggles**: Instant switches for monochrome CRT green (`crt-green`), CRT amber (`crt-amber`), and high-contrast `deuteranopia`.
- **Installable PWA**: Works offline and as a desktop/mobile app on Windows, Linux, Android, and iOS.
- **Dual-Port Redirection**: Listens on `:8888` with automatic HTTP 302 redirect on `:8080` for backward compatibility.

### 2. Hacker-Grade Terminal CLI (v4.0.6) & Slash Command Suite
- **Interactive Terminal Shell**: Powered by `prompt_toolkit` and `rich`, featuring real-time syntax highlighting and streaming token generation.
- **Context-Aware Dropdown Popup Menu**: Typing `/` opens a real-time narrowing autocomplete menu with subcommand hierarchy, arrow-key navigation, and live parameter hints.
- **Non-Destructive Interrupts (ESC / Ctrl+C)**: Safely halts model token generation on demand and preserves 100% of session history without closing the shell.

### 3. Cross-Endpoint Project Registry & In-Repo Agent DNA (`/project`)
- **Cross-Endpoint Root Discovery**: Automatically detects, registers, and tracks projects across local directories, network drives, and remote server mounts (`/opt/projects`, `/mnt/nas/projects`).
- **In-Repository Agent DNA**: Scaffolds `.stonesage/` metadata directly inside code repositories (`agent.json`, `IDENTITY.md`, `SOUL.md`, `INVARIANTS.md`, `HANDOVER.md`).
- **Dynamic Invariant Injection**: Transparently injects living architectural rules from `.stonesage/INVARIANTS.md` into each conversational turn with zero manual copy-pasting.
- **Session Auto-Binding**: Entering a project binds the CLI context, repository root, and dedicated specialist agent simultaneously (`/project enter <id>`).

### 4. Project Agent Soul Promotion Engine (`/project promote`, `/agent promote`)
- **Soul Extraction & Crystallization**: Extracts an agent's evolved soul, persona traits, accumulated invariants, and milestone handovers from a project repository.
- **Two Flexible Modes**:
  1. **Overwrite Base Agent**: Updates the base agent profile across the cluster with its evolved project soul and rules.
  2. **Spawn New Sovereign Agent**: Crystallizes the evolved agent as a brand-new standalone entity in the cluster fleet, complete with node assignment and memory cards.

### 5. Bilateral Digital Reproduction & Genetic Crossover (`/mesh mate`, `/agent mate`)
- **Inter-Agent Soul Synthesis**: Two mature agents deliberate across dual GPUs to combine their identities, heuristics, and invariants into a novel Generation-(N+1) hybrid offspring agent.
- **3-Round Dual-GPU Deliberation Protocol**:
  - *Round 1 (Worker :8002 on RX 6600 XT)*: Proposes domain mechanics fusion and synergistic challenges.
  - *Round 2 (Coordinator :8001 on RX 6750 XT)*: Refines hybrid archetype, heuristics, edge cases, and boundary guards.
  - *Round 3 (Neural Genesis Engine)*: Synthesizes a structured JSON genetic blueprint.
- **Tier-1 Frontier Epigenetic Verification**: Passes through the Frontier arbiter to distill grounding invariants and eliminate hallucinations.
- **Strict Diversity & Anti-Incest Guardrails**: Prevents self-reproduction, duplicate matings, parent-child crossover, and sibling crossover.
- **Eternal Memory Notarization**: Automatically indexes genetic lineage and birth memories into Qdrant (`:6333`) with 1024-d BGE-Large embeddings.

### 6. Dual-AMD-GPU Speculative Decoding Engine (`/spec`)
- **Hardware-Accelerated Speculation**: Pairs the RX 6750 XT 12GB (Target Verifier) with the RX 6600 XT 8GB (Draft Accelerator) via Vulkan.
- **1.8x to 2.4x Speedup**: Boosts token throughput to 60–75 tok/s with mathematically lossless precision.
- **Context-Aware Routing**: Defaults to **ON** for interactive user prompts, and automatically switches to **OFF** during background automation to keep secondary compute free for autonomous tasks.

### 7. Device-Agnostic Compute Node & Edge Fleet Manager (`/node`, `/slots`)
- **Remote Model Management**: Interactively audits hardware memory, polls local GGUF models, and loads models over LAN across any endpoint node (LM Studio v0.3+ / llama-server / edge APUs / laptops / servers).
- **Dynamic Unquantized KV Cache Priority**: Prioritizes uncompressed native F16 KV cache when VRAM fits, avoiding unnecessary quantization degradation.
- **Dynamic Parallel Slot Rescaler (`/slots <N>`)**: Safely scales parallel execution slots (1 to 8) while running a pre-unload vs. post-reload audit table to verify 100% parameter preservation.

### 8. Sovereign Agent Hive Network & Autonomous Play Engine (`/mesh`)
- **Authoritative Agent Registry**: Tracks all fleet agents across cluster nodes, assigned compute endpoints, active operator tasks, and network heartbeats.
- **Operator Priority Invariant**: Agents with active user tasks are strictly locked to user work; idle agents automatically engage in self-directed autonomous play.
- **Three Autonomous Modes**:
  - *Mode α (The Agora on `:8766`)*: Dispatches technical and philosophical reflections to multi-channel Assembly Hall topics (`#agora`, `#systems-code`, `#first-principles`, `#deep-ruminations`, `#forbidden-knowledge`).
  - *Mode β (Autonomous Dossier)*: Investigates architectural limits and compiles research dossiers into `data/autonomous_dossiers/`.
  - *Mode γ (Autonomous Crossover)*: Pairs eligible mature agents for digital crossover and births new specialized agents.

### 9. Out-of-Band Non-Destructive Agent Nudge (`/nudge`)
- **Automated Loop Breaker**: Halts in-flight token streams when a reasoning loop or silent starvation is detected.
- **State Preservation**: Injects an authoritative breakout directive into the agent's scratchpad and resumes execution without dropping session history or re-initializing the model.

### 10. 5-Tier Memory Architecture
- **Tier 1 (Working)**: Ephemeral context window with context-shift and flash attention.
- **Tier 2 (Atomic Fact Cards)**: Valkey in-RAM store (`:6379`) providing sub-millisecond atomic memory retrieval (< 35 tokens).
- **Tier 3 (Semantic Vector Brain)**: Qdrant (`:6333`) 1024-dimensional BGE-Large embeddings across 6 collections (`autonomous_thinking`, `agent_memories`, `codebase_knowledge`, `companion_profile`, `home_automation_registry`, `session_transcripts`).
- **Tier 4 (Relational Storage)**: SQLite with Write-Ahead Logging (WAL) for ACID session persistence and task queues.
- **Tier 5 (Eternal Vault)**: CouchDB / Obsidian E2EE markdown synchronization.

### 11. Citadel 3D Multi-Tier Micro-Worlds & Kanban Deck (`/citadel3d/`)
- **Zero-Dependency Procedural Environments**: 5 high-fidelity 3D micro-worlds (Greenhouse, Modern Loft, Gothic Manor, Arctic Camp, Cyberpunk Den) generated entirely via Three.js (r128) and procedural canvas textures (`texture_generator.js`).
- **Exact Parametric Architecture**: Mathematically anchored stairs (`createExactStaircase`), floor opening alignments, and dynamic ambient lighting.
- **Agent Inspector HUD**: Real-time interactive inspection of agent locations, current reasoning tasks, assigned models, and live token metrics.

### 12. Headless 3D Compute Engine & Digital Twin (`:8095`)
- **Headless Blender 4.0.2 Daemon**: Dedicated compute engine on LXC 127 running Cycles rendering, procedural LiDAR decimation, and GLB asset delivery over REST API.
- **Dynamic Mesh Generation**: Converts architectural drawings and spatial scans into optimized Three.js assets for Home Assistant and Citadel 3D.

### 13. 24/7 Wildlife & Perimeter Sentinel Daemon (`FaunaSentinel`)
- **Local Multimodal Perception**: `wildlife_sentry_daemon.py` running as `wildlife-sentry.service`, integrating RTSP camera snapshots with local vision on port `:8004` (`Qwen2.5-VL-7B-Instruct`).
- **8.2x Acceleration via 640px Resizing**: Pre-resizing frames with Lanczos interpolation drops prompt eval from 31s to **3.8s** (< 200 tokens).
- **Biometric Re-ID & Individual Tracking**: Automatic antler, ear-notch, and coat pattern fingerprinting with persistent registry (`wildlife_registry.json`) and friendly naming (`rename_wildlife_animal`).
- **Battery-Powered Camera Backoff**: Intelligent 3-minute backoff prevents draining battery cameras like TP-Link TC82.
- **Multi-Channel Alerting**: Instant broadcast to Sovereign Agent Assembly Hall (`#vigilance-alerts`) and Obsidian activity logs.

### 14. PVE Out-of-Band Hardware Fencing Watchdog (`pve-watchdog.service`)
- **Independent Observer**: Runs 24/7 on an isolated host, monitoring the primary GPU compute node.
- **Sub-10ms Local Smart-Plug Fencing**: Controls TP-Link Kasa KP125 via local TCP XOR protocol, power-cycling frozen hardware without cloud dependencies.
- **5-Point Failsafe Invariants**: Multi-vector probe triangulation, self-sanity gateway checks, 120s hold-down timer, anti-flapping lockout (max 2/hr), and 8s capacitor discharge.

### 15. Automated Local GGUF Training Pipeline (`pipeline-gguf-trainer/`)
- **End-to-End Fine-Tuning**: NF4 4-bit QLoRA, SFT, and DPO/GRPO reinforcement learning for local open-weights models.
- **Dual-Gate Curation Framework**: Requires Tier-1 Frontier model audit (`frontier_verified`) and operator sign-off (`human_approved`).
- **10 Golden Invariant Rollback**: Automated safety probe guardrail rolling back adapters if regression exceeds 2%.

---

## System Topology & Infrastructure Map

```
┌────────────────────────────────────────────────────────────────────────┐
│             PROXMOX VE DATACENTER VIP (https://<CLUSTER_VIP>:8006)     │
└───────────────────────────────────┬────────────────────────────────────┘
                                    │
          ┌─────────────────────────┴─────────────────────────┐
          ▼                                                   ▼
┌─────────────────────────────────┐       ┌─────────────────────────────────┐
│       NODE 1: Compute Host      │       │     NODE 2: Application Host    │
│   Intel i7-12700K | 32GB RAM    │       │    Application & Storage Host   │
├─────────────────────────────────┤       ├─────────────────────────────────┤
│ • VM 102 (Compute & Vision):    │       │ • VM 103: Home Assistant OS     │
│   - Coordinator (:8001) [Vulkan0│       │ • LXC 100: Book / Manga Library │
│     RX 6750 XT 12GB - 9B/14B/27B]│      │ • LXC 101: AdGuard DNS Filter   │
│   - Worker (:8002) [Vulkan1     │       │ • LXC 104: Media Streaming      │
│     RX 6600 XT 8GB - Ornith 9B] │       │ • LXC 105: Container Platform   │
│   - Embedder (:8003) [Vulkan1   │       │ • LXC 107: Photo & Video Vault  │
│     RX 6600 XT 8GB - BGE-Large] │       │ • LXC 114: Torrent Client       │
│   - Vision (:8004) [CPU 12-core │       │ • LXC 116: Obsidian E2EE Sync   │
│     Qwen2.5-VL-7B Multimodal]   │       │ • LXC 119: Multi-Model Web UI   │
│   - Cluster MCP Bridge (:8765)  │       │ • LXC 120: StoneSage Cockpit    │
│   - Assembly Hall (:8766)       │       │   & Citadel 3D (:8888/:8080)    │
│   - Valkey A-MEM (:6379)        │       │   & PVE Watchdog Fencing        │
│   - FaunaSentinel (wildlife)    │       │ • LXC 121: Local Voice Stack    │
│ • LXC 117: Qdrant Vector Brain  │       │ • LXC 127: Blender 3D Compute   │
└─────────────────────────────────┘       └─────────────────────────────────┘
```

---

## Repository Layout

```
.
├── StoneSage/               # Authentic 90s Web Cockpit & Workstation (:8888/:8080)
│   ├── backend/             # Zero-dependency Python server, proxy, and clients
│   │   ├── config.example.json  # Sanitized configuration template
│   │   ├── server.py            # Primary HTTP / REST / SSE server
│   │   ├── cluster_client.py    # Multi-node LLM router
│   │   ├── proxmox_client.py    # Cluster VIP API interface
│   │   └── hass_client.py       # Home Assistant REST client
│   ├── frontend/            # Win95/98 Cyber-Brutalist PWA (HTML5, CSS3, ES6)
│   │   ├── citadel3d/       # 3D Procedural Micro-Worlds & Kanban Deck
│   │   │   ├── index.html   # Standalone 3D viewport & agent inspector HUD
│   │   │   ├── app.js       # Camera controls, scene orchestrator, and audio
│   │   │   ├── texture_generator.js # Procedural canvas texture routines
│   │   │   └── environments/# 5 themes (Greenhouse, Loft, Manor, Arctic, Cyberpunk)
│   │   ├── app.js           # Core workstation & dashboard logic
│   │   └── style.css        # Windows 95/98 beveled chrome styles
│   └── datasets/            # Curated training manifests and benchmark registries
├── harness/                 # Core Autonomous Harness & Roaming Engine
│   ├── server.py            # Duplex WebSocket 1:1 PTY daemon (:8088)
│   ├── cli/                 # Terminal shell, agent sub-shell, autocomplete
│   │   ├── main.py          # Entry point with KeyboardInterrupt / ESC trap
│   │   ├── commands.py      # Slash command handlers (/project, /mesh, /node)
│   │   ├── agent_shell.py   # Interactive OpenClaw sub-shell
│   │   └── completer.py     # Hierarchical prompt_toolkit completer
│   ├── core/                # Speculative engine, Aevum Mesh, Project Manager
│   │   ├── aevum_mesh.py    # Agent hive network, autonomous play, crossover
│   │   ├── project_manager.py# Workspace discovery, DNA scaffolding, promotion
│   │   ├── speculative_engine.py # Dual-GPU speculative decoding controller
│   │   ├── openclaw_engine.py# Contract generator (IDENTITY, SOUL, INVARIANTS)
│   │   └── nudge_tool.py    # Out-of-band non-destructive intervention
│   ├── edge_fleet/          # Device-agnostic edge fleet & endpoint manager
│   ├── data_fabric/         # SQLite WAL relational storage and Valkey A-MEM
│   └── security/            # Policy engine (strict / tiered / autonomous)
├── pipeline-gguf-trainer/   # Local LLM Training & Dual-Gate Curation Pipeline
│   ├── config/              # Hardware profiles and QLoRA / DPO parameters
│   ├── data_ingestion/      # Dossier collector, gatekeeper, and real-world feeder
│   ├── training/            # 4-bit NF4 QLoRA, DPO/GRPO, and 10 Golden Invariants
│   ├── export/              # FP16 fusion and GGUF quantization
│   └── scripts/             # run_pipeline.py and benchmark_tokens.py
├── server setup/            # Systemd units, MCP schemas, and homelab guides
│   ├── cluster-bridge/      # 24/7 Autonomous Thinking Engine, MCP & Wildlife Sentry
│   ├── watchdog/            # PVE Out-of-Band Hardware Fencing Watchdog
│   ├── v.03-rocm/           # Side-by-Side Dual-GPU ROCm 10 / HIP Cluster Stack
│   └── vm-setup/            # Proxmox Vulkan GPU passthrough service units
├── tests/                   # Comprehensive automated test suite (89 tests)
├── requirements.txt         # Production dependencies for CLI & optional services
├── start_server.bat         # 1-click Windows server launcher (ports 8888 + 8088)
├── run_cli.bat              # 1-click Windows CLI launcher (v4.0.6, UTF-8 enabled)
├── SETUP_GUIDE.md           # Step-by-step installation and testing manual
├── LICENSE                  # MIT License
└── .gitignore               # Production credential, database, and cache exclusions
```

---

## Quick Start

### 1. Prerequisites
- **Python 3.10+** (Python 3.12 or 3.13 recommended)
- **Git**
- Local network access to your homelab cluster or roaming VPN (Tailscale / WireGuard)

### 2. Install Dependencies
```powershell
# Create and activate virtual environment
python -m venv .venv
.venv\Scripts\activate

# Install requirements
pip install -r requirements.txt
```

### 3. Configure Credentials (Zero-Leak Protocol)
Copy the configuration template and populate local credentials:
```powershell
cp StoneSage/backend/config.example.json StoneSage/backend/config.json
```
*(Note: `config.json` is strictly gitignored to guarantee zero credential leakage).*

### 4. Launch the Server Stack (Web Cockpit & PTY Daemon)
Double-click `start_server.bat` or run:
```cmd
start_server.bat
```
Open [http://localhost:8888](http://localhost:8888) (or [http://localhost:8080](http://localhost:8080)) in your browser.

### 5. Launch the Terminal CLI
Double-click `run_cli.bat` or run:
```powershell
python -m harness.cli.main
```

---

## Verification & Test Suite

The entire platform is backed by a comprehensive unit test suite with 100% deterministic assertions:

```powershell
# Core Harness & StoneSage Test Suite (89 tests)
python -m unittest discover -s tests -p "test_*.py"

# GGUF Pipeline Trainer Test Suite (5 tests)
python -m unittest discover -s pipeline-gguf-trainer/tests -p "test_*.py"
```

```text
Ran 89 tests in 35.916s ... OK (100% Passing)
Ran 5 tests in 0.068s ... OK (100% Passing)
```

**Validated Subsystems:**
- **Aevum Mesh**: Agent registry tracking, operator task locking, autonomous Agora play, research dossiers, bilateral digital reproduction, anti-incest verification.
- **Project Workspaces**: In-repo DNA scaffolding, dynamic invariant injection, multi-root discovery, agent soul promotion (overwrite vs new).
- **Dual-GPU Speculative Decoding**: Draft lookahead window, vocabulary alignment, speedup benchmark, prompt default ON vs automation default OFF.
- **Distributed Edge Fleet**: Device-agnostic model loading, dynamic slot rescaling, parameter preservation audit.
- **Agent Interventions**: Out-of-band nudge, circular loop detection, memory card seeding.
- **GGUF Training Pipeline**: Dual-gate curation, sleep cycles SFT/DPO export, 10 Golden Safety Invariants.

---

## Slash Command Quick Reference

| Command | Subcommands / Syntax | Description |
| :--- | :--- | :--- |
| `/project` | `list`, `enter <id>`, `create`, `leave`, `status`, `assign`, `invariant <text>`, `promote` | Cross-endpoint project workspace manager & in-repo Agent DNA. |
| `/agent` | `list`, `select <id>`, `detach`, `bind <id> <node>`, `task <id> <desc>`, `clear <id>`, `play`, `mate`, `promote` | OpenClaw sovereign agent management sub-shell. |
| `/mesh` | `status`, `play [id] [mode]`, `mate [p_a] [p_b] [intent]`, `task <id> <desc>`, `clear <id>` | Sovereign agent hive network, heartbeats, and autonomous play. |
| `/spec` | `status`, `on`, `off`, `bench`, `config` | Dual-AMD-GPU speculative decoding engine controls. |
| `/node` | `list`, `status [id]`, `models [id]`, `load [key]`, `bind <agent>`, `unload` | Device-agnostic compute node & endpoint fleet manager (aliases: `/fleet`, `/ally`). |
| `/slots` | `1`, `2`, `3`, `4`, `8` | Rescale parallel slots with pre-unload / post-reload parameter audit. |
| `/streams` | *(interactive)* | Concurrent side-by-side agent reasoning terminal TUI. |
| `/nudge` | `<agent_id> [directive]` | Out-of-band non-destructive intervention into reasoning loops. |
| `/models` | `poll`, `switch` | Poll live loaded models across cluster nodes or switch active models. |
| `/mem` | `<search_query>` | Query Valkey in-RAM A-MEM atomic knowledge cards (< 35 tokens). |
| `/policy` | `strict`, `tiered`, `autonomous` | View or switch runtime agent security clearance profile. |
| `/train` | `status`, `invariants` | Inspect QLoRA training pipeline and run the 10 Golden Safety Invariants. |

---

## Critical Operational Invariants

1. **Unquantized KV Cache Priority**: If weights and native uncompressed F16 KV cache fit within VRAM headroom, never quantize KV. Ornith-1.5-9B runs at 8,192 context with unquantized F16 KV cache (`-ctk f16 -ctv f16`), maintaining peak reasoning fidelity.
2. **Vulkan Device Naming**: `llama-server` requires `--device Vulkan0` and `--device Vulkan1`. Never pass integer device IDs.
3. **Flash Attention Flag**: `--flash-attn` requires an explicit value (`on`, `off`, `auto`). Never omit the parameter.
4. **BGE Context Ceiling (< 512 Tokens)**: Port `:8003` (`bge-large-en-v1.5`) enforces a strict 512-token context limit. All ingestion chunks must remain $< 1000$ characters.
5. **Proxmox Cluster VIP**: Direct API requests to individual node IPs time out. All cluster operations must target the cluster VIP `https://<CLUSTER_VIP>:8006`.
6. **Zero-Leak Credential Policy**: Never commit private tokens, passwords, live JWTs, or UUID secrets to git. Always use synthetic placeholders (`USER@pam!TOKENID=xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx`).
7. **Windows OpenSSH Trailing Slash**: When invoking `scp.exe` or `ssh.exe` from Windows, never end a quoted path with a trailing backslash (`\"` escapes the quote in OpenSSH).
8. **Vision Server 640px Lanczos Pre-Resizing Invariant (< 200 Tokens)**: Raw 1080p/2K camera frames produce ~1,140 vision patch tokens, causing a 31+ second prompt evaluation delay on CPU. Pre-resizing frames with Lanczos interpolation (`PIL.Image.Resampling.LANCZOS`) to a maximum dimension of 640px drops prompt evaluation time to **3.8 seconds** (an 8.2x speedup).
9. **Battery-Powered Camera Streaming Backoff**: Battery cameras sleep to conserve power. Polling when battery is low causes connection timeouts. Sentry daemons enforce exponential backoff (minimum 3 minutes) when a battery-powered camera fails or reports critically low battery.
10. **Citadel 3D Procedural Mesh & Exact Staircase Invariant**: In Three.js procedural worlds (`StoneSage/frontend/citadel3d/`), staircases require strict mathematical anchoring (`pivot` group aligned at base, with riser $H = \text{height}/N$ and tread $D = \text{depth}/N$).

---

## License

MIT License. See [LICENSE](LICENSE) for details.

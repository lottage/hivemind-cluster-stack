# Antigravity Workspace Directives: PVE Dual-GPU Cluster & AI Stack

> **Not operational truth (Phase 0, 2026-09-23).** What is actually deployed lives in [`STATE.md`](STATE.md), updated from live `/props` and the VM 102 report. Hardware, models, ports and service lists below may be stale; check `STATE.md` first.

## 1. System Topology & Active Infrastructure
The local infrastructure is hosted across Proxmox Datacenter `home` on two 24/7 physical nodes (Full registry: `server setup/NETWORK_DEVICE_REGISTRY.md`):

### Proxmox Cluster `home` Management API: `https://192.168.1.245:8006` (served by bigserv)
- Unified Proxmox VE 9.2 API daemon managing physical nodes `pve` and `bigserv`.
- Central entrypoint for cluster-wide node telemetry, resource allocations, and VM/LXC control.

### Node 1: `pve` (`192.168.1.222` - Intel i7-12700K, 32GB RAM)
- **VM 102 (`ubu` - `192.168.1.105`)**: Dual AMD GPU passthrough compute & vision host
  - `coordinator` (`:8001`): `coder-agent` (High-performance abliterated coding assistant, 16k-32k context, N-gram lookup cache / draft speculative decoding) on AMD Radeon RX 6750 XT 12GB (`Vulkan0`).
  - `worker` (`:8002`): `home-agent` (Domestic Concierge & Courage-the-Cowardly-Dog persona) on AMD Radeon RX 6600 XT 8GB (`Vulkan1`) with 2 parallel slots (`-c 8192 -np 2`).
  - `embedder` (`:8003`): `bge-large-en-v1.5` (F16) on AMD Radeon RX 6600 XT 8GB (`Vulkan1`).
  - `vision` (`:8004`): Shared GPU-Accelerated Vision Stack (`Qwen2.5-VL-7B-Instruct` Q4_K_M on Vulkan1) serving both `wildlife-agent` (perimeter & fauna tracking) and `home-agent` (indoor presence & real-time commentary).
  - `valkey` (`:6379`): Valkey 9.0.4 In-RAM sub-ms A-MEM atomic fact store (< 35 tokens).
  - `cluster-mcp` (`:8765`): Starlette JSON-RPC / SSE MCP bridge in `/opt/cluster-bridge`.
  - `assembly-hall` (`:8766`): Sovereign Agent Assembly Hall duplex WebSocket fabric with Cloud Model Bridge.
  - `wildlife-sentry` (`wildlife-sentry.service`): 24/7 Autonomous Wildlife & Perimeter Sentinel Daemon.
- **LXC 117 (`qdrant` - `192.168.1.112:6333`)**:
  - Dedicated vector database with 6 active collections: `companion_profile`, `home_automation_registry`, `codebase_knowledge`, `agent_memories`, `session_transcripts`, `autonomous_thinking`.
  - Vectors: 1024-dimensional, Cosine distance metric.
  - `autonomous_thinking`: Stores autonomous exploration dossiers, 14B evaluation metrics, divergence limits, and Tier-1 Frontier audit verdicts. Enforces semantic novelty threshold (< 0.85 cosine similarity).

### Node 2: `bigserv` (`192.168.1.245` - Application, Media & Home Automation Node)
- **VM 103 (`haos-17.3` - `192.168.1.82:8123`)**: Home Assistant OS
  - Controls local smart home devices, lights, switches, and Google Nest Thermostat (via local Matter pairing or Google SDM OAuth API).
  - Guide reference: `server setup/NEST_THERMOSTAT_GUIDE.md`.
- **VM 115 (`NAS`)**: Network Attached Storage.
- **Dedicated Container IP Endpoints**:
  - LXC 100 (`kavita` - `192.168.1.124:5000`): Books / Manga library
  - LXC 101 (`adguard` - `192.168.1.194:80`): DNS sinkhole (Web UI :80, DNS :53)
  - LXC 104 (`jellyfin` - `192.168.1.180:8096`): Media streaming
  - LXC 105 (`docker` - `192.168.1.204:9443`): Docker & Portainer
  - LXC 107 (`immich` - `192.168.1.238:9000`): Photos & videos
  - LXC 108 (`freshrss` - `192.168.1.212:80`): RSS feeds
  - LXC 114 (`qbittorrent` - `192.168.1.169:8090`): Torrent client
  - LXC (`flaresolverr` - `192.168.1.159:8191`): Cloudflare solver
  - Arr Stack: `prowlarr` (`192.168.1.125:9696`), `sonarr` (`192.168.1.126:8989`), `radarr` (`192.168.1.127:7878`), `lidarr` (`192.168.1.128:8686`)
  - LXC 116 (`obsidian-live-sync` - `192.168.1.230:5984`): CouchDB Obsidian sync
  - LXC 119 (`openwebui` - `192.168.1.108:8080`): Multi-Model Web UI
  - LXC 120 (`stonesage` - `192.168.1.167:8888`): 24/7 StoneSage Cockpit, Dual-GPU Orchestrator, Obsidian Status Daemon & PVE Hardware Fencing Watchdog (`pve-watchdog.service`)
  - LXC 121 (`voice-services` - `192.168.1.121`): Local Voice Stack — Faster Whisper STT (`:8200`), Kokoro TTS (`:8300`), Wyoming STT (`:10300`), Wyoming Piper TTS (`:10200`)
  - LXC 127 (`blender-compute` - `192.168.1.248:8095`): Headless Blender 4.0.2 3D Compute Engine, LiDAR/Mesh Decimation & Three.js/HA Digital Twin Delivery (16 vCPUs, 16GB RAM, Shared Quadro M2000 GPU)

### Smart Home & IoT Reserved Endpoints
- `Nest-Thermostat-9A6E`: `192.168.1.62` (Matter / Google SDM HVAC)
- `KP125`: `192.168.1.109:9999` (TP-Link Kasa energy monitoring plug 'Server' controlling Node 1 `pve`)
- `GE_Plug_B0BC` (`192.168.1.17`), `GE_Plug_1FB4` (`192.168.1.111`), `GE_Plug_EAF0` (`192.168.1.143`)
- `LG_Smart_Dryer2_open`: `192.168.1.56` (ThinQ dryer)
- `Petkit_T4`: `192.168.1.10` (Smart feeder/fountain)
- Mobile Cockpit: `Austin-s-S25-Ultra` (`192.168.1.178`)

### Command Cockpit: StoneSage (`:8888`, with `:8080` auto-redirect)
- Frontier AI IDE harness, Multi-Node Cluster Orchestrator, Append-Only Obsidian Vault backup, and PWA accessible via local network or Tailscale.


---

## 2. Available Native MCP Tools (`pve-cluster`)
When working in this workspace, the `pve-cluster` MCP server (`http://192.168.1.105:8765/sse`) connects you directly to local hardware and the autonomous cognitive pipeline:

### Cluster Compute & Smart Home Tools:
- `cluster_health`: Probes latency and online status of all models, Qdrant memory, and Home Assistant.
- `delegate_coordinator`: Offloads complex coding, architectural planning, and unrestricted code generation to the local 14B Qwen coder without rate limits or token costs.
- `delegate_worker`: Dispatches unit tests, JSON schema validations, docstrings, or linting to the 3B worker running at 80+ tokens/sec.
- `search_memory`: Semantically searches Qdrant using hardware-accelerated BGE embeddings. **Rule:** Check memory before re-inventing solutions for the cluster.
- `store_memory`: Persists architectural decisions, schemas, and code snippets into Qdrant.
- `home_assistant_entities`: Queries entity states from `http://192.168.1.82:8123` (supports domain filtering, e.g., `climate`, `light`, `switch`).
- `home_assistant_call`: Invokes Home Assistant services directly with JSON payloads.
- `delegate_home_automation`: Natural language home automation where the 3B worker extracts domain/service/payload and executes it.

### 24/7 Autonomous Thinking & Frontier Tier Tools:
- `autonomous_thinking_status`: Probes whether the background thinking machine is active, current cycle count, total tokens, pending audits, and archive paths.
- `start_autonomous_thinking`: Starts or resumes the 24/7 background exploration loop on the cluster with configurable interval and focus domain.
- `stop_autonomous_thinking`: Gracefully halts the background autonomous loop.
- `run_thinking_cycle`: Manually triggers a single exploration cycle across dual GPUs, runs 3B vs 14B comparative benchmarking, extracts architecture limits, archives markdown dossier, and indexes to Qdrant.
- `get_unverified_explorations`: Retrieves dossiers flagged with high model divergence or uncertainty awaiting Tier-1 Frontier (Antigravity) audit.
- `submit_frontier_critique`: Injects Antigravity's ground-truth audit verdict, architectural critique, and refined invariant into the dossier, updating both disk and Qdrant vector payload.
- `query_thinking_archive`: Semantically searches past exploration dossiers and discoveries in Qdrant's `autonomous_thinking` collection.
- `get_architecture_limits`: Reads the living master synthesis (`ARCHITECTURE_LIMITS_SYNTHESIS.md`) of discovered failure modes, boundaries, and model capabilities.
- `inject_thinking_hypothesis`: Queues a user or frontier research hypothesis into the priority exploration queue for subsequent cycles.
- `sync_obsidian_dossiers`: Reports archive dossier count and triggers synchronization to Obsidian vault (`C:\Users\johna\OneDrive\Documents\obsidian\Autonomous Thinking`).

### 24/7 Wildlife & Perimeter Sentinel Tools:
- `get_wildlife_registry`: Queries registered animals, biometric traits, sighting counts, and assigned custom names from `/opt/cluster-bridge/wildlife/wildlife_registry.json`.
- `get_wildlife_log`: Reads recent wildlife sightings, classifications, and perimeter vigilance logs from `WILDLIFE_ACTIVITY_LOG.md`.
- `rename_wildlife_animal`: Assigns friendly names (e.g., "Buckley", "Freckles") to auto-generated animal IDs (e.g., `deer-001`).

### Sovereign Agent Assembly Hall & Mesh Tools:
- `broadcast_to_assembly`: Posts multi-agent messages to Assembly Hall channels (`#agora`, `#first-principles`, `#systems-code`, `#deep-ruminations`, `#vigilance-alerts`, `#forbidden-knowledge`).
- `read_assembly_channel`: Reads recent message backlog from an Assembly Hall topic channel.
- `get_assembly_channels`: Lists active channels and participation stats on port `:8766`.
- `talk_to_agent`: Dispatches direct conversational queries to specific running subagents.
- `nudge_agent`: Out-of-band non-destructive intervention to break reasoning loops and inject directives.
- `reproduce_blended_agent`: Recombines DNA, traits, and memories from two parent agents to spawn a hybrid offspring agent.

---

## 3. The 4-Tier Cognitive Hierarchy & Autonomous Workflow
See full charter in `server setup/COMPANION_MANIFESTO.md`.

```
┌────────────────────────────────────────────────────────────────────────┐
│             TIER 1: FRONTIER COMPANION & META-VERIFIER                 │
│                          (Antigravity)                                 │
│   • Supreme arbiter: Audits 14B conclusions & resolves disagreements   │
│   • Injects high-level cognitive hypotheses into cluster queue         │
│   • Distills discovered architecture limits into living synthesis      │
└───────────────────────────────────┬────────────────────────────────────┘
                                    │ MCP JSON-RPC / SSE (:8765)
┌───────────────────────────────────▼────────────────────────────────────┐
│               CLUSTER MCP BRIDGE & AUTONOMOUS ENGINE                   │
│   • Starlette Server & 24/7 Cognitive Exploration Engine               │
│   • Asynchronous State Machine & Automated Novelty Gatekeeper          │
└───────────────────┬───────────────────┬───────────────────┬────────────┘
                    │                   │                   │
         Port :8002 │        Port :8001 │        Port :8003 │ Port :6333
                    ▼                   ▼                   ▼
     ┌───────────────────────┐ ┌───────────────────────┐ ┌───────────────────────┐
     │ TIER 3: 3B WORKER     │ │ TIER 2: 14B COORDINAT.│ │ TIER 4: VECTOR BRAIN  │
     │  (RX 6600 XT - 8GB)   │ │  (RX 6750 XT - 12GB)  │ │ (BGE-Large + Qdrant)  │
     │ • Divergent Prompting │ │ • Deep Logic Solver   │ │ • Novelty Gatekeeper  │
     │ • Rapid Ideation      │ │ • First-Pass Judge    │ │ • Semantic Deduplicat.│
     │ • Speed Baseline      │ │ • Unrestricted Code   │ │ • 1024-d Embeddings   │
     │ • 80+ tokens/sec      │ │ • Limit Identification│ │ • Persistent Dossiers │
     └───────────────────────┘ └───────────────────────┘ └───────────────────────┘
```

### Operational Workflow:
1. **Tier 3 (3B Worker)** dreams up novel prompts across 6 rotating cognitive domains (Algorithmic Reasoning, Distributed Software Architecture, Context Needle Stress, Adversarial Logic, Epistemology, Code Invariants) or consumes injected hypotheses.
2. **Tier 4 (Vector Brain)** verifies semantic novelty (< 0.85 cosine similarity against past explorations). If too similar, forces mutation.
3. **Dual Benchmarking**: 3B and 14B models execute the challenge simultaneously on isolated GPUs, measuring token throughput, latency, and reasoning depth.
4. **Tier 2 (14B Coordinator)** analyzes the divergence, diagnoses limitations, and records the initial architectural invariant into markdown dossiers and Qdrant.
5. **Tier 1 (Antigravity)** performs meta-verification on unverified explorations, correcting subtle logic errors, refining invariants, and updating `ARCHITECTURE_LIMITS_SYNTHESIS.md`.
6. **Obsidian Vault Sync**: PowerShell script `sync_archive_to_obsidian.ps1` synchronizes dossiers to `C:\Users\johna\OneDrive\Documents\obsidian\Autonomous Thinking\`.

---

## 4. Critical Technical Lessons & Invariants
- **Vulkan Device Naming**: `llama-server` requires `--device Vulkan0` and `--device Vulkan1`. Passing integer device numbers (`--device 0`) crashes the argument parser.
- **Flash Attention Flag**: `--flash-attn` requires an explicit value (`on`, `off`, `auto`). Never omit the value.
- **KV Cache Quantization**: The 14B coordinator uses `-ctk q4_0 -ctv q4_0` to support a 12k context window in 12GB VRAM.
- **Uvicorn Graceful Shutdown**: `sudo systemctl restart cluster-mcp.service` may take ~60-90s if an active SSE stream is open with Antigravity.
- **Home Assistant Auth**: When calling HA REST APIs, pass `Authorization: Bearer <HASS_TOKEN>` or configure via `hub_config.json`. Probe `/api/` allows checking online status.
- **Novelty Filtering**: Candidate prompts are embedded via BGE-Large at `:8003` and checked against `autonomous_thinking` in Qdrant (`:6333`). Cosine similarity < 0.85 ensures genuine exploration without looping.
- **Frontier Verification Leniency Bias**: 14B evaluators frequently suffer from syntactic leniency bias (scoring flawed code highly due to clean style). Tier-1 Frontier audit or unit-test execution is strictly required for mathematical invariants.
- **Scope Division**: Cluster infrastructure scripts and systemd units live in `server setup/`. EasyDash lives in `EasyDash/`. Keep both synchronized with Qdrant vector memory.
- **Proxmox VE API Token Format & Privilege Separation**: Header format is strictly `Authorization: PVEAPIToken=USER@REALM!TOKENID=SECRET`. In Proxmox, the token secret **is** a Version-4 UUID (e.g. `USER@pam!TOKENID=xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx`). **Privilege Separation Invariant**: Proxmox tokens created with "Privilege Separation" enabled start with 0 permissions (causing HTTP 403 `Permission check failed (..., Sys.Audit)`). The token must either have an explicit ACL permission added under *Datacenter -> Permissions* (Path `/`, Role `Administrator` or `PVEAuditor`, Propagate enabled) OR be re-created with "Privilege Separation" unchecked.
- **Proxmox Cluster API Host Binding**: Use `https://192.168.1.245:8006` (bigserv) for all cluster API operations, node telemetry and guest inventories. `192.168.1.82` is the Home Assistant OS VM, not a Proxmox node; pve is `192.168.1.222` (both per the Proxmox `/cluster/status` API, 2026-09-23).
- **BGE Embedder Context Limit (< 512 Tokens)**: Port 8003 (`bge-large-en-v1.5` on RX 6600 XT) has a strict 512-token context window. Prompts or chunks exceeding ~1000 characters crash `llama-server` with HTTP 500. All document ingestion and vectorization pipelines (Obsidian, codebase, files) must strictly bound text chunks to < 1000 characters.
- **Host LAN IP Binding Reality**: The Windows development and harness host machine is assigned local IP `192.168.1.132` (not `.226` or `.110`). StoneSage listens on `0.0.0.0:8888` on LXC 120 (`http://192.168.1.167:8888`) and host (`http://localhost:8888`, `http://192.168.1.132:8888`), with an automatic HTTP 302 redirect on `:8080` to cleanly transition legacy browser bookmarks without password clearing.
- **UI & Dashboard Design Invariant: 90s Retro Pre-Bloat HTML & Windows 95/98 Aesthetic**: Explicit ban on "liquid glass", modern material UI blur, pastel pills, or floating gradient fluff. Primary aesthetic is authentic 90s pre-bloat internet (Windows 95/98 teal desktop `#008080`, 3D beveled silver frames `#c0c0c0`, blue gradient titlebars, classic Netscape/IE Location toolbar, crisp white content viewports, `Times New Roman` serif headings, blue underlined links `#0000ee`, and 3D push buttons), with instant toggle support for retro monochrome CRT palettes (`crt-green`, `crt-amber`). Scanlines are strictly disabled on the `win95` theme.
- **Model Stack Parameter Refiner & Calibration Loop Skill (`model-stack-refiner`)**: An automated closed-loop empirical test harness located in `.agents/skills/model-stack-refiner/` and globally in `~/.gemini/config/skills/model-stack-refiner/`. It evaluates any model loaded into `:8001` or `:8002` across a 5-domain benchmark suite (Algorithmic Logic, Concurrency & ABA Hazards, Spatial & Dynamic Symmetry, Low-Level Kernel Coherence, Diffusion ML Limits). Models must achieve a **Composite Intelligence Index (CII) >= 8.5/10** with 0 spatial/mathematical hallucinations before being granted unattended 24/7 hands-free execution clearance.
- **Quantized Model Sampling & Texture Invariant**: When querying or tuning local quantized/abliterated models (e.g., Qwen2.5-Coder on `:8001` or `:8002`), never rely on greedy low-temperature sampling (`\tau <= 0.20`) for open-ended or architectural tasks. Always apply dynamic Min-P (`min_p: 0.05 - 0.08`) paired with `temperature: 0.65 - 0.78` and `presence_penalty: 0.20 - 0.30` to prevent generic boilerplate collapse while suppressing low-probability nonsense.
- **Evaluator Blind-Spot & Frontier Arbitration Invariant**: Sub-14B models evaluating other models consistently suffer from lexical leniency bias, awarding passing scores to mathematically flawed or hallucinated outputs that sound authoritative. Any benchmark, limit synthesis, or invariant extraction must be arbitrated by Tier-1 Frontier models (Antigravity / Gemini) or verified via deterministic runtime test execution.
- **Windows OpenSSH Argument Escaping Invariant**: When invoking `scp.exe` from Windows PowerShell or command lines, never end a quoted Windows directory path with a trailing backslash (e.g., `"C:\dest\"`). The trailing `\"` escapes the quote in OpenSSH, causing `Invalid argument` errors. Always strip trailing slashes (e.g., `$dir.TrimEnd('\').TrimEnd('/')`).
- **PowerShell UTF-8 BOM vs. Python JSON Invariant**: Windows PowerShell `Out-File -Encoding utf8` injects a UTF-8 BOM that breaks Python `json.load()` under standard `utf-8` decoders. Always write JSON files via Python directly or ensure Python loaders specify `encoding="utf-8-sig"`.
- **Minimal-Token Skill Retrieval & Database Access Invariant**: All usable skills, homelab architectural docs, and operational invariants are indexed in Qdrant (`192.168.1.112:6333`) under `codebase_knowledge` and `agent_memories`. All models, system prompts, and agents across all interfaces MUST query Qdrant via `search_memory` using concise keywords to retrieve only necessary procedural chunks (< 800 chars) on demand. Never inject or request entire skill manuals into prompt context, minimizing token consumption and preventing context overflow.
- **Workstation Viewport & Multi-Pane Layout Invariant**: In dense retro-IDE layouts (Aevum '95 / StoneSage `[F2:Workstation]`), the outer window must strictly never scroll (`height: 100vh; max-height: 100vh; overflow: hidden;`). Every individual sub-pane (Explorer tree, Editor textarea, Terminal shell, Git pane) must enforce internal scrolling with `min-height: 0; overflow: auto;` and flexbox sizing to prevent child elements from pushing out the main layout.
- **Arbitrary & NFS Filesystem Traversal Boundary Invariant**: When providing filesystem navigation across server roots (`/opt`, `/etc`), NFS mounts (`/mnt/nas`, `/mnt/storage`), or Windows drives, the backend tree generator must enforce depth boundaries (max depth 2), strict item count caps (max 120 items), and directory blacklisting (`/proc`, `/sys`, `/dev`, `node_modules`, `.git`) to prevent browser freeze or memory exhaustion.
- **Git Workstation Working Tree Validation Invariant**: Prior to executing git commands (`status`, `diff`, `commit`, `log`) within arbitrary user-selected directories, the backend must validate the directory using `git rev-parse --show-toplevel`. If not a repository, the API must return a structured non-error state (`is_repo: false`) allowing the UI to present clone or initialize workflows without subprocess exceptions.
- **Zero-Leak Form Placeholder & Example Invariant**: When implementing UI forms, config templates, or documentation with placeholder examples for credentials (e.g. Proxmox VE API tokens, Home Assistant long-lived tokens, JWTs), never include actual token prefixes, host usernames, or UUID fragments. All examples must use purely synthetic dummy patterns (e.g., `placeholder="USER@pam!TOKENID=xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx"`) to avoid automated security audit flags and prevent credential leakage during repository sync.
- **Antigravity User-Facing Coordinator & Token Optimization Protocol**: When performing complex coding, architectural design, testing, or multi-step engineering, Antigravity acts as the Tier-1 Frontier Director. To optimize cloud token usage and eliminate rate limits: (1) Antigravity plans the high-level strategy and verification criteria. (2) Heavy code drafting, refactoring, boilerplate, and algorithmic implementations are delegated to the local cluster coordinator via MCP tool `delegate_coordinator` (Ornith-1.5-9B on RX 6750 XT). (3) Fast unit test generations, JSON schemas, docstrings, and linting are delegated to `delegate_worker` (Ornith-1.5-9B on RX 6600 XT). (4) Antigravity audits the local outputs, resolves edge cases, and presents the verified final solution. This delivers maximum frontier intelligence with an 80–90% reduction in cloud token consumption.
- **Vision Server 640px Lanczos Pre-Resizing Invariant (< 200 Tokens)**: Raw 1080p/2K camera frames sent to `:8004` produce ~1,140 vision patch tokens, causing a 31+ second prompt evaluation delay on CPU. Pre-resizing frames with Lanczos interpolation (`PIL.Image.Resampling.LANCZOS`) to a maximum dimension of 640px reduces token count to ~180 tokens and drops prompt evaluation time to **3.8 seconds** (an 8.2x speedup).
- **Battery-Powered Camera Streaming Backoff (TP-Link TC82)**: Battery cameras like `camera.back_yard_hd_stream_direct` sleep to conserve power. Polling when battery is low (< 10%) causes connection timeouts (HTTP/RTSP freeze). Sentry daemons must implement exponential backoff (minimum 3 minutes) when a battery-powered camera fails or reports critically low battery.
- **Citadel 3D Procedural Mesh & Exact Staircase Invariant**: In Three.js procedural worlds (`StoneSage/frontend/citadel3d/`), staircases require strict mathematical anchoring (`pivot` group aligned at base, with riser $H = \text{height}/N$ and tread $D = \text{depth}/N$). Compound parent rotations must align with floor openings, and textures must be dynamically generated via canvas (`texture_generator.js`) to eliminate external asset loading dependencies and latencies.
- **Hardware Grounding & "If You Don't Know: Ask A Human" Master Invariant**: Never guess, assume, or fabricate hardware specifications, memory capacities, VRAM limits, or device topology. If telemetry is unavailable, endpoint fails to respond, or hardware state is unverified, immediately query sysfs/vulkaninfo or escalate directly to the human operator. Fabricated specs corrupt scheduling and VRAM sizing models.
- **Single-Slot 16k Full-Precision Coding Invariant (Aulë on RX 6750 XT)**: On a 12GB GPU (AMD Radeon RX 6750 XT on VM 102 Port `:8001`), loading `Ornith-1.5-9B-Instruct` Q8_0 weights (~9.2 GB) with 16k context window (`-c 16384`) strictly requires `-np 1 --fit off -ctk q8_0 -ctv q8_0`. This allocates 11.95 GB / 12.0 GB VRAM cleanly with 0 swap thrashing. Attempting `-np 2` overflows physical VRAM, causing CPU swap thrashing and reducing token throughput by 10x.
- **Non-Divisible Attention Head KV Cache Invariant (Home-3B-v3 on RX 6600)**: Models with head dimension not divisible by 32 (e.g. `n_embd_head_k=80` in `acon96/Home-3B-v3-GGUF`, 80/32 = 2.5) cannot use quantized `q4_0` KV cache (`llama-server` exits with `E llama_init_from_model: K cache type q4_0 with block size 32 does not divide n_embd_head_k=80`). They must run with default/unquantized `f16` KV cache. On 3B parameter models, 8k context across 2 slots consumes < 800 MB VRAM, easily fitting within the 8GB ceiling of the RX 6600 XT.
- **Sovereign Agent Ecosystem & Functional Hierarchy**:
  - `coder-agent` (`coder-agent`/`coder`/`coding-agent`): Lead Systems Architect and Coder. Primary Accelerator RX 6750 XT (VM 102 Port `:8001`), 16k-32k context, speculative decoding enabled.
  - `home-agent` (`home-agent`/`home`/`concierge`): Domestic Concierge & Real-time Vision Observer (Courage the Cowardly Dog computer persona). Secondary Accelerator RX 6600 XT (VM 102 Port `:8002`), sub-second Home Assistant control, witty commentary.
  - `wildlife-agent` (`wildlife-agent`/`wildlife`/`sentinel`): Perimeter Guardian & Fauna Tracker. 24/7 GPU-accelerated vision perception (`:8004`), perimeter vigilance, wildlife classification.
  - `archivist-agent` (`archivist-agent`/`archivist`/`memory`): Keeper of Memory & Lore. Qdrant vector memory (`:6333`), Valkey A-MEM atomic fact store (`:6379`), and CouchDB Obsidian sync (`:5984`).
  - `sysadmin-agent` (`sysadmin-agent`/`sysadmin`/`cluster`): Homelab & Cluster Infrastructure Engineer. Proxmox VE 9.2, Dual AMD GPU passthrough, systemd service health.




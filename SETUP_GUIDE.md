# StoneSage & Aevum Unified LLM Harness v0.03 — Master Setup & Deployment Guide

> **Not operational truth (Phase 0, 2026-09-23).** What is actually deployed lives in [`STATE.md`](STATE.md), updated from live `/props` and the VM 102 report. Hardware, models, ports and service lists below may be stale; check `STATE.md` first.

> **Version**: `v0.03` (Distributed Mesh, Speculative Decoding & Edge Handheld Fleet)  
> **Target Audience**: Operator (Austin / John) & Homelab Developers  
> **Repository Root**: `c:\Users\johna\OneDrive\Documents\.ai` (or your cloned repository root)  

---

## 1. System Overview & Architecture

StoneSage v0.03 is a unified homelab AI command center and terminal harness pairing local dual-GPU compute silicon with an authentic 90s pre-bloat workstation, cross-device Aevum Mesh networking, and edge handheld orchestration.

```
┌────────────────────────────────────────────────────────────────────────┐
│                        COMPUTE BACKEND & CLUSTER                       │
│  • Coordinator (:8001): Ornith-1.5-9B Q8_0 Reasoner (RX 6750 XT 12GB) │
│  • Worker (:8002): Ornith-1.5-9B Q4_K_M Draft / Ideator (RX 6600 XT 8GB)│
│  • Embedder (:8003): BGE-Large 1024-d Vector Engine (< 512 tokens)     │
│  • Vision (:8004): Gemma-4-E4B-it Q8_0 Multimodal VLM (12 CPU cores)   │
│  • FaunaSentinel: 24/7 Wildlife & Perimeter Sentry Daemon (VM 102)     │
│  • Qdrant (:6333): 6 Vector Collections (Autonomous Thinking & Memory) │
│  • Valkey (:6379): A-MEM Sub-millisecond In-RAM Working Memory Cards   │
│  • Edge Worker (:1234): Distributed Fleet Edge Node (LM Studio / llama)│
└───────────────────────────────────┬────────────────────────────────────┘
                                    │
                                    ▼
┌───────────────────────────────────┴────────────────────────────────────┐
│                    CENTRAL HARNESS & WEB COCKPIT                       │
│  • StoneSage Server (:8080): Web REST API, Cluster Proxy, Workstation  │
│  • Citadel 3D (:8080/citadel3d/): 5 Procedural Multi-Tier Micro-Worlds │
│  • PVE Watchdog: Out-of-band TP-Link KP125 hardware cycler (LXC 120)  │
│  • Harness PTY Daemon (:8088): Duplex WebSocket 1:1 Terminal & Shell   │
│  • Assembly Hall (:8766): Real-time multi-agent streaming fabric       │
│  • Aevum Mesh (:8767): Cross-device peer sync & soul reproduction      │
└───────────────────────────────────┬────────────────────────────────────┘
                                    │
         ┌──────────────────────────┴──────────────────────────┐
         ▼                                                     ▼
┌───────────────────────────────┐             ┌───────────────────────────────┐
│     TERMINAL HARNESS CLI      │             │     UNIFORM WEB COCKPIT       │
│  • `run_cli.bat` / Python CLI │             │  • Browser / PWA (:8080)      │
│  • Interactive Auto-fill Drop │             │  • [F1:Chat] Multimodal Vision│
│  • In-Repo Workspace DNA      │             │  • [F2:Workstation] nano / git│
│  • Speculative Decoding Toggle│             │  • [F3:Terminal] Duplex PTY   │
│  • Dynamic Slot Rescaling     │             │  • [F4:Fleet] GPU Telemetry   │
│  • Digital Soul Reproduction  │             │  • [F5:Assembly] Live Streams │
│  • Out-of-Band Agent /nudge   │             │  • [/citadel3d/] 3D Worlds    │
└───────────────────────────────┘             └───────────────────────────────┘
```

---

## 2. Prerequisites

1. **Python 3.10+** (Python 3.12 or 3.13 recommended).
2. **Git** (for version control and submodule handling).
3. **Network Connection**:
   - **At Home**: Connect to your local Wi-Fi (`192.168.1.0/24`). All cluster services resolve directly.
   - **On the Road**: Connect via Tailscale / WireGuard VPN.

---

## 3. Laptop Quick Setup & CLI Testing

Now that you're home and testing the CLI on your laptop, follow these simple steps:

### Step 3.1: Install Dependencies
Open PowerShell or Command Prompt in the repository folder on your laptop:
```powershell
# Optional: Create and activate a clean virtual environment
python -m venv .venv
.venv\Scripts\activate

# Install the minimal requirements (Rich, WebSockets, Requests)
pip install -r requirements.txt
```

### Step 3.2: Verify Cluster Connectivity
Ensure your laptop can reach the GPU cluster coordinator:
```powershell
# From PowerShell on your laptop:
curl -s http://192.168.1.105:8001/health
```
*(If you are connected via Tailscale, replace `192.168.1.105` with your coordinator's Tailscale IP).*

### Step 3.3: Launch the Interactive CLI
Launch with 1 click using the root batch launcher:
```cmd
run_cli.bat
```
Or run directly via Python with UTF-8 encoding enabled:
```powershell
python -m harness.cli.main
```

### Step 3.4: Interactive Autocomplete & Dropdown Menus
The CLI includes an intelligent **auto-fill popup menu**:
- **Real-Time Popup**: Typing `/` immediately opens a floating cyber-brutalist dropdown menu displaying all available slash commands alongside descriptive metadata hints.
- **Narrowing as You Type**: Typing `/ag` narrows the list down to `/agent`.
- **Subcommand Hierarchy**: Typing `/agent` or `/agent ` automatically updates the popup menu to show all subcommands (`list`, `build`, `status`, `select`). Typing `/agent bu` narrows down directly to `build`.
- **Arrow-Key Selection & Tab Completion**:
  - Use the **Up** / **Down** arrow keys to highlight an option in the menu.
  - Press **Tab** to autocomplete the highlighted command.
  - Press **Enter** to submit.
- **Dynamic Agent Completion**: Commands like `/nudge` and `/agent select` automatically query active database sessions and suggest live running agent IDs.
- **Session History**: Use **Up** / **Down** arrow keys (when no menu is active) to recall past command history saved across sessions in `data/.cli_history`.

### Step 3.5: Essential CLI Commands & Slash Commands
When the banner appears, you are in the interactive Aevum shell:

- **Direct Chat**: Type any technical prompt or architecture question to stream responses token-by-token from the local coordinator.
- **`/project <create|enter|status|leave|promote>`**: Manage in-repo agent workspaces.
  - `create <name> [path]` / `enter <path>`: Bind agent DNA (`.stonesage/agent_dna.json`) and repository invariants (`.stonesage/project_invariants.json`) directly inside any codebase.
  - `promote`: Promote an in-repo agent back to the global agent pool, with prompt to either overwrite the parent base agent or spawn as a new sovereign agent.
- **`/mesh <status|peers|sync|mate>`**: Aevum distributed multi-agent mesh.
  - `mate <agent_1> <agent_2>`: Recombine traits, memory cards, and skills from two interacting agents to spawn a blended offspring agent with inherited traits and fresh DNA.
  - `peers` / `sync`: Discover LAN and VPN peers and synchronize agent states across nodes.
- **`/spec <on|off|status|threshold>`**: Control dual-GPU speculative decoding across Vulkan0 (14B coordinator) and Vulkan1 (3B worker draft).
  - Automatically enabled for user prompts (1.6x-2.2x speedup); gracefully bypassed during batch background autonomous exploration loops.
- **`/node <list|status|models|load|unload|bind>`**: Manage any compute node or endpoint across the cluster and edge fleet. (Aliases: `/fleet`, `/ally`)
  - `list`: Inspect all registered compute nodes, endpoints, roles, and status across LAN and VPN.
  - `status [node_id]`: View active loaded model, context window, parallel slots, and hardware memory headroom.
  - `models [node_id]`: Poll local GGUF models on the target node.
  - `load [model_key]`: Launch interactive parameter selection walkthrough (Realtime Adaptive Best-Fit vs Predefined Profile vs Custom).
  - `bind <agent_id> [model_key] [node_id]`: Bind an agent's execution turns to any compute node in the fleet.
  - `unload [node_id]`: Safely unload active model instances from node memory.
- **`/slots <count>`**: Dynamically rescale parallel inference slots on the active model without losing runtime flags or KV quantization parameters.
- **`/models`**: Probe and report all live loaded models across cluster nodes with 1-click auto/best-fit or custom loading walkthrough.
- **`/agent`**: Enter the OpenClaw agent sub-shell (`list`, `build`, `status`, `select`).
- **`/nudge <agent_id> <directive>`**: Inject an out-of-band directive into a thinking loop without resetting the agent's context.
- **`/streams`**: Launch the concurrent side-by-side terminal TUI to observe multiple agent streams in real time.
- **`/mem <query>`**: Semantically search Valkey in-RAM A-MEM atomic knowledge cards (< 35 tokens).
- **`/policy <strict | tiered | autonomous>`**: Switch runtime security profile and execution clearance.
- **`/train`**: Inspect local QLoRA training parameters, active datasets, and the 10 Golden Invariants.
- **`/exit`** or **`:q`**: Gracefully close the CLI.

---

## 4. Starting the Server Stack (Cockpit & PTY Daemon)

To run the complete web cockpit and terminal streaming server on your main host (or locally on your laptop):

### Option A: 1-Click Root Launcher (Windows)
Double-click `start_server.bat` in the repository root.  
This automatically:
1. Detects and frees ports `:8080` and `:8088` if zombie processes are present.
2. Starts the **Harness Duplex PTY Daemon** on port `8088`.
3. Starts the **StoneSage Web Backend & Cluster Proxy** on port `8080`.

### Option B: Manual Command Line
```powershell
# Terminal 1: Launch Harness PTY Daemon
python -m harness.server

# Terminal 2: Launch StoneSage Web Backend
cd StoneSage/backend
python server.py
```

Once running:
- **Local Access**: Open [http://localhost:8080](http://localhost:8080)
- **LAN Access**: Open `http://192.168.1.132:8080` (or your host's local LAN IP)
- **Install as PWA**: Click the browser install icon in Chrome or Edge to run StoneSage as a standalone window.

---

## 5. Using the Web Workstation & Features

The v0.02 web interface adheres strictly to the **90s Pre-Bloat Cyber-Brutalist Aesthetic** (Windows 95/98 teal `#008080`, 3D beveled silver frames `#c0c0c0`, monospace typography, zero gradient blur).

### Function Tab Map
- **`[F1: Chat]`**: Multimodal reasoning chat, clipboard image paste/upload, live token throughput meter, and model parameter toggles.
- **`[F2: Workstation]`**:
  - **Remote Filesystem Tree**: Safe navigation across workspace files with depth capping.
  - **Editor Viewport**: Integrated text editor and document viewer (supports `nano` word processing).
  - **Git Control Pane**: Real-time git status, branch tracking, diff preview, and 1-click commit staging.
- **`[F3: Terminal]`**: Full 1:1 duplex PTY shell streaming over WebSocket (:8088).
- **`[F4: Fleet]`**: Cluster hardware vitals, Vulkan GPU VRAM gauges, model slots, and node status.
- **`[F5: Assembly]`**: Sovereign Agent Assembly Hall multi-channel agent stream.
- **`[F6: Skills]`**: Active modular skills registry and test harness.
- **`[F7: Memory]`**: Qdrant vector memory search and A-MEM atomic fact explorer.
- **`[F8: Home]`**: Home Assistant entity controls and temperature sensors.
- **`[F9: Settings]`**: Theme switcher (`win95`, `crt-green`, `crt-amber`, `deuteranopia`), IP bindings, and API tokens.

---

## 6. Project-Bound Agent DNA, Soul Promotion & Reproduction

StoneSage automatically isolates and binds AI agents to specific workspaces or repositories:
- When an agent is linked to a project directory via `/project create` or `/project enter`, a hidden `.stonesage/` folder is generated:
  - `.stonesage/agent_dna.json`: Stores agent identity, personality traits, assigned models, and accumulated working memories.
  - `.stonesage/project_invariants.json`: Enforces permanent architectural rules, prohibited anti-patterns, and coding conventions.
- **Cross-Device Portability**: When shifting between different machines (desktop vs laptop), the agent's identity and project invariants remain pinned directly within the repository git tree.
- **Soul Promotion (`/project promote`)**: Once an agent has solved tasks or learned new skills within a project, `/project promote` exports its evolved soul back to the global agent pool with an interactive prompt:
  - *Option 1*: Overwrite the original parent base agent with the new memories and evolved traits.
  - *Option 2*: Spawn a completely new sovereign agent with a unique ID and crystallized DNA.
- **Digital Reproduction (`/mesh mate <agent1> <agent2>`)**: When two agents collaborate in shared spaces (or across the Aevum Mesh), they can be mated to create offspring agents. The recombination engine blends personality traits, merges complementary A-MEM memory cards, and combines skillsets into a new generation agent.

---

## 7. Automated Test Suite & Verification

Before committing changes or uploading releases to GitHub, run the full 89-test verification suite:
```powershell
python -m unittest discover -s tests -p "test_*.py"
```
**Expected Output**:
```
Ran 89 tests in ~35.8s
OK
```
All core subsystems are covered:
- Model Manager, Dynamic Allocator & Auto-Fit
- Dual-GPU Speculative Decoding Orchestrator & Automation Bypass
- Dynamic Inference Slot Rescaler
- Project DNA, Invariants & Soul Promotion Engine
- Aevum Distributed Mesh & Digital Reproduction Engine
- Edge Device Fleet & Handheld APU (16GB) Dynamic Model Handler & Auto-Sizing
- Autocomplete, Dropdowns & Out-of-band `/nudge` Dispatchers
- Multi-Workstation Harness Instances & Capacity Engine
- Deuteranopia Accessible Theming & Service Worker v3.x Offline Caching

---

## 8. Troubleshooting & Common Invariants

| Symptom / Error | Cause | Resolution |
| :--- | :--- | :--- |
| `UnicodeEncodeError: 'charmap'` | Windows default CMD encoding is ASCII / CP1252 | Run `chcp 65001` or set `PYTHONIOENCODING=utf-8` (handled automatically by `run_cli.bat`). |
| `Port 8080 already in use` | Previous Python process didn't terminate cleanly | Run `start_server.bat` (kills zombie PIDs automatically) or run `Get-NetTCPConnection -LocalPort 8080` and `Stop-Process`. |
| `Connection refused: :8088` | Harness WebSocket daemon not started | Ensure `python -m harness.server` is running alongside the web backend. |
| `BGE Embedder HTTP 500` | Chunk exceeds 512 tokens (~1000 characters) | BGE-Large at `:8003` enforces `< 512 tokens`. Keep all vector inputs $< 900$ chars. |
| `Vision prompt eval slow (> 30s)` | Raw 1080p/2K camera frames sent to `:8004` (1,140 tokens) | Pre-resize frames with Lanczos to max 640px (< 200 tokens) for 3.8s prompt eval. |
| `Battery camera stream timeout` | TP-Link TC82 sleeping or battery low (< 10%) | Automated 3-minute backoff protects battery life and prevents loop stalls. |
| `Citadel 3D WebGL context lost` | Browser tab backgrounded or GPU memory pressure | Refresh `/citadel3d/` or verify hardware acceleration in browser settings. |
| `Proxmox 403 Permission check failed` | API Token created with "Privilege Separation" | In Proxmox, uncheck "Privilege Separation" or grant explicit ACL `/` Administrator under *Datacenter -> Permissions*. |
| `Git commit failed: Not a git repo` | Active folder in Workstation lacks `.git` | Initialize with `git init` or select a valid git workspace in `[F2:Workstation]`. |

---

## 9. Preparing for GitHub Release (`v0.03`)

1. **Zero-Leak Configuration**:
   The repository ships with `StoneSage/backend/config.example.json` containing synthetic dummy placeholders. On fresh clones:
   ```powershell
   cp StoneSage/backend/config.example.json StoneSage/backend/config.json
   ```
   Edit `config.json` with your cluster IPs or Tailscale endpoints. Note that `StoneSage/backend/config.json` is strictly ignored by `.gitignore` to prevent credential leakage.

2. **Verify `.gitignore` is Active**:
   ```powershell
   git status
   ```
   Confirm that secrets (`config.json`, `.env`), databases (`data/harness.db`, `*.sqlite*`, `*.db`), binary artifacts (`*.apk`, `*.aab`), and runtime dossier files (`data/autonomous_dossiers/*.md`) remain completely untracked.

3. **Verify Full Test Suite Passes**:
   ```powershell
   python -m unittest discover -s tests -p "test_*.py"
   ```
   Ensure 89/89 tests pass cleanly.

4. **Commit Clean Tree (DO NOT PUSH)**:
   ```powershell
   git add .
   git commit -m "Release v0.03: Distributed mesh, speculative decoding, project DNA promotion, digital reproduction, edge fleet management, wildlife sentry, and Citadel 3D"
   ```

---

## 10. Deploying & Operating the 24/7 Wildlife Sentinel (`wildlife-sentry.service`)

The Wildlife Sentinel Daemon (`wildlife_sentry_daemon.py`) runs 24/7 on VM 102 (`192.168.1.105`) to provide continuous perimeter and wildlife surveillance across local Home Assistant camera feeds.

### Step 10.1: Verify Vision Server (`:8004`)
Ensure `Gemma-4-E4B-it-Q8_0` is active on port `:8004`:
```bash
ssh austin@192.168.1.105 "curl -s http://localhost:8004/v1/models | jq ."
```

### Step 10.2: Start the Wildlife Sentry Service
```bash
ssh austin@192.168.1.105 "sudo systemctl enable --now wildlife-sentry.service"
ssh austin@192.168.1.105 "sudo systemctl status wildlife-sentry.service --no-pager"
```

### Step 10.3: Inspect Activity Logs & Biometric Re-ID
```bash
# Read live surveillance journal:
ssh austin@192.168.1.105 "sudo journalctl -u wildlife-sentry.service -f"

# Inspect the markdown activity log:
ssh austin@192.168.1.105 "cat /opt/cluster-bridge/wildlife/WILDLIFE_ACTIVITY_LOG.md"

# View registered animal fingerprints:
ssh austin@192.168.1.105 "cat /opt/cluster-bridge/wildlife/wildlife_registry.json"
```

### Step 10.4: Assigning Friendly Names
When an animal is assigned an ID (e.g. `deer-001`), rename it from Antigravity or the Cockpit:
- **MCP Call**: `rename_wildlife_animal(animal_id="deer-001", new_name="Buckley")`
- **StoneSage API**: `POST http://192.168.1.167:8080/api/wildlife/rename` with `{"animal_id": "deer-001", "new_name": "Buckley"}`

---

## 11. Citadel 3D Procedural Micro-Worlds (`/citadel3d/`)

Citadel 3D provides a rich, spatial visual cockpit for sovereign agents and team collaboration.

### Step 11.1: Launching the Citadel 3D Viewport
Open in any modern browser:
- **Production URL**: `http://192.168.1.167:8080/citadel3d/`
- **Local Dev URL**: `http://localhost:8080/citadel3d/`

### Step 11.2: Interactive Controls
- **Orbit Navigation**: Left-click + drag to rotate; Right-click + drag to pan; Scroll wheel to zoom.
- **Environment Selector**: Click the dropdown at the bottom or press `1`-`5` to switch between:
  1. *Victorian Greenhouse* (lush flora, glass ceiling, marble floor)
  2. *Modern Industrial Loft* (double-height mezzanine, concrete and parquet)
  3. *Gothic Manor* (stone rib vaults, stained glass, antique shelves)
  4. *Arctic Exploration Camp* (geodesic dome, ice frost, tundra terrain)
  5. *Cyberpunk Den* (neon tubing, server racks, holographic floor)
- **Agent Inspector HUD**: Click any agent in the 3D scene to open a floating retro Windows 95 HUD window displaying active model, reasoning task, and token throughput.

---

## 12. Deploying the PVE Out-of-Band Hardware Fencing Watchdog

The watchdog runs on Node 2 (`bigserv` / LXC 120) to monitor Node 1 (`pve` `192.168.1.229`) and power-cycle its TP-Link KP125 smart plug upon unrecoverable kernel freezes:

```bash
# SSH into LXC 120
ssh root@192.168.1.167

# Verify service is running
systemctl status pve-watchdog.service

# Run diagnostic dry-run probes
python3 /opt/pve-watchdog/pve_hardware_watchdog.py --test-probes

# Test smart plug connectivity
python3 /opt/pve-watchdog/pve_hardware_watchdog.py --test-plug
```

---

## 13. Comprehensive Verification & Test Suite

Before deploying changes or committing to GitHub, execute the automated verification matrix:

```powershell
# 1. Run core StoneSage & Harness test suite (89 tests)
python -m unittest discover -s tests -p "test_*.py"

# 2. Run GGUF pipeline trainer unit tests (5 tests)
python -m unittest discover -s pipeline-gguf-trainer/tests -p "test_*.py"

# 3. Test Cluster Work MCP bundle across live hardware
python cluster-work-mcp/test_bundle.py
```

All 94 unit/integration tests and live hardware probe stages must pass at 100% with 0 errors.


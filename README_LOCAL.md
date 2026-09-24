# StoneSage Homelab Operator Guide: Local Stack Reference & Runbook

> **Not operational truth (Phase 0, 2026-09-23).** What is actually deployed lives in [`STATE.md`](STATE.md), updated from live `/props` and the VM 102 report. Hardware, models, ports and service lists below may be stale; check `STATE.md` first.

> **Audience**: Homelab Operator (Austin / John)  
> **Workspace**: [`c:/Users/johna/OneDrive/Documents/.ai`](file:///c:/Users/johna/OneDrive/Documents/.ai)  
> **Obsidian Vault**: `C:\Users\johna\OneDrive\Documents\obsidian\`  
> **Host LAN IP**: `192.168.1.132` (Windows Harness Host)  
> **Cluster API**: `https://192.168.1.245:8006` (Proxmox VE 9.2 API, served by bigserv)  

---

## 1. Quick Launchers & Daily Shortcuts

| Action | Command / Target | Purpose |
| :--- | :--- | :--- |
| **Launch CLI Harness** | [`run_cli.bat`](file:///c:/Users/johna/OneDrive/Documents/.ai/run_cli.bat) | Starts StoneSage Unified CLI v4.0.6 with prompt dropdown. |
| **Launch Local Server** | [`start_server.bat`](file:///c:/Users/johna/OneDrive/Documents/.ai/start_server.bat) | Starts local StoneSage backend and terminal PTY daemon. |
| **Open Web Cockpit** | [http://192.168.1.167:8888](http://192.168.1.167:8888) | 24/7 StoneSage Cockpit on LXC 120 (port `:8080` redirects). |
| **Open Citadel 3D** | [http://192.168.1.167:8888/citadel3d/](http://192.168.1.167:8888/citadel3d/) | 3D procedural environments & agent inspector deck. |
| **Sync Code to LXC 120** | [`server setup/sync_stonesage_to_lxc.ps1`](file:///c:/Users/johna/OneDrive/Documents/.ai/server%20setup/sync_stonesage_to_lxc.ps1) | Pushes StoneSage backend and frontend to LXC 120. |
| **Sync Obsidian Vault** | [`server setup/sync_archive_to_obsidian.ps1`](file:///c:/Users/johna/OneDrive/Documents/.ai/server%20setup/sync_archive_to_obsidian.ps1) | Syncs autonomous thinking dossiers to local Obsidian. |

---

## 2. Complete Local Infrastructure & Endpoint Directory

### Node 1: `pve` (`192.168.1.222` - Intel i7-12700K, 32GB RAM, Dual AMD GPUs)

Power-fenced via TP-Link Kasa KP125 (`192.168.1.109:9999`).

#### VM 102 (`ubu` - `192.168.1.105` - Ubuntu 24.04 LTS)
SSH: `ssh austin@192.168.1.105`

| Service | Port | Endpoint URL | Hardware / Backing Process | Service Unit |
| :--- | :--- | :--- | :--- | :--- |
| **Coordinator** | `:8001` | [http://192.168.1.105:8001](http://192.168.1.105:8001) | Ornith-1.5-9B (Q8) on AMD RX 6750 XT 12GB (`Vulkan0`) | [`llama-coordinator.service`](file:///c:/Users/johna/OneDrive/Documents/.ai/server%20setup/vm-setup/systemd/llama-coordinator.service) |
| **Worker** | `:8002` | [http://192.168.1.105:8002](http://192.168.1.105:8002) | Ornith-1.5-9B (Q4_K_M) on AMD RX 6600 XT 8GB (`Vulkan1`), F16 KV | [`llama-worker.service`](file:///c:/Users/johna/OneDrive/Documents/.ai/server%20setup/vm-setup/systemd/llama-worker.service) |
| **Embedder** | `:8003` | [http://192.168.1.105:8003](http://192.168.1.105:8003) | BGE-Large-en-v1.5 (1024-d) on AMD RX 6600 XT 8GB (`Vulkan1`) | [`llama-embedder.service`](file:///c:/Users/johna/OneDrive/Documents/.ai/server%20setup/vm-setup/systemd/llama-embedder.service) |
| **Vision** | `:8004` | [http://192.168.1.105:8004](http://192.168.1.105:8004) | Qwen2.5-VL-7B-Instruct (Q4_K_M) on CPU (12 cores, `-ngl 0`) | [`vision-server.service`](file:///c:/Users/johna/OneDrive/Documents/.ai/server%20setup/vm-setup/systemd/vision-server.service) |
| **Valkey Memory** | `:6379` | `192.168.1.105:6379` | Valkey 9.0.4 In-RAM sub-ms A-MEM atomic store (< 35 tokens) | `valkey.service` |
| **Cluster MCP** | `:8765` | [http://192.168.1.105:8765](http://192.168.1.105:8765) | Starlette JSON-RPC / SSE MCP Bridge (`/opt/cluster-bridge`) | [`cluster-mcp.service`](file:///c:/Users/johna/OneDrive/Documents/.ai/server%20setup/vm-setup/systemd/cluster-mcp.service) |
| **Assembly Hall** | `:8766` | `ws://192.168.1.105:8766` | Sovereign Agent duplex WebSocket fabric & cloud bridge | `assembly-hall.service` |
| **FaunaSentinel** | Background | Internal daemon | 24/7 Wildlife & perimeter vision sentry daemon | [`wildlife-sentry.service`](file:///c:/Users/johna/OneDrive/Documents/.ai/server%20setup/cluster-bridge/wildlife-sentry.service) |

#### LXC 117 (`qdrant` - `192.168.1.112:6333`)
SSH: `ssh root@192.168.1.112`

| Collection Name | Dimension | Distance | Purpose |
| :--- | :--- | :--- | :--- |
| `autonomous_thinking` | 1024-d | Cosine | Autonomous dossiers, divergence metrics, Tier-1 Frontier verdicts. |
| `agent_memories` | 1024-d | Cosine | Sovereign agent autobiographical memories & genetic lineage cards. |
| `codebase_knowledge` | 1024-d | Cosine | Homelab architectural docs, invariants, and operational guides. |
| `companion_profile` | 1024-d | Cosine | User preference models, conversational patterns, and history. |
| `home_automation_registry` | 1024-d | Cosine | Device mappings, Home Assistant service domains, and entities. |
| `session_transcripts` | 1024-d | Cosine | Long-term multi-turn conversational transcripts and summaries. |

*Web Dashboard*: [http://192.168.1.112:6333/dashboard](http://192.168.1.112:6333/dashboard)

---

### Node 2: `bigserv` (`192.168.1.245` - Application, Media & Storage Node)

SSH: `ssh root@192.168.1.245` (no key installed yet; use the API)

| Host / VM / Container | IP Address | Port | Description |
| :--- | :--- | :--- | :--- |
| **VM 103 (`haos`)** | `192.168.1.82` | `:8123` | [Home Assistant OS](http://192.168.1.82:8123) (Lights, switches, HVAC, cameras) |
| **LXC 120 (`stonesage`)** | `192.168.1.167` | `:8888` | [StoneSage Cockpit](http://192.168.1.167:8888) & [`pve-watchdog.service`](file:///c:/Users/johna/OneDrive/Documents/.ai/server%20setup/watchdog/pve-watchdog.service) |
| **LXC 127 (`blender-compute`)**| `192.168.1.248` | `:8095` | [Headless Blender 4.0.2 Cycles Engine](http://192.168.1.248:8095) (Quadro M2000 GPU) |
| **LXC 121 (`voice-services`)** | `192.168.1.121` | `:8200` | Faster Whisper STT (`:8200`) & Kokoro TTS (`:8300`) |
| **LXC 116 (`obsidian-sync`)**   | `192.168.1.230` | `:5984` | [CouchDB Obsidian Live-Sync](http://192.168.1.230:5984) |
| **LXC 119 (`openwebui`)**       | `192.168.1.108` | `:8080` | [Open WebUI Multi-Model Interface](http://192.168.1.108:8080) |
| **LXC 107 (`immich`)**          | `192.168.1.238` | `:9000` | [Immich Photos & Videos](http://192.168.1.238:9000) |
| **LXC 104 (`jellyfin`)**        | `192.168.1.180` | `:8096` | [Jellyfin Media Streaming](http://192.168.1.180:8096) |
| **LXC 101 (`adguard`)**         | `192.168.1.194` | `:80`   | [AdGuard DNS Sinkhole](http://192.168.1.194:80) (DNS `:53`) |
| **LXC 100 (`kavita`)**          | `192.168.1.124` | `:5000` | [Kavita Manga & Book Reader](http://192.168.1.124:5000) |
| **LXC 114 (`qbittorrent`)**     | `192.168.1.169` | `:8090` | [qBittorrent Torrent Client](http://192.168.1.169:8090) |
| **LXC 105 (`docker`)**          | `192.168.1.204` | `:9443` | [Portainer Container Admin](https://192.168.1.204:9443) |

---

### IoT & Smart Device Registry

| Device Name | IP Address | Protocol | Role |
| :--- | :--- | :--- | :--- |
| **KP125 Smart Plug** | `192.168.1.109:9999` | Local TCP XOR | Power fences Node 1 (`pve`). Controlled by watchdog. |
| **Nest Thermostat** | `192.168.1.62` | Matter / SDM | HVAC target and ambient temperature control. |
| **Backyard Camera (TC82)** | RTSP | TP-Link RTSP | Battery camera tracked by `wildlife-sentry.service`. |
| **Living Room Camera** | RTSP / Tapo | Stream | Monitored by `home-agent` and vision stack. |
| **GE Smart Plugs** | `192.168.1.17`, `.111`, `.143` | Zigbee / Wi-Fi | Auxiliary homelab power switching. |
| **Mobile Cockpit** | `192.168.1.178` | Wi-Fi / PWA | S25 Ultra mobile workstation access. |

---

## 3. Local Key Files & Direct Links

### Backend & Harness Core
- Primary Server: [`StoneSage/backend/server.py`](file:///c:/Users/johna/OneDrive/Documents/.ai/StoneSage/backend/server.py)
- Cluster Model Router: [`StoneSage/backend/cluster_client.py`](file:///c:/Users/johna/OneDrive/Documents/.ai/StoneSage/backend/cluster_client.py)
- Proxmox VIP Client: [`StoneSage/backend/proxmox_client.py`](file:///c:/Users/johna/OneDrive/Documents/.ai/StoneSage/backend/proxmox_client.py)
- Home Assistant Client: [`StoneSage/backend/hass_client.py`](file:///c:/Users/johna/OneDrive/Documents/.ai/StoneSage/backend/hass_client.py)
- Terminal CLI Commands: [`harness/cli/commands.py`](file:///c:/Users/johna/OneDrive/Documents/.ai/harness/cli/commands.py)
- Project & Workspace DNA: [`harness/core/project_manager.py`](file:///c:/Users/johna/OneDrive/Documents/.ai/harness/core/project_manager.py)
- Speculative Engine: [`harness/core/speculative_engine.py`](file:///c:/Users/johna/OneDrive/Documents/.ai/harness/core/speculative_engine.py)

### Frontend & 3D Worlds
- Workstation HTML: [`StoneSage/frontend/index.html`](file:///c:/Users/johna/OneDrive/Documents/.ai/StoneSage/frontend/index.html)
- Retro Style Sheet: [`StoneSage/frontend/style.css`](file:///c:/Users/johna/OneDrive/Documents/.ai/StoneSage/frontend/style.css)
- Frontend Logic: [`StoneSage/frontend/app.js`](file:///c:/Users/johna/OneDrive/Documents/.ai/StoneSage/frontend/app.js)
- Citadel 3D Micro-Worlds: [`StoneSage/frontend/citadel3d/index.html`](file:///c:/Users/johna/OneDrive/Documents/.ai/StoneSage/frontend/citadel3d/index.html)
- Procedural Textures: [`StoneSage/frontend/citadel3d/texture_generator.js`](file:///c:/Users/johna/OneDrive/Documents/.ai/StoneSage/frontend/citadel3d/texture_generator.js)

### Systemd Units & Remote Services
- Coordinator Unit: [`server setup/vm-setup/systemd/llama-coordinator.service`](file:///c:/Users/johna/OneDrive/Documents/.ai/server%20setup/vm-setup/systemd/llama-coordinator.service)
- Worker Unit: [`server setup/vm-setup/systemd/llama-worker.service`](file:///c:/Users/johna/OneDrive/Documents/.ai/server%20setup/vm-setup/systemd/llama-worker.service)
- Embedder Unit: [`server setup/vm-setup/systemd/llama-embedder.service`](file:///c:/Users/johna/OneDrive/Documents/.ai/server%20setup/vm-setup/systemd/llama-embedder.service)
- Vision Unit: [`server setup/vm-setup/systemd/vision-server.service`](file:///c:/Users/johna/OneDrive/Documents/.ai/server%20setup/vm-setup/systemd/vision-server.service)
- Wildlife Sentry Unit: [`server setup/cluster-bridge/wildlife-sentry.service`](file:///c:/Users/johna/OneDrive/Documents/.ai/server%20setup/cluster-bridge/wildlife-sentry.service)
- PVE Watchdog Unit: [`server setup/watchdog/pve-watchdog.service`](file:///c:/Users/johna/OneDrive/Documents/.ai/server%20setup/watchdog/pve-watchdog.service)

### Invariant & Architecture Documentation
- Workspace Rules: [`GEMINI.md`](file:///c:/Users/johna/OneDrive/Documents/.ai/GEMINI.md)
- Network Device Registry: [`server setup/NETWORK_DEVICE_REGISTRY.md`](file:///c:/Users/johna/OneDrive/Documents/.ai/server%20setup/NETWORK_DEVICE_REGISTRY.md)
- Companion Manifesto: [`server setup/COMPANION_MANIFESTO.md`](file:///c:/Users/johna/OneDrive/Documents/.ai/server%20setup/COMPANION_MANIFESTO.md)
- Hardware Watchdog Guide: [`server setup/PVE_HARDWARE_WATCHDOG_GUIDE.md`](file:///c:/Users/johna/OneDrive/Documents/.ai/server%20setup/PVE_HARDWARE_WATCHDOG_GUIDE.md)

---

## 4. Operational Runbook & Common Maintenance Commands

### 4.1 Probing Cluster Health from Windows
Run from PowerShell to check all service endpoints:
```powershell
# Probe GPU compute ports on VM 102
curl.exe -s http://192.168.1.105:8001/props | Select-String "model"
curl.exe -s http://192.168.1.105:8002/props | Select-String "model"
curl.exe -s http://192.168.1.105:8003/props | Select-String "model"
curl.exe -s http://192.168.1.105:8004/props | Select-String "model"

# Probe Qdrant vector database
curl.exe -s http://192.168.1.112:6333/collections

# Probe StoneSage Cockpit on LXC 120
curl.exe -s http://192.168.1.167:8888/api/status
```

### 4.2 Restarting Services on VM 102 (`austin@192.168.1.105`)
```bash
# Restart Coordinator (RX 6750 XT)
ssh austin@192.168.1.105 "sudo systemctl restart llama-coordinator.service"

# Restart Worker (RX 6600 XT)
ssh austin@192.168.1.105 "sudo systemctl restart llama-worker.service"

# Restart Vision Server (CPU)
ssh austin@192.168.1.105 "sudo systemctl restart vision-server.service"

# Restart Cluster MCP Bridge
ssh austin@192.168.1.105 "sudo systemctl restart cluster-mcp.service"

# View live service logs
ssh austin@192.168.1.105 "journalctl -u llama-worker.service -f -n 50"
```

### 4.3 Updating StoneSage on LXC 120 (`root@192.168.1.167`)
Whenever you make edits to `StoneSage/backend/` or `StoneSage/frontend/`, sync them instantly:
```powershell
# Run PowerShell sync script from workspace root:
& ".\server setup\sync_stonesage_to_lxc.ps1"
```
Or restart `stonesage.service` directly on LXC 120:
```bash
ssh root@192.168.1.167 "systemctl restart stonesage.service"
```

### 4.4 Running Automated Verification Suites
```powershell
# Run all harness and CLI tests (89 tests)
python -m unittest discover -s tests -p "test_*.py"

# Run GGUF trainer tests (5 tests)
python -m unittest discover -s pipeline-gguf-trainer/tests -p "test_*.py"
```

---

## 5. Critical Invariants & Rules of Thumb

1. **Unquantized KV Cache Priority**: If weights and uncompressed F16 KV cache fit within VRAM, never quantize KV. Ornith-1.5-9B on `:8002` runs at 8,192 context with unquantized F16 KV cache (`-ctk f16 -ctv f16`) using 6.8 GB of 8.0 GB VRAM.
2. **Vulkan Device Naming**: Always use `--device Vulkan0` and `--device Vulkan1`. Never pass integer device indexes.
3. **Proxmox Cluster API**: All API telemetry calls target `https://192.168.1.245:8006` (bigserv). `192.168.1.82` is the Home Assistant OS VM, not a Proxmox node.
4. **BGE Context Limit (< 512 Tokens)**: Port `:8003` accepts chunks under 1,000 characters. Exceeding 512 tokens causes HTTP 500.
5. **Vision Server 640px Pre-Resizing**: Always pre-resize camera frames with Lanczos interpolation to max 640px before calling `:8004`. Reduces latency from 31 seconds to 3.8 seconds.
6. **Zero-Leak Secret Policy**: Never commit credentials to git. All examples in docs must use synthetic dummy strings.

# StoneSage: Sovereign AI Command Cockpit & Workstation

> **Not operational truth (Phase 0, 2026-09-23).** What is actually deployed lives in [`STATE.md`](../STATE.md), updated from live `/props` and the VM 102 report. Hardware, models, ports and service lists below may be stale; check `STATE.md` first.

StoneSage is a cyber-brutalist homelab AI command center and developer workstation built for the dual-GPU PVE cluster. Operating with zero external UI frameworks, it pairs an authentic 1990s pre-bloat interface (Windows 95/98 silver frames, teal desktop `#008080`, monospace typography) with multi-model routing, full terminal PTY streaming, multimodal vision, and spatial 3D agent environments.

---

## 1. Directory Structure

```
StoneSage/
├── backend/
│   ├── server.py            # Core HTTP REST & SSE API server (Port :8080)
│   ├── config.example.json  # Sanitized configuration template (Zero-Leak)
│   ├── cluster_client.py    # Local dual-GPU cluster proxy & model switcher
│   ├── proxmox_client.py    # Proxmox VE 9.2 Datacenter VIP API client
│   ├── hass_client.py       # Home Assistant REST API client
│   ├── couchdb_client.py    # CouchDB Obsidian sync client
│   ├── immich_client.py     # Immich photo vault client
│   └── reasoning_watchdog.py# Background reasoning loop monitor
├── frontend/
│   ├── index.html           # Main retro workstation & multi-tab layout
│   ├── app.js               # Application logic, REST bindings & WebSocket hooks
│   ├── style.css            # Windows 95/98 beveled chrome & CRT theme styling
│   ├── sw.js                # Service Worker for offline PWA execution
│   └── citadel3d/           # 3D Procedural Micro-Worlds & Kanban Deck (:8080/citadel3d/)
└── datasets/
    ├── homelab_curated_manifest.json # Training dataset registry
    └── curation_registry.json        # Dual-Gate audit states
```

---

## 2. Core Features & Navigation Map

### Workstation Function Tabs
- **`[F1: Chat]`**: Real-time streaming conversation with cluster models (`Ornith-1.5-9B`), image upload/clipboard paste, token throughput gauge, and sampling presets.
- **`[F2: Workstation]`**: Integrated multi-pane IDE with remote filesystem tree, `nano`-style text editor, and Git control pane (diffs, staging, commits).
- **`[F3: Terminal]`**: Full 1:1 duplex interactive PTY shell streaming over WebSocket (`:8088`).
- **`[F4: Fleet]`**: Cluster hardware vitals, Vulkan GPU VRAM allocations, model slots, and node health.
- **`[F5: Assembly]`**: Sovereign Agent Assembly Hall multi-channel stream (`#agora`, `#first-principles`, `#systems-code`, `#deep-ruminations`, `#vigilance-alerts`, `#forbidden-knowledge`).
- **`[F6: Skills]`**: Registry of 64 modular skills indexed in Qdrant with interactive testing.
- **`[F7: Memory]`**: Semantic vector search (Qdrant `:6333`) and Valkey in-RAM A-MEM atomic fact explorer.
- **`[F8: Home]`**: Home Assistant device status, switch toggles, climate controls, and camera feeds.
- **`[F9: Settings]`**: Theme switcher (`win95`, `crt-green`, `crt-amber`, `deuteranopia`), IP bindings, and API tokens.
- **`[/citadel3d/]`**: Spatial 3D procedural environments with interactive agent inspector.

---

## 3. Running StoneSage

### Windows Host:
```cmd
start_server.bat
```
Open [http://localhost:8080](http://localhost:8080).

### Homelab 24/7 Deployment:
Runs inside LXC 120 on Node 2 (`bigserv` @ `192.168.1.167:8080`):
```bash
ssh root@192.168.1.167 "systemctl status stonesage.service"
```
Accessible across the home network at `http://192.168.1.167:8080`.

# PVE Dual-GPU & Multimodal Cluster Deployment Guide

This guide details how to deploy the 24/7 dual-GPU LLM cluster, multimodal vision engine, and autonomous sentry infrastructure on your Ubuntu compute host VM 102 (`192.168.1.105`) and integrate it with Antigravity, StoneSage, and Qdrant.

---

## Architecture Summary

| Endpoint | Hardware / Port | Model | Role & Service Description |
| :--- | :--- | :--- | :--- |
| **Coordinator** | RX 6750 XT (12GB) / `:8001` | `Ornith-1.5-9B-Instruct` (Q8_0) | 24/7 Systems Proofs, Deep Logic Solver & Master Reasoner |
| **Worker** | RX 6600 XT (8GB) / `:8002` | `Ornith-1.5-9B-Instruct` (Q4_K_M) | Fast Ideation, Speculative Draft, Tests, Linter (80+ t/s) |
| **Embedder** | RX 6600 XT (8GB) / `:8003` | `bge-large-en-v1.5` (F16) | Continuous Vector Embedding Engine (< 512 tokens / < 950 chars) |
| **Vision Server** | CPU (12 Threads) / `:8004` | `Gemma-4-E4B-it-Q8_0` + `mmproj` | 24/7 Multimodal Vision & Camera Frame Analysis |
| **Valkey A-MEM** | In-RAM / `:6379` | Valkey 9.0.4 | Sub-millisecond Atomic Working Memory Cards (< 35 tokens) |
| **Vector Brain** | LXC 117 / `:6333` | Qdrant Vector Engine | 6 Persistent Collections (1024-d Cosine metric) |
| **FaunaSentinel** | VM 102 Daemon | `wildlife_sentry_daemon.py` | 24/7 Autonomous Wildlife & Perimeter Perception Daemon |
| **Assembly Hall**| VM 102 / `:8766` | `assembly_server.py` | Multi-channel real-time agent streaming fabric (WebSocket) |
| **MCP Bridge** | VM 102 / `:8765` | `mcp_server.py` (SSE) | Native JSON-RPC / SSE Bridge into Antigravity IDE & Cockpit |

---

## Step 1: Copy Files to the Ubuntu Compute Host (VM 102)

From PowerShell on your Windows workstation, transfer the setup directories to VM 102:

```powershell
# Transfer deployment assets (strip trailing backslashes for OpenSSH compatibility)
scp -r "c:\Users\johna\OneDrive\Documents\.ai\server setup\vm-setup" austin@192.168.1.105:/tmp/vm-setup
scp -r "c:\Users\johna\OneDrive\Documents\.ai\server setup\cluster-bridge" austin@192.168.1.105:/tmp/cluster-bridge
```

---

## Step 2: Build Vulkan llama.cpp & Verify Device Identifiers

SSH into VM 102:
```bash
ssh austin@192.168.1.105
cd /tmp/vm-setup
chmod +x *.sh

# Run Vulkan compilation script
./01_install_vulkan_llamacpp.sh
```

### Critical Vulkan Device Naming Invariant
`llama-server` strictly requires device strings `--device Vulkan0` and `--device Vulkan1`. Passing raw integers (`--device 0`) crashes the argument parser.

Verify detected Vulkan devices:
```bash
/usr/local/bin/llama-server --list-devices
```
Expected:
- `Vulkan0`: AMD Radeon RX 6750 XT (12GB VRAM - NAVI22)
- `Vulkan1`: AMD Radeon RX 6600 XT (8GB VRAM - NAVI23)

---

## Step 3: Install Models & Initialize Qdrant Memory

```bash
# Verify models are placed in /opt/models
ls -lh /opt/models/
# Expected models:
# - Ornith-1.5-9B-Instruct-Q8_0.gguf
# - Ornith-1.5-9B-Instruct-Q4_K_M.gguf
# - bge-large-en-v1.5.gguf
# - Gemma-4-E4B-it-Q8_0.gguf & mmproj-gemma-4-E4B-it-BF16.gguf

# Install Python requirements for bridge, sentry, and Qdrant
pip3 install -r /tmp/cluster-bridge/requirements.txt pillow requests qdrant-client

# Initialize Qdrant vector collections on LXC 117
python3 /tmp/cluster-bridge/qdrant_init.py --host 192.168.1.112 --port 6333
```

---

## Step 4: Install Systemd Services (24/7 Persistence)

Deploy the services to `/opt/cluster-bridge` and register the systemd daemons:

```bash
# Sync cluster bridge into /opt
sudo rsync -av --exclude '.git' /tmp/cluster-bridge/ /opt/cluster-bridge/
sudo chown -R austin:austin /opt/cluster-bridge

# Ensure wildlife logs directory exists with write permissions
mkdir -p /opt/cluster-bridge/wildlife
chmod 775 /opt/cluster-bridge/wildlife

# Copy systemd unit definitions
sudo cp /tmp/vm-setup/systemd/llama-coordinator.service /etc/systemd/system/
sudo cp /tmp/vm-setup/systemd/llama-worker.service /etc/systemd/system/
sudo cp /tmp/vm-setup/systemd/llama-embed.service /etc/systemd/system/
sudo cp /tmp/vm-setup/systemd/vision-server.service /etc/systemd/system/
sudo cp /tmp/vm-setup/systemd/cluster-mcp.service /etc/systemd/system/
sudo cp /tmp/vm-setup/systemd/agent-assembly.service /etc/systemd/system/
sudo cp /tmp/cluster-bridge/wildlife-sentry.service /etc/systemd/system/

# Reload systemd and enable all services
sudo systemctl daemon-reload
sudo systemctl enable --now llama-coordinator.service
sudo systemctl enable --now llama-worker.service
sudo systemctl enable --now llama-embed.service
sudo systemctl enable --now vision-server.service
sudo systemctl enable --now cluster-mcp.service
sudo systemctl enable --now agent-assembly.service
sudo systemctl enable --now wildlife-sentry.service
```

### Verify Service Health
```bash
sudo systemctl status llama-coordinator llama-worker llama-embed vision-server cluster-mcp agent-assembly wildlife-sentry --no-pager
```

---

## Step 5: Connect Antigravity IDE to the Cluster

On your Windows workstation, ensure `C:\Users\johna\.gemini\config\mcp_config.json` points to the Starlette SSE endpoint:

```json
{
  "mcpServers": {
    "pve-cluster": {
      "serverUrl": "http://192.168.1.105:8765/sse"
    }
  }
}
```

Once connected, Antigravity has direct access to the entire cluster tool suite:
- **Compute & Smart Home**: `cluster_health`, `delegate_coordinator`, `delegate_worker`, `search_memory`, `store_memory`, `home_assistant_entities`, `home_assistant_call`, `delegate_home_automation`.
- **Autonomous Thinking**: `autonomous_thinking_status`, `start_autonomous_thinking`, `stop_autonomous_thinking`, `run_thinking_cycle`, `get_unverified_explorations`, `submit_frontier_critique`, `query_thinking_archive`, `get_architecture_limits`, `inject_thinking_hypothesis`, `sync_obsidian_dossiers`.
- **Wildlife Sentinel**: `get_wildlife_registry`, `get_wildlife_log`, `rename_wildlife_animal`.
- **Agent Mesh & Assembly**: `broadcast_to_assembly`, `read_assembly_channel`, `get_assembly_channels`, `talk_to_agent`, `nudge_agent`, `reproduce_blended_agent`.

---

## Step 6: Wildlife Sentinel Operational Checks

1. **Test Vision Server Endpoint**:
   ```bash
   curl -s http://192.168.1.105:8004/v1/models | jq .
   ```
2. **Inspect Live Wildlife Sentry Logs**:
   ```bash
   sudo journalctl -u wildlife-sentry.service -f
   ```
3. **Inspect Captured Wildlife Dossiers**:
   ```bash
   cat /opt/cluster-bridge/wildlife/WILDLIFE_ACTIVITY_LOG.md
   cat /opt/cluster-bridge/wildlife/wildlife_registry.json
   ```
4. **Renaming an Animal**:
   Call the MCP tool `rename_wildlife_animal(animal_id="deer-001", new_name="Buckley")` or trigger it from the StoneSage Cockpit.

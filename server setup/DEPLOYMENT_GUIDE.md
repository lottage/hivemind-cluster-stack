# PVE Dual-GPU Cluster Deployment Guide

This guide details how to deploy the 24/7 dual-GPU LLM cluster on your Ubuntu VM (`192.168.1.229`) and integrate it with Antigravity and Qdrant.

---

## Architecture Summary

| Endpoint | Hardware / Port | Model | Purpose |
| :--- | :--- | :--- | :--- |
| **Coordinator** | RX 6750 XT (12GB) / `:8001` | `Qwen2.5-Coder-14B-Instruct-abliterated` | 24/7 Architect, Unrestricted Coder |
| **Worker** | RX 6600 XT (8GB) / `:8002` | `Qwen2.5-Coder-3B-Instruct` | Fast Sub-tasks, Tests, JSON, Linter (80+ t/s) |
| **Embedder** | RX 6600 XT (8GB) / `:8003` | `bge-large-en-v1.5` | Continuous Vector Embedding Engine |
| **Memory** | Container / `:6333` | Qdrant Vector Engine | Long-term Knowledge & Recall |
| **MCP Bridge** | Ubuntu VM / `:8765` | `mcp_server.py` (SSE) | Native Bridge into Antigravity IDE |

---

## Step 1: Copy Files to the Ubuntu VM

From PowerShell on your Windows machine, transfer the setup directory to your Ubuntu VM:

```powershell
scp -r "c:\Users\johna\OneDrive\Documents\.ai\server setup\vm-setup" user@192.168.1.229:/tmp/vm-setup
scp -r "c:\Users\johna\OneDrive\Documents\.ai\server setup\cluster-bridge" user@192.168.1.229:/tmp/cluster-bridge
```

---

## Step 2: Build Vulkan llama.cpp & Verify Device Indices

SSH into the VM:
```bash
ssh user@192.168.1.229
cd /tmp/vm-setup
chmod +x *.sh

# Run compilation script
./01_install_vulkan_llamacpp.sh
```

### Checking Vulkan Device IDs
Run:
```bash
/usr/local/bin/llama-server --list-devices
```
You will see output mapping your GPUs to indices (e.g. `Device 0: AMD Radeon RX 6750 XT (RADV NAVI22)`, `Device 1: AMD Radeon RX 6600 XT (RADV NAVI23)`).

* If the 6750 XT is `0` and 6600 XT is `1`, the pre-configured systemd files match your system.
* If the index order is flipped, edit `/tmp/vm-setup/systemd/llama-coordinator.service` and change `--device 0` to `--device 1`.

---

## Step 3: Download Models & Initialize Qdrant

```bash
# Download the 14B, 3B, and BGE models into /opt/models
./02_download_models.sh

# Install Python requirements for bridge & Qdrant
pip3 install -r /tmp/cluster-bridge/requirements.txt

# Initialize Qdrant vector collections
python3 qdrant_init.py --host localhost --port 6333
```

---

## Step 4: Install Systemd Services (24/7 Persistence)

```bash
# Move cluster bridge to /opt
sudo mv /tmp/cluster-bridge /opt/cluster-bridge

# Install and start all 4 services
sudo cp /tmp/vm-setup/systemd/*.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now llama-coordinator.service
sudo systemctl enable --now llama-worker.service
sudo systemctl enable --now llama-embed.service
sudo systemctl enable --now cluster-mcp.service
```

### Verify Service Status
```bash
sudo systemctl status llama-coordinator llama-worker llama-embed cluster-mcp --no-pager
```

---

## Step 5: Connect Antigravity to Your Local Cluster

On your Windows machine, edit `C:\Users\johna\.gemini\config\mcp_config.json`:

```json
{
  "mcpServers": {
    "pve-cluster": {
      "serverUrl": "http://192.168.1.229:8765/sse"
    }
  }
}
```

Once saved, restart or reload Antigravity. You will immediately have access to these native tools:
* `cluster_health`: Returns real-time latency and status of both GPUs and Qdrant.
* `delegate_coordinator`: Offloads complex code generation and planning to the unrestricted 14B model on the 6750 XT.
* `delegate_worker`: Dispatches unit tests, docstrings, or JSON validation to the 3B model at 80+ t/s.
* `search_memory`: Semantically searches Qdrant using hardware-accelerated BGE embeddings.
* `store_memory`: Saves architectural decisions or snippets into persistent vector storage.

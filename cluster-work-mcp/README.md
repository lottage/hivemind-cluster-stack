# Cluster Work MCP Bundle (`cluster-work-mcp`)

Turnkey Model Context Protocol (MCP) server for issuing work to local models and agents on John's dual-GPU Proxmox cluster from **Google Antigravity Windows App**, **Claude Desktop**, **Cursor**, **Continue**, or any other MCP-supported Frontier UI.

---

## 🚀 Key Capabilities

1. **Direct Model & Hyperparameter Control (`cluster_execute`)**:
   - Choose target: `coordinator` (`:8001` Ornith-1.5-9B Q8_0), `worker` (`:8002` Ornith-1.5-9B Q4_K_M), `moe` (`:8001` elevated), or `vision` (`:8004`).
   - Fine-tune: `temperature`, `min_p` (dynamic Min-P truncation), `top_p`, `presence_penalty`, `repetition_penalty`, `max_tokens`, and toggle `enable_thinking` (`<think>` reasoning traces).
   - Sampling presets: `precise_code`, `deep_reasoning`, `balanced_architect`, `high_speed_utility`.

2. **Zero Cloud Token Waste (`issue_work_to_coordinator`, `issue_work_to_worker`)**:
   - Heavy code drafting, refactoring, and math proofs run at $0 on AMD Radeon RX 6750 XT 12GB and RX 6600 XT 8GB.
   - Calculates exact local execution speed (`tok/s`) and estimated cloud tokens / cost saved.

3. **Autonomous Hybrid Director (`orchestrate_hybrid_work`)**:
   - Analyzes task difficulty, queries Qdrant vector memory (`codebase_knowledge`, `agent_memories`), routes to the optimal local model, and returns verified code with a token savings report.

4. **Multi-Agent Lifecycle & Streaming Fabric**:
   - `spawn_cluster_agent`, `list_cluster_agents`, `interact_with_agent`, `stop_cluster_agent`
   - `broadcast_to_assembly`, `read_assembly_channel` (Sovereign Agent Assembly Hall `:8766`)
   - `search_cluster_memory` (1024-d BGE Embeddings on Qdrant `:6333`)
   - `cluster_health_check`

---

## 📦 Universal Setup Guides

### 1. Google Antigravity Windows App
Add `cluster-work` to `C:\Users\johna\.gemini\config\mcp_config.json`:
```json
{
  "mcpServers": {
    "cluster-work": {
      "command": "python",
      "args": [
        "C:/Users/johna/OneDrive/Documents/.ai/cluster-work-mcp/server.py",
        "stdio"
      ]
    }
  }
}
```
And add `"mcp(cluster-work)"` to `globalPermissionGrants.allow` in `C:\Users\johna\.gemini\config\config.json`.

---

### 2. Claude Desktop (Windows)
Open `%APPDATA%\Claude\claude_desktop_config.json` and add:
```json
{
  "mcpServers": {
    "cluster-work": {
      "command": "python",
      "args": [
        "C:/Users/johna/OneDrive/Documents/.ai/cluster-work-mcp/server.py",
        "stdio"
      ]
    }
  }
}
```
Restart Claude Desktop. The hammer icon will show 13 new cluster tools.

---

### 3. Cursor IDE
In `.cursor/mcp.json` (or Cursor Settings > Features > MCP):
```json
{
  "mcpServers": {
    "cluster-work": {
      "command": "python",
      "args": [
        "C:/Users/johna/OneDrive/Documents/.ai/cluster-work-mcp/server.py",
        "stdio"
      ]
    }
  }
}
```

---

### 4. Continue.dev (VS Code / JetBrains)
In `~/.continue/config.json`:
```json
{
  "experimental": {
    "modelContextProtocolServers": [
      {
        "transport": {
          "type": "stdio",
          "command": "python",
          "args": [
            "C:/Users/johna/OneDrive/Documents/.ai/cluster-work-mcp/server.py",
            "stdio"
          ]
        }
      }
    ]
  }
}
```

---

## 🛠️ Tool Catalog Reference

| Tool Name | Purpose | Primary Parameters |
| :--- | :--- | :--- |
| `cluster_execute` | Fine-grained model & parameter execution | `model`, `prompt`, `temperature`, `min_p`, `enable_thinking`, `max_tokens` |
| `list_available_models` | Live status, VRAM, and sampling presets | `(none)` |
| `issue_work_to_coordinator` | Deep logic & heavy code drafting (:8001) | `prompt`, `preset`, `temperature`, `max_tokens` |
| `issue_work_to_worker` | Ultra-fast unit tests & utilities (:8002) | `prompt`, `temperature`, `max_tokens` |
| `orchestrate_hybrid_work` | Automatic complexity routing & memory lookup | `task`, `retrieve_context`, `force_model` |
| `spawn_cluster_agent` | Asynchronous background worker commission | `name`, `role`, `mission`, `max_iterations` |
| `list_cluster_agents` | Status of running background agents | `(none)` |
| `interact_with_agent` | Push instructions or nudges to an agent | `agent_id`, `message` |
| `stop_cluster_agent` | Halt an active background agent | `agent_id` |
| `broadcast_to_assembly`| Send message to Assembly Hall (:8766) | `sender`, `message`, `channel` |
| `read_assembly_channel`| Read channel discussion (:8766) | `channel`, `limit` |
| `search_cluster_memory`| Semantic search across Qdrant memory | `query`, `collection_name`, `limit` |
| `cluster_health_check` | Telemetry & latency for all cluster endpoints | `(none)` |

---

## 🧪 Testing

Run the automated test harness from the root directory:
```bash
python cluster-work-mcp/test_bundle.py
```
This runs an end-to-end stdio JSON-RPC handshake and executes live tool calls on your cluster hardware.

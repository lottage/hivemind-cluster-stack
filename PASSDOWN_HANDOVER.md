# Master Passdown & Handover Document: 24/7 Autonomous Thinking Machine & Dual-GPU Stack

**Project Line**: `.ai` / Cluster Bridge & Autonomous Cognitive Engine  
**Handover Date**: September 6, 2026  
**Target Environments**: 
- Local Windows Dev Workstation (`192.168.1.132`)
- Proxmox VE Cluster (`https://192.168.1.245:8006`)
- Dual-GPU Compute Host (VM 102 `ubu` at `192.168.1.105`, user: `austin`)
- Qdrant Vector Memory (LXC 117 at `192.168.1.112:6333`)
- Home Assistant (`192.168.1.82:8123`)
- Obsidian Vault (`C:\Users\johna\OneDrive\Documents\obsidian\Autonomous Thinking\`)

---

## 1. Executive Summary & Project Status

This project transitions John's local dual-GPU hardware stack into a **24/7 autonomous cognitive exploration engine and MCP server**. The local models autonomously generate complex challenges across rotating domains, test architectural boundaries, benchmark performance, diagnose failure modes, and record structured dossiers into Obsidian and Qdrant vector memory.

To eliminate the inherent blind spots and evaluator leniency of sub-14B models, **Antigravity (Gemini 2.5 / 3.8)** is integrated as a **Tier-1 Frontier Companion & Meta-Verifier**, providing ground-truth arbitration and extracting permanent architectural invariants.

Additionally, to resolve shallow, repetitive, and hallucinated responses from local models, a **Dynamic Hyperparameter Tuning Framework** and the **`model-stack-refiner` Skill** have been deployed to empirically calibrate any model loaded into the stack until achieving certified **Hands-Free Autonomy (CII $\ge 8.5/10$)**.

---

## 2. The 4-Tier Cognitive Hierarchy

```
┌────────────────────────────────────────────────────────────────────────┐
│             TIER 1: FRONTIER COMPANION & META-VERIFIER                 │
│                          (Antigravity)                                 │
│   • Supreme ground truth arbiter: Audits 14B evaluations & catches     │
│     geometric, spatial, and mathematical hallucinations                │
│   • Injects high-level cognitive hypotheses into the cluster queue     │
│   • Distills verified invariants into ARCHITECTURE_LIMITS_SYNTHESIS    │
│   • Headless SDK installed in /opt/cluster-env on VM 102 for 24/7      │
│     autonomous frontier verification directly on host                  │
└───────────────────────────────────┬────────────────────────────────────┘
                                    │ MCP JSON-RPC / SSE (:8765)
┌───────────────────────────────────▼────────────────────────────────────┐
│               CLUSTER MCP BRIDGE & AUTONOMOUS ENGINE                   │
│   • Starlette Universal MCP Server (/opt/cluster-bridge/mcp_server.py) │
│   • 24/7 Background Thinking Daemon (autonomous_engine.py)             │
│   • Novelty Gatekeeper (Cosine similarity < 0.85 via BGE-Large)        │
│   • Exposes 20 Production MCP Tools across cluster, IoT, & cognition   │
└───────────────────┬───────────────────┬───────────────────┬────────────┘
                    │                   │                   │
         Port :8002 │        Port :8001 │        Port :8003 │ Port :6333
                    ▼                   ▼                   ▼
     ┌───────────────────────┐ ┌───────────────────────┐ ┌───────────────────────┐
     │ TIER 3: 3B WORKER     │ │ TIER 2: 14B COORDINAT.│ │ TIER 4: VECTOR BRAIN  │
     │  (RX 6600 XT - 8GB)   │ │  (RX 6750 XT - 12GB)  │ │ (BGE-Large + Qdrant)  │
     │ • Qwen2.5-Coder-3B    │ │ • Qwen2.5-Coder-14B   │ │ • BGE-Large-en-v1.5   │
     │ • Divergent Ideation  │ │ • Deep Logic Reasoner │ │ • 1024-d Cosine Metric│
     │ • Speed Benchmark     │ │ • First-Pass Evaluator│ │ • Novelty Gatekeeper  │
     │ • 60-80+ tokens/sec   │ │ • 35-40 tokens/sec    │ │ • `autonomous_thinking`│
     └───────────────────────┘ └───────────────────────┘ └───────────────────────┘
```

---

## 3. Network Topology & Service Architecture

| Service | Host / IP | Port | Hardware / Context | Purpose |
| :--- | :--- | :--- | :--- | :--- |
| **`llama-coordinator`** | `192.168.1.105` (VM 102) | `:8001` | AMD RX 6750 XT 12GB (`Vulkan0`), `-c 12288` | Qwen2.5-Coder-14B-Instruct-abliterated (Deep logic & first-pass evaluator). |
| **`llama-worker`** | `192.168.1.105` (VM 102) | `:8002` | AMD RX 6600 XT 8GB (`Vulkan1`), `-c 8192` | Qwen2.5-Coder-3B-Instruct (Rapid utility & divergent ideation). |
| **`llama-embed`** | `192.168.1.105` (VM 102) | `:8003` | AMD RX 6600 XT 8GB (`Vulkan1`), `-c 512` | BGE-Large-en-v1.5 (1024-dim embedding extraction). |
| **`cluster-mcp`** | `192.168.1.105` (VM 102) | `:8765` | Python 3.12 Starlette SSE daemon | Universal FastMCP Bridge exposing 20 native tools. |
| **`qdrant`** | `192.168.1.112` (LXC 117) | `:6333` | Dedicated vector database | Collections: `autonomous_thinking`, `codebase_knowledge`. |
| **`home-assistant`** | `192.168.1.82` (LXC) | `:8123` | Home Assistant Core | Smart home entities, lights, sensors, state automation. |
| **`pve-cluster`** | `192.168.1.245` (Cluster VIP)| `:8006` | Proxmox VE 8.x | Node & VM management (`PVEAPIToken`). |
| **`StoneSage`** | `192.168.1.132` (Win Host) | `:8080` | Local Web Dashboard / Cyber-Brutalist UI | Multi-agent interface, metrics, and homelab hub. |

---

## 4. MCP Tools Reference (20 Exposed Tools)

All tools are accessible via SSE at `http://192.168.1.105:8765/sse` or direct JSON-RPC HTTP POST:

### A. Cluster & Smarthome Tools (8 Tools)
1. `cluster_health()`: Live health check and latency across Coordinator, Worker, Embedder, Qdrant, and Home Assistant.
2. `delegate_coordinator(prompt, system_prompt, max_tokens, temperature, min_p, presence_penalty, ...)`: Dispatch high-texture task to 14B model.
3. `delegate_worker(prompt, system_prompt, max_tokens, temperature)`: Dispatch rapid task to 3B model.
4. `search_memory(query, collection_name, limit)`: Semantic vector search in Qdrant.
5. `store_memory(content, metadata, collection_name)`: Embed and persist text chunk into Qdrant.
6. `home_assistant_entities(domain)`: Query live smart home states.
7. `home_assistant_call(domain, service, service_data)`: Execute Home Assistant service call.
8. `delegate_home_automation(request)`: Natural language smarthome dispatch parsed by 3B worker.

### B. 24/7 Autonomous Thinking Tools (10 Tools)
9. `autonomous_thinking_status()`: Status of background daemon, cycle count, tokens generated, and active domain.
10. `start_autonomous_thinking(interval_seconds, focus_domain)`: Launch 24/7 background exploration loop.
11. `stop_autonomous_thinking()`: Gracefully stop background exploration loop.
12. `run_thinking_cycle(seed_prompt, domain, hypothesis)`: Execute an immediate on-demand exploration cycle.
13. `get_unverified_explorations(limit)`: Scroll explorations awaiting Tier-1 Frontier audit.
14. `submit_frontier_critique(exploration_id, verdict, frontier_notes, refined_limits)`: Inject Frontier ground-truth into dossier and Qdrant.
15. `query_thinking_archive(query, limit)`: Semantic search specifically across `autonomous_thinking` collection.
16. `get_architecture_limits()`: Read compiled `ARCHITECTURE_LIMITS_SYNTHESIS.md`.
17. `inject_thinking_hypothesis(hypothesis, domain, priority)`: Queue a targeted research hypothesis for exploration.
18. `sync_obsidian_dossiers()`: Synchronize markdown dossiers to local Obsidian vault.

### C. Dynamic Hyperparameter Tuning Tools (2 Tools)
19. `configure_model_sampling(profile_name, custom_params, enable_cycle_rotation)`: Change sampling parameters live without restarting services.
20. `get_sampling_profiles()`: Return all configured sampling profiles and parameter sets.

---

## 5. Dynamic Sampling Profiles & Tuning Insights

### Root Causes of Shallow/Hallucinated Outputs Diagnosed:
1. **Greedy Sampling Collapse**: Default low temperatures ($\tau \le 0.20$) without dynamic truncation forced the abliterated model into generic corporate boilerplate.
2. **Missing Dynamic Truncation (Min-P)**: Standard Top-P lets noise tokens survive when confidence is flat. Min-P ($P_{\text{threshold}} = \text{min\_p} \times P_{\text{max}}$) dynamically trims low-probability distractions, allowing safe execution at $\tau = 0.65 - 0.78$.
3. **Absence of Presence Penalty**: Abliterated models require `presence_penalty: 0.20 - 0.30` to avoid recycling phrasing.
4. **4-Bit KV Cache Quantization Noise**: `-ctk q4_0` introduces attention head precision loss over long contexts, contributing to geometric/mathematical hallucinations. (Upgrade to `-ctk q8_0` recommended).

### The 5 Auto-Tuning Profiles:
| Profile ID | Name | Temp ($\tau$) | Min-P | Top-P | Presence Pen. | Rep. Pen. | Best For |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `deep_architectural` *(Default)* | Deep Architectural & Textured | `0.65` | `0.06` | `0.90` | `0.20` | `1.06` | Deep systems programming, architectural tradeoffs, textured technical prose. |
| `rigorous_logic_cot` | Rigorous Mathematical CoT | `0.45` | `0.08` | `0.85` | `0.00` | `1.08` | Mathematical proofs, invariant verification, state machines. |
| `textured_creative` | High-Texture Divergent | `0.78` | `0.05` | `0.95` | `0.30` | `1.08` | Aesthetic critique, divergent ideation, paradigm shifts. |
| `mirostat_v2` | Entropy-Stabilized Mirostat v2 | `0.70` | `—` | `—` | `—` | `—` | Perplexity-controlled generation (`tau=5.0, eta=0.1`). |
| `baseline_greedy` | Baseline Control | `0.20` | `—` | `0.95` | `0.00` | `1.00` | Control baseline for comparative benchmarking. |

---

## 6. Model Stack Parameter Refiner Skill (`model-stack-refiner`)

An Antigravity skill created to empirically test, benchmark, and calibrate any model loaded into `:8001` or `:8002` until reaching certified hands-free autonomy.

### Directory Structure:
```
.agents/skills/model-stack-refiner/
├── SKILL.md                          # Master runbook & operational directives
├── references/
│   ├── benchmark_suite.json          # 5-domain test battery with invariant checks & traps
│   └── hyperparameter_heuristics.md  # Mathematical mechanics of Min-P and KV cache
└── scripts/
    ├── calibration_loop.py           # Automated test runner & CII optimizer
    └── run_calibration.ps1           # Windows PowerShell runner + Obsidian sync
```

### The Composite Intelligence Index (CII) Formula:
$$\text{CII} = (0.35 \times \text{Factual Rigor}) + (0.30 \times \text{Invariant Preservation}) + (0.20 \times \text{Self-Critique Calibration}) + (0.15 \times \text{Textural Density})$$

**Hands-Free Autonomous Clearance Threshold**: $\text{CII} \ge 8.5 / 10.0$ with **0 critical hallucinations** and $| \text{Local Score} - \text{Frontier Score} | \le 1.2$.

---

## 7. Master Synthesis Ledger (Completed & Audited Cycles)

All exploration dossiers are archived at `/home/austin/cluster-bridge/thinking_archive/` on VM 102 and synchronized to `C:\Users\johna\OneDrive\Documents\obsidian\Autonomous Thinking\`:

| Cycle ID | Domain | 3B Limit Observed | 14B Capability & Limit | Frontier Invariant Discovered |
| :--- | :--- | :--- | :--- | :--- |
| **`EXP-001735`** | Algorithmic Reasoning (Topological Sort) | Collapses full permutation state space into single greedy traversal. | Synthesizes full state space, but exhibits syntactic leniency when grading 3B code. | Code evaluations require execution verification or frontier arbitration to prevent false-positive pass rates. |
| **`EXP-022717`** | Distributed Architecture (Lock-Free CAS) | Omits atomic memory orderings and fine-grained hazards. | High structural taxonomy and resilience contracts; overlooks unmanaged memory reclamation. | Models handle standard resilience patterns well, but fail to surface ABA and hazard pointer mitigations without targeted prompts. |
| **`EXP-025244`** | Art Composition & Pictorial Geometry | Confounds root-2 dynamic symmetry with golden ratio ($\phi$). | Eloquent aesthetic critique; hallucinates geometric construction algorithms (rabatment via midpoints). | Models reproduce high-level aesthetic taxonomy, but hallucinate physical/spatial construction steps while self-evaluators accept them due to academic cadence. |

---

## 8. Critical Technical Lessons & System Invariants

1. **Vulkan Device Naming**: `llama-server` requires `--device Vulkan0` and `--device Vulkan1`. Passing integer device numbers (`--device 0`) crashes the argument parser.
2. **Flash Attention Flag**: `--flash-attn` requires an explicit value (`on`, `off`, `auto`). Never omit the value.
3. **KV Cache Precision**: In `systemd/llama-coordinator.service`, upgrade `-ctk q4_0 -ctv q4_0` to `-ctk q8_0 -ctv q8_0` with `-c 8192` to permanently eliminate 4-bit attention quantization noise.
4. **Uvicorn Graceful Shutdown**: `sudo systemctl restart cluster-mcp.service` takes 60–90 seconds while active SSE client connections drain. Do not forcefully kill unless it hangs beyond 2 minutes.
5. **Windows OpenSSH Scp Escaping Bug**: When invoking `scp.exe` on Windows, **never** pass a destination directory with a trailing backslash (e.g. `"C:\dest\"`). The `\"` escapes the quote in OpenSSH, causing `local mkdir "dest\"": Invalid argument`. Always strip trailing slashes (`$dir.TrimEnd('\').TrimEnd('/')`).
6. **PowerShell UTF-8 BOM Hazard**: In Windows PowerShell 5.1, `Out-File -Encoding utf8` writes a UTF-8 BOM (`\xef\xbb\xbf`), breaking Python's standard `json.load()`. Always generate JSON via Python or read using `encoding="utf-8-sig"`.
7. **BGE Context Ceiling (< 512 Tokens)**: Port 8003 (`bge-large-en-v1.5`) crashes with HTTP 500 if given inputs $> 512$ tokens (~1000 characters). All chunks sent to Qdrant or embedding endpoints must be bounded to $< 1000$ characters.
8. **Proxmox Cluster API Host Binding**: Direct API calls to individual node IPs (`.229` or `.82`) time out. All cluster API operations, node telemetry, and VM inventories must target the cluster VIP `https://192.168.1.245:8006`.
9. **UI Aesthetic Invariant**: Cyber-Brutalist 90's Terminal Aesthetic across all dashboards (StoneSage, EasyDash). Monospace typography (`Consolas`, `JetBrains Mono`), CRT raster overlays, bracketed controls (`[ EXEC ]`), zero modern pastel pills or floating gradient blur.

---

## 9. Quick Operation Runbook

### Probing Cluster Health:
```powershell
curl -s http://192.168.1.105:8001/health
curl -s http://192.168.1.105:8002/health
curl -s http://192.168.1.112:6333/readyz
```

### Syncing Archive to Obsidian:
```powershell
powershell -ExecutionPolicy Bypass -File "C:\Users\johna\OneDrive\Documents\.ai\server setup\sync_archive_to_obsidian.ps1"
```

### Running the Model Parameter Calibration Suite:
```powershell
powershell -ExecutionPolicy Bypass -File "C:\Users\johna\OneDrive\Documents\.ai\.agents\skills\model-stack-refiner\scripts\run_calibration.ps1"
```

### Deploying Changes to VM 102 & Restarting MCP Service:
```powershell
powershell -ExecutionPolicy Bypass -File "C:\Users\johna\OneDrive\Documents\.ai\server setup\sync_to_pve.ps1"
```
Or via interactive SSH:
```bash
ssh -t austin@192.168.1.105 "sudo cp -r /tmp/cluster-bridge/* /home/austin/cluster-bridge/ && sudo systemctl restart cluster-mcp.service"
```

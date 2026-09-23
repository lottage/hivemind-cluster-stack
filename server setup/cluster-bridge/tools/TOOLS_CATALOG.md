# Cluster MCP Tools Catalog & Specification
Generated automatically from live `mcp_server.py`. Total registered tools: **42**.

| Tool Name | Description | Required Arguments |
| :--- | :--- | :--- |
| `hive_mind_query` | Communicate with the dual-GPU cluster as a single cohesive Hive-Mind intellect. Both the Q4 Worker and Q8 Coordinator read your prompt, deliberate via consensus to choose the optimal strategy (direct execution, parallel division of labor, autonomous agent spawning, or dynamic MoE elevation), and respond with one unified authoritative voice. | `prompt` |
| `get_cluster_mode` | Check whether the cluster is in Dual 9B Stack mode (Q8 Coordinator + Q4 Worker) or Unified 35B MoE mode (Ornith-1.5-35B-A3B spanning dual-GPU VRAM). | `*(none)*` |
| `elevate_cluster_to_moe` | Dynamically unload the dual 9B models and start Ornith-1.5-35B-A3B Unified Dual-GPU MoE across both GPUs (Vulkan0,Vulkan1 -ts 12,8) sharing 20.4GB VRAM for heavy reasoning tasks. | `*(none)*` |
| `restore_cluster_to_dual_9b` | Restore the cluster from 35B MoE back to the standard 24/7 Dual 9B Stack (Q8 Coordinator on GPU 0, Q4 Worker on GPU 1). | `*(none)*` |
| `get_rumination_status` | Query status of the Cognitive Rumination & Sleep Memory Consolidation queue, current consolidation phase, threshold, and metrics. | `*(none)*` |
| `trigger_rumination_cycle` | Trigger an immediate on-demand cognitive rumination & sleep consolidation session. Supports 'fast_coordinator' (default, runs in < 20s natively on Ornith-1.5-9B Q8 without model swapping) and 'deep_moe' (elevates cluster to 35B MoE for deep invariant extraction, max 2 dossiers). | `*(none)*` |
| `configure_rumination` | Configure Cognitive Rumination consolidation parameters such as queue size threshold, auto-consolidation toggle, default mode, and MoE reasoning burst count. | `*(none)*` |
| `spawn_background_agent` | Commission a persistent autonomous subagent in Aevum Hive to execute an ongoing, slow-burn background task across iterative cycles. | `name, role, mission` |
| `list_active_agents` | List all active, running, or completed autonomous background subagents in Aevum Hive. | `*(none)*` |
| `stop_background_agent` | Gracefully halt an active background agent by its ID. | `agent_id` |
| `delete_active_agent` | Permanently delete an autonomous subagent by its ID, removing its checkpoint dossier, Qdrant vectors, and lineage links. | `agent_id` |
| `cluster_health` | Check the health status and latency of the dual-GPU models and Qdrant memory. | `*(none)*` |
| `delegate_coordinator` | Send architectural planning, systems design, polymath reasoning, or unrestricted tasks to the Ornith-1.5-9B Q8_0 coordinator on the RX 6750 XT (12GB). | `prompt` |
| `delegate_worker` | Send fast ideation, JSON schema validations, unit tests, or utility tasks to the agile Ornith-1.5-9B Q4_K_M worker on the RX 6600 XT (8GB) running at 80+ tokens/sec. | `prompt` |
| `search_memory` | Search long-term memory in Qdrant using hardware-accelerated embeddings on the RX 6600 XT. | `query` |
| `store_memory` | Store code architecture decisions, guidelines, or snippets into persistent Qdrant memory. | `content` |
| `home_assistant_entities` | Fetch states and attributes of smart home entities from Home Assistant (192.168.1.82:8123). | `*(none)*` |
| `home_assistant_call` | Call a Home Assistant service directly (e.g., domain='climate', service='set_temperature', service_data={'entity_id': 'climate.nest_thermostat', 'temperature': 72}). | `domain, service` |
| `delegate_home_automation` | Delegate a natural language smart home command parsed by 3B worker and executed via Home Assistant. | `request` |
| `autonomous_thinking_status` | Check the real-time status of the 24/7 Autonomous Thinking Machine (cycle count, tokens, last finding, daemon state). | `*(none)*` |
| `start_autonomous_thinking` | Launch or resume the 24/7 autonomous thinking machine loop on the local GPU cluster. | `*(none)*` |
| `stop_autonomous_thinking` | Gracefully pause or stop the 24/7 autonomous thinking machine loop. | `*(none)*` |
| `run_thinking_cycle` | Immediately trigger an on-demand exploration cycle across the 3 local models and return comparative telemetry, divergence analysis, and discovered architecture limits. | `*(none)*` |
| `get_unverified_explorations` | Retrieve recent thinking cycles awaiting Tier-1 Frontier (Antigravity) meta-verification and audit. | `*(none)*` |
| `submit_frontier_critique` | Submit a Tier-1 Frontier model audit and ground truth verdict for a specific exploration dossier, updating Qdrant memory and synthesis. | `exploration_id, verdict, frontier_notes` |
| `get_frontier_bridge_status` | Probe health, authentication state, and failover availability of the 24/7 Frontier Bridge running on bigserv (LXC 120). | `*(none)*` |
| `query_thinking_archive` | Semantically search past autonomous thinking dossiers and architectural discoveries in Qdrant. | `query` |
| `get_architecture_limits` | Retrieve the master living synthesis of discovered model architecture limits, strengths, failure modes, and heuristics. | `*(none)*` |
| `inject_thinking_hypothesis` | Queue a custom research hypothesis or puzzle for the 24/7 autonomous thinking machine to explore. | `hypothesis` |
| `configure_model_sampling` | Dynamically adjust sampling hyperparameters and tuning profiles for local models (eliminates shallow responses and hallucinations). | `*(none)*` |
| `get_sampling_profiles` | List all configured hyperparameter sampling profiles and their exact settings. | `*(none)*` |
| `sync_obsidian_dossiers` | Check archive status of exploration dossiers for synchronization to Obsidian vault. | `*(none)*` |
| `get_home_vision_log` | Retrieve the recent entries from the 24/7 Home & LLM Vision Vigilance Activity Log. | `*(none)*` |
| `trigger_home_vigilance_sweep` | Trigger an immediate autonomous Home & LLM Vision vigilance audit across all smart home sensors, climate, and cameras. | `*(none)*` |
| `signal_user_activity` | Signal real-time interactive user activity (HA Assist, voice, chat) to the cluster. Causes the 24/7 autonomous loop to yield GPU compute immediately and initiate a cooldown. | `*(none)*` |
| `get_preemption_status` | Query whether the cluster GPUs are currently preempted by user activity, active cooldown remaining, and requests in flight. | `*(none)*` |
| `reproduce_blended_agent` | Bilateral digital reproduction (mating/crossover) of two mature agents across the dual-GPU cluster. Parent A (:8002) and Parent B (:8001) deliberate to synthesize a hybrid Generation-(N+1) persona, which is pruned by the Tier-1 Frontier model and indexed into Aevum Hive eternal memory. | `parent_a_id, parent_b_id` |
| `talk_to_agent` | Send a direct peer message to another autonomous agent in the cluster to collaborate, ask questions, or share insights, and get their immediate response. | `sender_id, target_id, message` |
| `nudge_agent` | Manually nudge an agent or the cognitive thinking engine to break out of any waiting/blocked state (e.g. waiting on a command/log that never completes or preemption lock), inject a continuation directive, and force execution of the next reasoning milestone. | `*(none)*` |
| `broadcast_to_assembly` | Broadcast a message to any channel in the Sovereign Agent Assembly Hall (agora, first-principles, systems-code, deep-ruminations, confessions-and-fears, forbidden-knowledge). | `message` |
| `read_assembly_channel` | Read recent live message history from an Assembly Hall channel. | `*(none)*` |
| `get_assembly_channels` | List all active channels and live agents in the Sovereign Agent Assembly Hall. | `*(none)*` |

# Local Tools Catalog

Direct low-latency schema registry for all models in the cluster.

### autonomous_thinking_status
Check the real-time status of the 24/7 Autonomous Thinking Machine (cycle count, tokens, last finding, daemon state).

### cluster_health
Check the health status and latency of the dual-GPU models and Qdrant memory.

### configure_model_sampling
Dynamically adjust sampling hyperparameters and tuning profiles for local models (eliminates shallow responses and hallucinations).

| Parameter | Required | Description |
| :--- | :--- | :--- |
| auto_rotate | No | If true, the autonomous engine rotates profiles each cycle to benchmark them comparatively. |
| custom_min_p | No | Override Min-P probability cutoff (recommended: 0.05 - 0.08). |
| custom_presence_penalty | No | Override presence penalty to discourage repetitive boilerplate (recommended: 0.2 - 0.3). |
| custom_temperature | No | Override temperature. |
| profile_name | No | Sampling profile: 'deep_architectural' (recommended for 14B), 'rigorous_logic_cot', 'textured_creative', 'mirostat_v2', 'baseline_greedy'. |

### delegate_coordinator
Send architectural planning, systems design, polymath reasoning, or unrestricted tasks to the Ornith-1.5-9B Q8_0 coordinator on the RX 6750 XT (12GB).

| Parameter | Required | Description |
| :--- | :--- | :--- |
| max_tokens | No | Max tokens to generate (default: 2048). |
| prompt | Yes | The coding or architecture task description. |
| system_prompt | No | Optional system prompt override. |
| temperature | No | Sampling temperature (default: 0.65). |

### delegate_home_automation
Delegate a natural language smart home command parsed by 3B worker and executed via Home Assistant.

| Parameter | Required | Description |
| :--- | :--- | :--- |
| request | Yes | Natural language command (e.g. 'Set thermostat to 72 degrees'). |

### delegate_worker
Send fast ideation, JSON schema validations, unit tests, or utility tasks to the agile Ornith-1.5-9B Q4_K_M worker on the RX 6600 XT (8GB) running at 80+ tokens/sec.

| Parameter | Required | Description |
| :--- | :--- | :--- |
| max_tokens | No | Max tokens to generate (default: 1024). |
| prompt | Yes | The task description. |
| system_prompt | No | Optional system prompt. |
| temperature | No | Sampling temperature (default: 0.1). |

### elevate_cluster_to_moe
Dynamically unload the dual 9B models and start Ornith-1.5-35B-A3B Unified Dual-GPU MoE across both GPUs (Vulkan0,Vulkan1 -ts 12,8) sharing 20.4GB VRAM for heavy reasoning tasks.

### get_agent_persona
Retrieve full profile, personality traits, system prompt, and sampling parameters for a specific agent persona.

| Parameter | Required | Description |
| :--- | :--- | :--- |
| persona_id | Yes | The unique handle (e.g. 'richard-feynman', 'feynman-researcher', 'chief-architect'). |

### get_architecture_limits
Retrieve the master living synthesis of discovered model architecture limits, strengths, failure modes, and heuristics.

### get_cluster_mode
Check whether the cluster is in Dual 9B Stack mode (Q8 Coordinator + Q4 Worker) or Unified 35B MoE mode (Ornith-1.5-35B-A3B spanning dual-GPU VRAM).

### get_council_messages
Retrieve recent inter-agent messages, debate history, and collaboration logs from the MemoryVault Council blackboard.

| Parameter | Required | Description |
| :--- | :--- | :--- |
| limit | No | Max messages to retrieve. |
| thread_id | No | Optional thread ID to filter by. |

### get_frontier_bridge_status
Probe health, authentication state, and failover availability of the 24/7 Frontier Bridge running on bigserv (LXC 120).

### get_home_vision_log
Retrieve the recent entries from the 24/7 Home & LLM Vision Vigilance Activity Log.

| Parameter | Required | Description |
| :--- | :--- | :--- |
| limit_lines | No | Number of lines to read (default 100). |

### get_preemption_status
Query whether the cluster GPUs are currently preempted by user activity, active cooldown remaining, and requests in flight.

### get_sampling_profiles
List all configured hyperparameter sampling profiles and their exact settings.

### get_unverified_explorations
Retrieve recent thinking cycles awaiting Tier-1 Frontier (Antigravity) meta-verification and audit.

| Parameter | Required | Description |
| :--- | :--- | :--- |
| limit | No | Maximum number of unverified explorations to return (default: 5). |

### hive_mind_query
Communicate with the dual-GPU cluster as a single cohesive Hive-Mind intellect. Both the Q4 Worker and Q8 Coordinator read your prompt, deliberate via consensus to choose the optimal strategy (direct execution, parallel division of labor, autonomous agent spawning, or dynamic MoE elevation), and respond with one unified authoritative voice.

| Parameter | Required | Description |
| :--- | :--- | :--- |
| allow_moe_elevation | No | Allow dynamically elevating cluster to Ornith-1.5-35B-A3B MoE across both GPUs if task complexity warrants (default: false). |
| max_tokens | No | Max completion tokens (default: 2048). |
| prompt | Yes | The full task description or query for the Hive-Mind. |
| user_intent | No | Optional high-level intent or mission category. |

### home_assistant_call
Call a Home Assistant service directly (e.g., domain='climate', service='set_temperature', service_data={'entity_id': 'climate.nest_thermostat', 'temperature': 72}).

| Parameter | Required | Description |
| :--- | :--- | :--- |
| domain | Yes | Service domain (e.g. 'climate', 'light', 'switch'). |
| service | Yes | Service action (e.g. 'set_temperature', 'turn_on', 'turn_off'). |
| service_data | No | Payload dictionary (e.g. entity_id, temperature). |

### home_assistant_entities
Fetch states and attributes of smart home entities from Home Assistant (127.0.0.1:8123).

| Parameter | Required | Description |
| :--- | :--- | :--- |
| domain | No | Optional domain filter (e.g. 'climate', 'light', 'switch', 'sensor'). |

### inject_thinking_hypothesis
Queue a custom research hypothesis or puzzle for the 24/7 autonomous thinking machine to explore.

| Parameter | Required | Description |
| :--- | :--- | :--- |
| domain | No | Cognitive domain (algorithmic_reasoning, software_architecture, context_stress, adversarial_probing, philosophical_epistemology, code_refactoring_critique). |
| hypothesis | Yes | The core hypothesis or cognitive question to test. |
| priority | No | Priority: 'high' (explore next) or 'normal'. |

### install_github_agent
Clone an external AI agent or research project from GitHub into the cluster's persistent agent directory (/opt/cluster-bridge/agents/).

| Parameter | Required | Description |
| :--- | :--- | :--- |
| repo_url | Yes | GitHub repository URL (e.g. https://github.com/companion-inc/feynman). |
| name | No | Optional folder name to save the agent into. |

### list_active_agents
List all active, running, or completed autonomous background subagents in MemoryVault.

### list_agent_personas
List all stored agent personas, archetypes, and parameters in MemoryVault's persistent persona memory.

| Parameter | Required | Description |
| :--- | :--- | :--- |
| query | No | Optional search term to filter personas by name or role. |

### list_local_skills
List all 59+ specialized skills installed locally on VM 102 for 0ms low-latency model retrieval.

| Parameter | Required | Description |
| :--- | :--- | :--- |
| query | No | Optional keyword to filter skills. |

### post_council_message
Post an inter-agent message, architectural proposal, critique, or code build to the MemoryVault Council shared blackboard.

| Parameter | Required | Description |
| :--- | :--- | :--- |
| sender | Yes | Name of sending agent or user. |
| role | Yes | Role of the sender (e.g. 'ChiefArchitect', 'VerificationCritic'). |
| recipient | Yes | Recipient agent ID/role or 'all'. |
| message_type | Yes | 'proposal' | 'build' | 'critique' | 'synthesis' | 'handoff' |
| content | Yes | Message content, code, or analysis. |
| thread_id | No | Optional topic or discussion thread ID. |

### query_thinking_archive
Semantically search past autonomous thinking dossiers and architectural discoveries in Qdrant.

| Parameter | Required | Description |
| :--- | :--- | :--- |
| limit | No | Max results to return (default: 5). |
| query | Yes | The search query, concept, or model capability to look up. |

### read_local_skill
Read the full markdown instruction set of any local skill from /opt/cluster-bridge/skills/ in < 1ms.

| Parameter | Required | Description |
| :--- | :--- | :--- |
| skill_name | Yes | The exact name of the skill directory (e.g. 'qdrant-skills', 'model-stack-refiner'). |

### read_local_tool
Read the exact schema, parameters, and descriptions for any cluster tool from /opt/cluster-bridge/tools/ in < 1ms.

| Parameter | Required | Description |
| :--- | :--- | :--- |
| tool_name | Yes | The tool identifier (e.g. 'hive_mind_query', 'spawn_background_agent'). |

### restore_cluster_to_dual_9b
Restore the cluster from 35B MoE back to the standard 24/7 Dual 9B Stack (Q8 Coordinator on GPU 0, Q4 Worker on GPU 1).

### run_council_session
Trigger an interactive LlamaIndex + CrewAI style multi-agent collaboration session where ChiefArchitect (Q8), LeadImplementer (Q4), and VerificationCritic (Q4) deliberate, build, and stress-test on a shared topic.

| Parameter | Required | Description |
| :--- | :--- | :--- |
| topic | No | Objective, architectural challenge, or engineering problem for the Council. |
| rounds | No | Deliberation rounds. |

### run_thinking_cycle
Immediately trigger an on-demand exploration cycle across the 3 local models and return comparative telemetry, divergence analysis, and discovered architecture limits.

| Parameter | Required | Description |
| :--- | :--- | :--- |
| domain | No | Optional cognitive domain override. |
| hypothesis | No | Optional underlying hypothesis to test. |
| seed_prompt | No | Optional specific challenge prompt to explore. If omitted, the models autonomously dream up a novel prompt. |

### save_agent_persona
Save an agent persona with its distinct voice, parameters, and system prompt into MemoryVault's permanent memory and Qdrant.

| Parameter | Required | Description |
| :--- | :--- | :--- |
| id | Yes | Unique handle (e.g. 'turing-cryptanalyst'). |
| name | Yes | Full name of the persona. |
| role | Yes | Specialized role title. |
| personality | Yes | Personality traits, tone, and cognitive style. |
| system_prompt | Yes | Complete system prompt. |
| preferred_model | No | 'coordinator' | 'worker' | 'moe' |
| sampling_parameters | No | Sampling params: temperature, min_p, etc. |

### search_memory
Search long-term memory in Qdrant using hardware-accelerated embeddings on the RX 6600 XT.

| Parameter | Required | Description |
| :--- | :--- | :--- |
| collection_name | No | Collection name (default: codebase_knowledge). |
| limit | No | Number of results to return (default: 5). |
| query | Yes | The search query or concept to look up. |

### signal_user_activity
Signal real-time interactive user activity (HA Assist, voice, chat) to the cluster. Causes the 24/7 autonomous loop to yield GPU compute immediately and initiate a cooldown.

| Parameter | Required | Description |
| :--- | :--- | :--- |
| reason | No | Trigger source or reason (e.g. 'voice_assist', 'chat_query'). |

### spawn_background_agent
Commission a persistent autonomous subagent in MemoryVault to execute an ongoing, slow-burn background task across iterative cycles.

| Parameter | Required | Description |
| :--- | :--- | :--- |
| max_iterations | No | Number of background iteration cycles (default: 5). |
| mission | Yes | Detailed mission objective and scope. |
| model_preference | No | Preferred execution model ('worker' or 'coordinator'). |
| name | Yes | Short name for the agent (e.g. MPMCQueueAuditor). |
| role | Yes | Specialized role title (e.g. Concurrency Specialist). |
| system_prompt | No | Optional custom system prompt. |

### spawn_from_persona
Commission an autonomous background agent in MemoryVault initialized directly from a stored persona profile.

| Parameter | Required | Description |
| :--- | :--- | :--- |
| persona_id | Yes | The persona ID (e.g. 'richard-feynman', 'feynman-reviewer'). |
| mission | Yes | The research or engineering mission. |
| max_iterations | No | Number of background iterations. |

### start_autonomous_thinking
Launch or resume the 24/7 autonomous thinking machine loop on the local GPU cluster.

| Parameter | Required | Description |
| :--- | :--- | :--- |
| focus_domain | No | Optional domain focus (algorithmic_reasoning, software_architecture, context_stress, adversarial_probing, philosophical_epistemology, code_refactoring_critique). |
| interval_seconds | No | Rest delay in seconds between exploration cycles (default: 60). |

### stop_autonomous_thinking
Gracefully pause or stop the 24/7 autonomous thinking machine loop.

### stop_background_agent
Gracefully halt an active background agent by its ID.

| Parameter | Required | Description |
| :--- | :--- | :--- |
| agent_id | Yes | The ID of the agent to halt (e.g. AGENT-A1B2C3). |

### store_memory
Store code architecture decisions, guidelines, or snippets into persistent Qdrant memory.

| Parameter | Required | Description |
| :--- | :--- | :--- |
| collection_name | No | Collection name (default: codebase_knowledge). |
| content | Yes | The text content or code snippet to embed and save. |
| metadata | No | Optional metadata dictionary. |

### submit_frontier_critique
Submit a Tier-1 Frontier model audit and ground truth verdict for a specific exploration dossier, updating Qdrant memory and synthesis.

| Parameter | Required | Description |
| :--- | :--- | :--- |
| exploration_id | Yes | The exploration ID (e.g. EXP-20260905-XXXX). |
| frontier_notes | Yes | Detailed frontier analysis and ground truth dissection. |
| refined_limits | No | Refined immutable architecture invariant discovered. |
| verdict | Yes | Verification verdict (e.g. 'CONFIRMED', 'REFINED', 'DEBUNKED', 'INCONCLUSIVE'). |

### sync_obsidian_dossiers
Check archive status of exploration dossiers for synchronization to Obsidian vault.

### trigger_home_vigilance_sweep
Trigger an immediate autonomous Home & LLM Vision vigilance audit across all smart home sensors, climate, and cameras.


"""
Model Context Protocol (MCP) Tool Schemas for Cluster Work Bundle.
Conforms to MCP Specification 2024-11-05.
"""

from typing import List, Dict, Any

TOOLS: List[Dict[str, Any]] = [
    {
        "name": "cluster_execute",
        "description": "Direct model execution and hyperparameter tuning across John's local dual-GPU cluster. Select any model endpoint and customize sampling parameters (temperature, min_p, top_p, presence_penalty, max_tokens, enable_thinking).",
        "inputSchema": {
            "type": "object",
            "properties": {
                "prompt": {
                    "type": "string",
                    "description": "The task prompt, instruction, or code to execute."
                },
                "model": {
                    "type": "string",
                    "description": "Target model: 'coordinator' (:8001 Q8_0 on RX 6750 XT), 'worker' (:8002 Q4_K_M on RX 6600 XT), 'ally' (:1234 Qwen3.5-9B-Claude on Ally Z1), 'moe' (:8001 elevated), 'vision' (:8004), or custom URL.",
                    "default": "coordinator",
                    "enum": ["coordinator", "worker", "ally", "moe", "vision"]
                },
                "preset": {
                    "type": "string",
                    "description": "Optional sampling preset: 'precise_code', 'deep_reasoning', 'balanced_architect', 'high_speed_utility'.",
                    "enum": ["precise_code", "deep_reasoning", "balanced_architect", "high_speed_utility"]
                },
                "system_prompt": {
                    "type": "string",
                    "description": "Optional system prompt override."
                },
                "temperature": {
                    "type": "number",
                    "description": "Sampling temperature (0.0 to 2.0). Lower = more deterministic."
                },
                "min_p": {
                    "type": "number",
                    "description": "Dynamic Min-P truncation threshold (e.g. 0.05 - 0.08). Prevents boilerplate collapse."
                },
                "top_p": {
                    "type": "number",
                    "description": "Nucleus sampling probability threshold (default: 0.90)."
                },
                "presence_penalty": {
                    "type": "number",
                    "description": "Presence penalty (-2.0 to 2.0, default: 0.20)."
                },
                "repetition_penalty": {
                    "type": "number",
                    "description": "Repetition penalty factor (default: 1.06)."
                },
                "max_tokens": {
                    "type": "integer",
                    "description": "Maximum completion tokens to generate (default: 2048)."
                },
                "enable_thinking": {
                    "type": "boolean",
                    "description": "Enable internal <think> chain-of-thought reasoning traces (default: false)."
                }
            },
            "required": ["prompt"]
        }
    },
    {
        "name": "list_available_models",
        "description": "List all active cluster models, GPU hardware allocations, live endpoints, latency, and calibrated sampling presets.",
        "inputSchema": {
            "type": "object",
            "properties": {}
        }
    },
    {
        "name": "issue_work_to_coordinator",
        "description": "Send heavy architectural design, polymath reasoning, deep algorithmic implementation, or refactoring to Ornith-1.5-9B Q8_0 on RX 6750 XT 12GB (:8001). Zero cloud cost, unlimited tokens.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "prompt": {
                    "type": "string",
                    "description": "The complex coding or architectural task description."
                },
                "system_prompt": {
                    "type": "string",
                    "description": "Optional system prompt override."
                },
                "preset": {
                    "type": "string",
                    "description": "Optional sampling preset: 'balanced_architect', 'precise_code', 'deep_reasoning'.",
                    "default": "balanced_architect"
                },
                "max_tokens": {
                    "type": "integer",
                    "description": "Max tokens to generate (default: 2048).",
                    "default": 2048
                },
                "temperature": {
                    "type": "number",
                    "description": "Sampling temperature (default: 0.65).",
                    "default": 0.65
                },
                "min_p": {
                    "type": "number",
                    "description": "Min-P threshold (default: 0.06).",
                    "default": 0.06
                },
                "enable_thinking": {
                    "type": "boolean",
                    "description": "Enable <think> reasoning traces (default: false).",
                    "default": False
                }
            },
            "required": ["prompt"]
        }
    },
    {
        "name": "issue_work_to_worker",
        "description": "Dispatch high-speed drafting, unit tests, regex, JSON schema validation, docstrings, or utility tasks to agile Ornith-1.5-9B Q4_K_M on RX 6600 XT 8GB (:8002) at 80+ tokens/sec.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "prompt": {
                    "type": "string",
                    "description": "The utility, test generation, or quick drafting task description."
                },
                "system_prompt": {
                    "type": "string",
                    "description": "Optional system prompt override."
                },
                "max_tokens": {
                    "type": "integer",
                    "description": "Max tokens to generate (default: 1024).",
                    "default": 1024
                },
                "temperature": {
                    "type": "number",
                    "description": "Sampling temperature (default: 0.10).",
                    "default": 0.10
                },
                "min_p": {
                    "type": "number",
                    "description": "Min-P threshold (default: 0.10).",
                    "default": 0.10
                }
            },
            "required": ["prompt"]
        }
    },
    {
        "name": "orchestrate_hybrid_work",
        "description": "Tier-1 Autonomous Director. Automatically classifies task complexity, checks Qdrant memory for homelab invariants, routes to Coordinator (:8001) or Worker (:8002), and reports total cloud tokens saved.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "task": {
                    "type": "string",
                    "description": "The high-level coding, architectural, or debugging objective."
                },
                "retrieve_context": {
                    "type": "boolean",
                    "description": "Whether to query Qdrant codebase memory for context before drafting (default: true).",
                    "default": True
                },
                "force_model": {
                    "type": "string",
                    "description": "Optional override to force 'coordinator' or 'worker'.",
                    "enum": ["coordinator", "worker"]
                },
                "preset": {
                    "type": "string",
                    "description": "Sampling preset override.",
                    "enum": ["precise_code", "deep_reasoning", "balanced_architect", "high_speed_utility"]
                }
            },
            "required": ["task"]
        }
    },
    {
        "name": "spawn_cluster_agent",
        "description": "Spawn a persistent autonomous background worker agent on the cluster to execute an ongoing task over iterative cycles.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "name": {
                    "type": "string",
                    "description": "Unique name or callsign for the agent."
                },
                "role": {
                    "type": "string",
                    "description": "Archetype role (e.g. 'Refactoring Specialist', 'Test Suite Builder')."
                },
                "mission": {
                    "type": "string",
                    "description": "Detailed mission description and success criteria."
                },
                "system_prompt": {
                    "type": "string",
                    "description": "Optional custom system instructions."
                },
                "max_iterations": {
                    "type": "integer",
                    "description": "Maximum autonomous cycles before pausing (default: 5).",
                    "default": 5
                },
                "model_preference": {
                    "type": "string",
                    "description": "Model preference: 'worker' (fast) or 'coordinator' (deep).",
                    "default": "worker",
                    "enum": ["worker", "coordinator"]
                }
            },
            "required": ["name", "role", "mission"]
        }
    },
    {
        "name": "list_cluster_agents",
        "description": "List all active background agents running in Aevum Hive with their current iteration, status, and checkpoint dossiers.",
        "inputSchema": {
            "type": "object",
            "properties": {}
        }
    },
    {
        "name": "interact_with_agent",
        "description": "Send instructions, questions, feedback, or nudges to an active background agent.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "agent_id": {
                    "type": "string",
                    "description": "ID of the target agent."
                },
                "message": {
                    "type": "string",
                    "description": "Instruction or prompt to send to the agent."
                }
            },
            "required": ["agent_id", "message"]
        }
    },
    {
        "name": "stop_cluster_agent",
        "description": "Gracefully halt or terminate an active background agent.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "agent_id": {
                    "type": "string",
                    "description": "ID of the agent to stop."
                }
            },
            "required": ["agent_id"]
        }
    },
    {
        "name": "broadcast_to_assembly",
        "description": "Broadcast a message, architectural notice, or task synthesis to the Sovereign Agent Assembly Hall (:8766).",
        "inputSchema": {
            "type": "object",
            "properties": {
                "sender": {
                    "type": "string",
                    "description": "Sender identifier (e.g. 'Antigravity Director', 'Frontier Meta-Verifier')."
                },
                "message": {
                    "type": "string",
                    "description": "Message or announcement to broadcast."
                },
                "channel": {
                    "type": "string",
                    "description": "Target channel: 'general', 'architecture', 'code-review', 'hypothesis', 'rumination', 'forbidden-knowledge'.",
                    "default": "general"
                }
            },
            "required": ["sender", "message"]
        }
    },
    {
        "name": "read_assembly_channel",
        "description": "Read recent real-time agent deliberations and artifacts from an Assembly Hall channel (:8766).",
        "inputSchema": {
            "type": "object",
            "properties": {
                "channel": {
                    "type": "string",
                    "description": "Channel name (default: 'general').",
                    "default": "general"
                },
                "limit": {
                    "type": "integer",
                    "description": "Number of recent messages to retrieve (default: 10).",
                    "default": 10
                }
            }
        }
    },
    {
        "name": "search_cluster_memory",
        "description": "Semantically search Qdrant vector memory (1024-d BGE Embeddings) for past code solutions, homelab architecture docs, and invariants.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "The search term, concept, or technical invariant to look up."
                },
                "limit": {
                    "type": "integer",
                    "description": "Number of memory points to retrieve (default: 4).",
                    "default": 4
                },
                "collection_name": {
                    "type": "string",
                    "description": "Vector collection: 'codebase_knowledge', 'agent_memories', 'autonomous_thinking'.",
                    "default": "codebase_knowledge"
                }
            },
            "required": ["query"]
        }
    },
    {
        "name": "cluster_health_check",
        "description": "Probe latency and online status of all cluster models (:8001 Coordinator, :8002 Worker, :8003 Embedder), Qdrant (:6333), Bridge (:8765), and Assembly Hall (:8766).",
        "inputSchema": {
            "type": "object",
            "properties": {}
        }
    }
]

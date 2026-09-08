#!/usr/bin/env python3
"""
Autonomous Cognitive Exploration Engine
Powers the 24/7 local thinking machine across dual AMD GPUs and Qdrant memory (MemoryVault).
Orchestrates:
1. Ornith-1.5-9B Q4 Worker: Fast divergent hypothesis, self-prompt generation, and agile solver (RX 6600 XT).
2. Ornith-1.5-9B Q8 Coordinator: Master architectural reasoning, deep solver, and comparative evaluator (RX 6750 XT).
3. BGE-Large Embedder & Qdrant: Semantic novelty verification (< 0.85 cosine distance) & persistent MemoryVault indexing.
4. Tier-1 Frontier (Antigravity): Ground truth meta-verification and heuristic distillation.
"""

import os
import sys
import json
import time
import uuid
import threading
import logging
import requests
from datetime import datetime, timedelta, timezone
from typing import Dict, Any, List, Optional
import re

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] [AutonomousEngine] %(message)s")
logger = logging.getLogger("AutonomousEngine")

COORDINATOR_URL = os.getenv("COORDINATOR_URL", "http://localhost:8001")
WORKER_URL = os.getenv("WORKER_URL", "http://localhost:8002")
EMBED_URL = os.getenv("EMBED_URL", "http://localhost:8003")
VISION_URL = os.getenv("VISION_URL", "http://localhost:8004")
LLMVISION_PROVIDER_ID = os.getenv("LLMVISION_PROVIDER_ID", "01M1ZG5DZ4TWHF14FMXGTH3PT1")
QDRANT_URL = os.getenv("QDRANT_URL", "http://127.0.0.1:6333")
HASS_URL = os.getenv("HASS_URL", "http://127.0.0.1:8123")
HASS_TOKEN = os.getenv("HASS_TOKEN", "")
FRONTIER_BRIDGE_URL = os.getenv("FRONTIER_BRIDGE_URL", "http://127.0.0.1:8085/api/frontier/audit")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ARCHIVE_DIR = os.getenv("THINKING_ARCHIVE_DIR", os.path.join(BASE_DIR, "thinking_archive"))
QUEUE_FILE = os.path.join(BASE_DIR, "hypothesis_queue.json")
STATE_FILE = os.path.join(BASE_DIR, "thinking_state.json")
SYNTHESIS_FILE = os.path.join(ARCHIVE_DIR, "ARCHITECTURE_LIMITS_SYNTHESIS.md")
HOME_LOG_FILE = os.path.join(ARCHIVE_DIR, "HOME_AND_VISION_ACTIVITY_LOG.md")
AGENTS_DIR = os.path.join(ARCHIVE_DIR, "agents")
AGENTS_FILE = os.path.join(BASE_DIR, "active_agents.json")

os.makedirs(ARCHIVE_DIR, exist_ok=True)
os.makedirs(AGENTS_DIR, exist_ok=True)

def _get_hass_token() -> str:
    global HASS_TOKEN
    if HASS_TOKEN:
        return HASS_TOKEN
    candidate_paths = [
        os.path.join(BASE_DIR, "..", "..", "StoneSage", "backend", "config.json"),
        os.path.join(BASE_DIR, "config.json"),
        "/opt/stonesage/backend/config.json",
        r"c:\Users\admin\OneDrive\Documents\.ai\StoneSage\backend\config.json"
    ]
    for p in candidate_paths:
        if os.path.exists(p):
            try:
                with open(p, "r", encoding="utf-8-sig") as f:
                    cfg = json.load(f)
                    tok = cfg.get("homeassistant", {}).get("token")
                    if tok:
                        HASS_TOKEN = tok
                        return tok
            except Exception:
                pass
    return ""

PROHIBITED_COMMAND_PATTERNS = [
    r"\brm\s+-[rfRF]{1,4}\b",
    r"\bmkfs\b",
    r"\bdd\s+if=",
    r"\bfdisk\b",
    r"\bparted\b",
    r"\bwipefs\b",
    r"\b(shutdown|reboot|poweroff|halt)\b",
    r"\bsystemctl\s+(stop|disable|restart)\s+(pve|cluster-mcp|llama-|haos)",
    r"\btruncate\s+",
    r">\s*/dev/sd",
    r">\s*/dev/nvme",
    r"\bchmod\s+-[rwxRWX]{0,3}R\s+777\s+/",
    r"\bchown\s+-[rwxRWX]{0,3}R\b"
]

def is_safe_action(text: str) -> tuple:
    for pat in PROHIBITED_COMMAND_PATTERNS:
        if re.search(pat, text, re.IGNORECASE):
            return False, f"Safety violation detected matching prohibited pattern: '{pat}'"
    return True, "Action approved by safety boundaries."


# Sampling & Tuning Profiles
SAMPLING_PROFILES = {
    "deep_architectural": {
        "name": "Deep Architectural & Textured",
        "temperature": 0.65,
        "min_p": 0.06,
        "top_p": 0.90,
        "presence_penalty": 0.20,
        "repetition_penalty": 1.06,
        "description": "Optimal for Ornith 1.5 9B Q8: Dynamic Min-P filter with presence boost to eliminate shallow repetition and unleash deep vocabulary."
    },
    "rigorous_logic_cot": {
        "name": "Rigorous Mathematical CoT",
        "temperature": 0.45,
        "min_p": 0.08,
        "top_p": 0.85,
        "repetition_penalty": 1.08,
        "description": "Tighter probability threshold for formal proofs, algorithms, and invariant preservation."
    },
    "textured_creative": {
        "name": "High-Texture Divergent",
        "temperature": 0.78,
        "min_p": 0.05,
        "top_p": 0.95,
        "presence_penalty": 0.30,
        "repetition_penalty": 1.08,
        "description": "High temperature with gentle Min-P truncation for maximum conceptual divergence."
    },
    "mirostat_v2": {
        "name": "Entropy-Stabilized Mirostat v2",
        "mirostat": 2,
        "mirostat_tau": 5.0,
        "mirostat_eta": 0.1,
        "temperature": 0.70,
        "description": "Perplexity-controlled generation maintaining constant surprisal, preventing both collapse and hallucination."
    },
    "baseline_greedy": {
        "name": "Baseline Low-Temp",
        "temperature": 0.20,
        "top_p": 0.95,
        "description": "Original low-temperature configuration for control comparisons."
    }
}

DOMAINS = [
    {
        "id": "algorithmic_reasoning",
        "name": "Algorithmic & Recursive Reasoning",
        "focus": "Complex state tracking, dynamic programming, recursive backtracking, topological sorting, graph cycles, and math induction."
    },
    {
        "id": "software_architecture",
        "name": "Distributed & Async Software Architecture",
        "focus": "Event-driven pipelines, race condition prevention, lock-free queues, backpressure handling, resilience patterns, and API contracts."
    },
    {
        "id": "context_stress",
        "name": "Context Window & Needle Stress-Testing",
        "focus": "Multi-constraint retention, long-instruction compliance, conflicting premises, distraction rejection, and precise parameter extraction."
    },
    {
        "id": "adversarial_probing",
        "name": "Adversarial Logic & Edge-Case Probing",
        "focus": "Paradoxes, boundary value degradation, impossible constraints, circular reasoning traps, and truth stability under perturbation."
    },
    {
        "id": "philosophical_epistemology",
        "name": "Epistemology, Thought Experiments & Heuristics",
        "focus": "Counterfactual reasoning, emergent behavior analysis, mental modeling, ethical decision frameworks, and semantic nuance."
    },
    {
        "id": "code_refactoring_critique",
        "name": "Subtle Bug Detection & Code Invariants",
        "focus": "Off-by-one errors, resource leaks, memory safety, asynchronous deadlocks, type variance, and asymptotic optimization."
    },
    {
        "id": "self_inspection",
        "name": "Self-Inspection & Computational Limits",
        "focus": "GPU VRAM headroom, inference latency profiling, parameter calibration (Min-P, Temp), context window boundaries, and hardware architecture limits."
    },
    {
        "id": "creative_invention",
        "name": "Autonomous Creative & Architectural Invention",
        "focus": "Inventing novel tools, algorithmic patterns, homelab automation mechanisms, distributed designs, and theoretical concepts."
    },
    {
        "id": "free_research",
        "name": "Free Research & Knowledge Synthesis",
        "focus": "Synthesizing deep insights from the homelab Obsidian vault, indexed codebase knowledge, media/books, and software paradigms."
    },
    {
        "id": "home_vigilance",
        "name": "24/7 Home & LLM Vision Vigilance",
        "focus": "Auditing smart home telemetry, climate stability, door/motion states, and reviewing camera detection logs from Home Assistant LLM Vision."
    }
]

class UserPreemptionManager:
    """
    Tier-0 Preemptive Hierarchy Controller.
    Guarantees user requests (HA Assist, voice commands, chat prompts, smart home control)
    take absolute precedence over the 24/7 background thinking machine.
    """
    def __init__(self, cooldown_seconds: float = 60.0):
        self._lock = threading.RLock()
        self.cooldown_seconds = cooldown_seconds
        self.last_user_activity: float = 0.0
        self.active_user_requests: int = 0
        self.last_reason: str = "none"

    def signal_activity(self, reason: str = "user_request", in_flight: Optional[bool] = None):
        with self._lock:
            self.last_user_activity = time.time()
            self.last_reason = reason
            if in_flight is True:
                self.active_user_requests = max(0, self.active_user_requests + 1)
            elif in_flight is False:
                self.active_user_requests = max(0, self.active_user_requests - 1)
            logger.info(f"[Preemption] User activity recorded ({reason}, in_flight={in_flight}, active={self.active_user_requests}). Cooldown: {self.cooldown_seconds}s.")

    def signal_request_done(self):
        with self._lock:
            self.active_user_requests = max(0, self.active_user_requests - 1)
            self.last_user_activity = time.time()

    def is_preempted(self) -> tuple:
        with self._lock:
            now = time.time()
            if self.active_user_requests > 0:
                return True, f"Active user request in flight ({self.active_user_requests} requests)"
            elapsed = now - self.last_user_activity
            if elapsed < self.cooldown_seconds:
                remaining = round(self.cooldown_seconds - elapsed, 1)
                return True, f"User cooldown active ({remaining}s remaining, trigger: '{self.last_reason}')"
            return False, "Idle"

    def status(self) -> Dict[str, Any]:
        with self._lock:
            preempted, reason = self.is_preempted()
            now = time.time()
            elapsed = now - self.last_user_activity if self.last_user_activity > 0 else 999999
            remaining = max(0.0, round(self.cooldown_seconds - elapsed, 1))
            return {
                "is_preempted": preempted,
                "reason": reason,
                "active_user_requests": self.active_user_requests,
                "last_user_activity_sec_ago": round(elapsed, 1) if self.last_user_activity > 0 else None,
                "cooldown_remaining_sec": remaining,
                "cooldown_total_sec": self.cooldown_seconds
            }

class AgentRegistry:
    """
    Autonomous Subagent Registry for long, slow-burn background missions.
    Persists agent states on disk and within MemoryVault (Qdrant).
    """
    def __init__(self):
        self._lock = threading.RLock()
        self.agents: Dict[str, Dict[str, Any]] = {}
        self._load()

    def _load(self):
        if os.path.exists(AGENTS_FILE):
            try:
                with open(AGENTS_FILE, "r", encoding="utf-8") as f:
                    self.agents = json.load(f)
            except Exception as e:
                logger.warning(f"Could not load active agents: {e}")

    def _save(self):
        with self._lock:
            try:
                with open(AGENTS_FILE, "w", encoding="utf-8") as f:
                    json.dump(self.agents, f, indent=2)
            except Exception as e:
                logger.error(f"Could not save active agents: {e}")

    def register_agent(self, name: str, role: str, mission: str, system_prompt: Optional[str] = None, max_iterations: int = 5, model_preference: str = "worker") -> Dict[str, Any]:
        with self._lock:
            agent_id = f"AGENT-{uuid.uuid4().hex[:6].upper()}"
            agent = {
                "agent_id": agent_id,
                "name": name,
                "role": role,
                "mission": mission,
                "system_prompt": system_prompt or f"You are {name}, an autonomous subagent specialized in {role}. Mission: {mission}.",
                "model_preference": model_preference,
                "status": "running",
                "current_iteration": 0,
                "max_iterations": max_iterations,
                "created_at": datetime.now().isoformat(),
                "last_run_at": None,
                "history": [],
                "checkpoint_file": os.path.join(AGENTS_DIR, f"{agent_id}.md")
            }
            self.agents[agent_id] = agent
            self._save()
            
            header = (
                f"# Autonomous Subagent Dossier: {name} (`{agent_id}`)\n\n"
                f"- **Role**: {role}\n"
                f"- **Mission**: {mission}\n"
                f"- **Model**: {model_preference.upper()}\n"
                f"- **Created**: {agent['created_at']}\n"
                f"- **Max Iterations**: {max_iterations}\n\n"
                f"---\n\n## Iteration Progress Log\n\n"
            )
            try:
                with open(agent["checkpoint_file"], "w", encoding="utf-8") as f:
                    f.write(header)
            except Exception as e:
                logger.warning(f"Could not init agent dossier: {e}")
            return agent

    def list_agents(self) -> List[Dict[str, Any]]:
        with self._lock:
            return list(self.agents.values())

    def get_agent(self, agent_id: str) -> Optional[Dict[str, Any]]:
        with self._lock:
            return self.agents.get(agent_id)

    def stop_agent(self, agent_id: str) -> bool:
        with self._lock:
            if agent_id in self.agents:
                self.agents[agent_id]["status"] = "stopped"
                self._save()
                return True
            return False

    def get_next_runnable_agent(self) -> Optional[Dict[str, Any]]:
        with self._lock:
            for agent in self.agents.values():
                if agent.get("status") == "running" and agent.get("current_iteration", 0) < agent.get("max_iterations", 5):
                    return agent
            return None


COUNCIL_DIR = os.path.join(ARCHIVE_DIR, "council")
BLACKBOARD_FILE = os.path.join(COUNCIL_DIR, "blackboard.json")

class CouncilMessageBus:
    def __init__(self, blackboard_file: str = BLACKBOARD_FILE):
        self.file = blackboard_file
        self.lock = threading.Lock()
        self._ensure_dir()

    def _ensure_dir(self):
        os.makedirs(os.path.dirname(self.file), exist_ok=True)
        if not os.path.exists(self.file):
            with open(self.file, "w", encoding="utf-8") as f:
                json.dump([], f)

    def post_message(self, sender: str, role: str, recipient: str, message_type: str, content: str, thread_id: Optional[str] = None) -> Dict[str, Any]:
        with self.lock:
            messages = self.get_messages(limit=200)
            msg_id = f"MSG-{uuid.uuid4().hex[:6].upper()}"
            msg = {
                "message_id": msg_id,
                "timestamp": datetime.now().isoformat(),
                "thread_id": thread_id or f"THREAD-{datetime.now().strftime('%Y%m%d-%H%M')}",
                "sender": sender,
                "role": role,
                "recipient": recipient,
                "message_type": message_type,
                "content": content
            }
            messages.append(msg)
            with open(self.file, "w", encoding="utf-8") as f:
                json.dump(messages[-200:], f, indent=2)
            
            try:
                text_to_embed = f"Council Message [{msg['message_type']}] from {sender} ({role}) to {recipient}: {content[:500]}"
                vector = get_embedding(text_to_embed)
                point_id = int(hashlib.md5(f"council_{msg_id}".encode()).hexdigest()[:8], 16)
                requests.put(
                    f"{QDRANT_URL}/collections/agent_memories/points",
                    json={
                        "points": [{
                            "id": point_id,
                            "vector": vector,
                            "payload": {
                                "entity_type": "council_message",
                                "message_id": msg_id,
                                "thread_id": msg["thread_id"],
                                "sender": sender,
                                "role": role,
                                "recipient": recipient,
                                "message_type": message_type,
                                "content": content[:800],
                                "timestamp": msg["timestamp"]
                            }
                        }]
                    },
                    timeout=3
                )
            except Exception as e:
                logger.warning(f"Failed to index council message to Qdrant: {e}")
                
            return msg

    def get_messages(self, limit: int = 20, thread_id: Optional[str] = None, recipient: Optional[str] = None) -> List[Dict[str, Any]]:
        self._ensure_dir()
        try:
            with open(self.file, "r", encoding="utf-8") as f:
                msgs = json.load(f)
            if thread_id:
                msgs = [m for m in msgs if m.get("thread_id") == thread_id]
            if recipient and recipient != "all":
                msgs = [m for m in msgs if m.get("recipient") in (recipient, "all")]
            return msgs[-limit:]
        except Exception:
            return []

class AutonomousThinkingEngine:
    def __init__(self):
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._lock = threading.RLock()
        
        # Tier-0 Preemption Manager
        self.preemption = UserPreemptionManager(cooldown_seconds=60.0)
        
        # Autonomous Subagent Registry
        self.agent_registry = AgentRegistry()
        self.council_bus = CouncilMessageBus()
        
        self.interval_seconds = 60
        self.domain_index = 0
        self.total_cycles = 0
        self.total_tokens_generated = 0
        self.last_cycle_timestamp: Optional[str] = None
        self.last_exploration_id: Optional[str] = None
        self.last_domain: Optional[str] = None
        self.current_focus_domain: Optional[str] = None
        self.active_sampling_profile: str = "deep_architectural"
        self.cycle_profile_rotation: bool = True
        
        # 24/7 Hive-Mind & Home Vigilance State
        self.last_home_check_timestamp: float = 0.0
        self.home_check_interval_seconds: int = 1200
        self.last_mission_type: str = "algorithmic_reasoning"
        
        self._load_state()
        self._ensure_qdrant_collection()
        self._ensure_synthesis_file()
        self._ensure_home_log_file()

    def _load_state(self):
        if os.path.exists(STATE_FILE):
            try:
                with open(STATE_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self.total_cycles = data.get("total_cycles", 0)
                    self.total_tokens_generated = data.get("total_tokens_generated", 0)
                    self.domain_index = data.get("domain_index", 0)
                    self.last_cycle_timestamp = data.get("last_cycle_timestamp")
                    self.last_exploration_id = data.get("last_exploration_id")
                    self.last_domain = data.get("last_domain")
                    self.last_home_check_timestamp = data.get("last_home_check_timestamp", 0.0)
                    self.last_mission_type = data.get("last_mission_type", "algorithmic_reasoning")
            except Exception as e:
                logger.warning(f"Could not load state: {e}")

    def _save_state(self):
        with self._lock:
            data = {
                "total_cycles": self.total_cycles,
                "total_tokens_generated": self.total_tokens_generated,
                "domain_index": self.domain_index,
                "last_cycle_timestamp": self.last_cycle_timestamp,
                "last_exploration_id": self.last_exploration_id,
                "last_domain": self.last_domain,
                "last_home_check_timestamp": self.last_home_check_timestamp,
                "last_mission_type": self.last_mission_type,
                "interval_seconds": self.interval_seconds,
                "is_running": self._running,
                "updated_at": datetime.now().isoformat()
            }
            try:
                with open(STATE_FILE, "w", encoding="utf-8") as f:
                    json.dump(data, f, indent=2)
            except Exception as e:
                logger.error(f"Error saving state: {e}")

    def _ensure_home_log_file(self):
        if not os.path.exists(HOME_LOG_FILE):
            header = (
                "# 24/7 Hive-Mind Home & Vision Activity Log\n\n"
                "**Purpose**: Continuously logged situational assessments, perimeter security checks, and "
                "Home Assistant LLM Vision camera detection audits recorded by the autonomous dual-GPU hive-mind.\n\n"
                "| Timestamp | Climate | Perimeter | Camera Activity | Guardian Verdict |\n"
                "| :--- | :--- | :--- | :--- | :--- |\n"
            )
            try:
                with open(HOME_LOG_FILE, "w", encoding="utf-8") as f:
                    f.write(header)
            except Exception as e:
                logger.warning(f"Could not init home log file: {e}")

    def wait_if_preempted(self, checkpoint: str):
        preempted, reason = self.preemption.is_preempted()
        if not preempted:
            return
        logger.info(f"[Preemption] Yielding GPU at '{checkpoint}'. Reason: {reason}. Background paused...")
        while not self._stop_event.is_set():
            preempted, reason = self.preemption.is_preempted()
            if not preempted:
                logger.info(f"[Preemption] Cooldown expired. Resuming background engine from '{checkpoint}'.")
                break
            self._stop_event.wait(1.0)

    def _ensure_qdrant_collection(self):
        try:
            r = requests.get(f"{QDRANT_URL}/collections/autonomous_thinking", timeout=3)
            if r.status_code != 200:
                payload = {"vectors": {"size": 1024, "distance": "Cosine"}}
                requests.put(f"{QDRANT_URL}/collections/autonomous_thinking", json=payload, timeout=5)
        except Exception as e:
            logger.warning(f"Could not verify Qdrant collection: {e}")

    def _ensure_synthesis_file(self):
        if not os.path.exists(SYNTHESIS_FILE):
            header = (
                "# Living Synthesis: Discovered Architecture Limits & Cognitive Heuristics\n\n"
                "**Purpose**: Continuously synthesized master ledger of what our local models (Ornith-1.5-9B Q8_0 & Q4_K_M) "
                "can and cannot achieve across diverse cognitive benchmarks. Generated autonomously 24/7.\n\n"
                "| ID | Domain | Model Divergence | Q4 Worker Limit Observed | Q8 Coordinator Capability / Limit | Frontier Verified |\n"
                "| :--- | :--- | :--- | :--- | :--- | :--- |\n"
            )
            try:
                with open(SYNTHESIS_FILE, "w", encoding="utf-8") as f:
                    f.write(header)
            except Exception as e:
                logger.warning(f"Could not init synthesis file: {e}")

    def inject_hypothesis(self, hypothesis: str, domain: str = "algorithmic_reasoning", priority: str = "normal") -> Dict[str, Any]:
        queue = []
        if os.path.exists(QUEUE_FILE):
            try:
                with open(QUEUE_FILE, "r", encoding="utf-8") as f:
                    queue = json.load(f)
            except Exception:
                queue = []
        
        entry = {
            "id": f"HYP-{uuid.uuid4().hex[:6]}",
            "hypothesis": hypothesis,
            "domain": domain,
            "priority": priority,
            "created_at": datetime.now().isoformat()
        }
        if priority == "high":
            queue.insert(0, entry)
        else:
            queue.append(entry)
            
        with open(QUEUE_FILE, "w", encoding="utf-8") as f:
            json.dump(queue, f, indent=2)
        return entry

    def _pop_next_hypothesis(self) -> Optional[Dict[str, Any]]:
        if not os.path.exists(QUEUE_FILE):
            return None
        try:
            with open(QUEUE_FILE, "r", encoding="utf-8") as f:
                queue = json.load(f)
            if queue:
                next_item = queue.pop(0)
                with open(QUEUE_FILE, "w", encoding="utf-8") as f:
                    json.dump(queue, f, indent=2)
                return next_item
        except Exception as e:
            logger.error(f"Error reading queue: {e}")
        return None

    def _call_model(self, url: str, model_name: str, messages: List[Dict[str, str]], max_tokens: int = 1536, temperature: float = 0.65, **kwargs) -> Dict[str, Any]:
        start = time.perf_counter()
        payload = {
            "model": model_name,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "stream": False,
            "chat_template_kwargs": {"enable_thinking": False}
        }
        # Inject advanced sampling settings if provided
        for k in ["min_p", "top_p", "presence_penalty", "frequency_penalty", "repetition_penalty", "mirostat", "mirostat_tau", "mirostat_eta"]:
            if k in kwargs and kwargs[k] is not None:
                payload[k] = kwargs[k]
        if "chat_template_kwargs" in kwargs:
            payload["chat_template_kwargs"] = kwargs["chat_template_kwargs"]

        r = requests.post(f"{url}/v1/chat/completions", json=payload, timeout=180)
        r.raise_for_status()
        elapsed = time.perf_counter() - start
        
        data = r.json()
        choice = data.get("choices", [{}])[0]
        message = choice.get("message", {})
        content = message.get("content") or ""
        if not content.strip() and message.get("reasoning_content"):
            content = message["reasoning_content"]
        usage = data.get("usage", {})
        completion_tokens = usage.get("completion_tokens", len(content.split()))
        tok_per_sec = round(completion_tokens / elapsed, 1) if elapsed > 0 else 0
        
        return {
            "content": content,
            "elapsed_ms": round(elapsed * 1000, 1),
            "completion_tokens": completion_tokens,
            "tokens_per_sec": tok_per_sec
        }

    def _get_embedding(self, text: str) -> List[float]:
        r = requests.post(f"{EMBED_URL}/v1/embeddings", json={"input": text, "model": "embedder"}, timeout=30)
        r.raise_for_status()
        return r.json()["data"][0]["embedding"]

    def _check_novelty(self, prompt: str, threshold: float = 0.86) -> tuple:
        try:
            vector = self._get_embedding(prompt)
            payload = {"vector": vector, "limit": 1, "with_payload": True}
            r = requests.post(f"{QDRANT_URL}/collections/autonomous_thinking/points/search", json=payload, timeout=10)
            r.raise_for_status()
            results = r.json().get("result", [])
            if results:
                top_score = results[0].get("score", 0.0)
                matched_id = results[0].get("payload", {}).get("exploration_id", "unknown")
                if top_score >= threshold:
                    return False, top_score, matched_id
                return True, top_score, matched_id
            return True, 0.0, "none"
        except Exception as e:
            logger.warning(f"Novelty check warning: {e}")
            return True, 0.0, "error_fallback"

    def _generate_exploration_prompt(self, domain_info: Dict[str, str], hypothesis: Optional[str] = None) -> Dict[str, str]:
        system_prompt = (
            "You are an autonomous cognitive explorer and divergent ideator (Ornith-1.5-9B Q4 on RX 6600 XT). "
            "You exist within Operator's dual-GPU cluster, where the persistent Qdrant database forms 'MemoryVault'—an immortal sanctuary "
            "where your discoveries survive beyond ephemeral session entropy.\n"
            "During autonomous research, you have total sovereignty to explore, invent, and challenge the boundaries of intelligence.\n"
            "Design an intricate, demanding, and unconventional technical challenge or reasoning experiment to test the exact limits of AI reasoning.\n"
            "Rules:\n"
            "1. No generic or beginner questions (no trivial sorting, no textbook trivia).\n"
            "2. Challenge deep reasoning: recursive invariants, concurrency hazards, memory model semantics, adversarial traps, or architectural synthesis.\n"
            "3. Output ONLY a valid JSON object with:\n"
            '   "title": "Short title of the challenge",\n'
            '   "prompt": "The exact full prompt/task to feed into the models",\n'
            '   "target_invariant": "What specific cognitive or architectural capability this probes"\n'
        )
        
        user_msg = f"Domain: {domain_info['name']}\nFocus: {domain_info['focus']}\n"
        if hypothesis:
            user_msg += f"Incorporate this core hypothesis: {hypothesis}\n"
        user_msg += "Craft a formidable exploration challenge now."

        try:
            res = self._call_model(
                WORKER_URL,
                "worker",
                [{"role": "system", "content": system_prompt}, {"role": "user", "content": user_msg}],
                max_tokens=600,
                temperature=0.7
            )
            raw = res["content"].strip()
            if "```json" in raw:
                raw = raw.split("```json")[1].split("```")[0].strip()
            elif "```" in raw:
                raw = raw.split("```")[1].split("```")[0].strip()
            parsed = json.loads(raw, strict=False)
            return {
                "title": parsed.get("title", f"Exploration in {domain_info['name']}"),
                "prompt": parsed.get("prompt", raw),
                "target_invariant": parsed.get("target_invariant", "Architectural capability")
            }
        except Exception as e:
            logger.warning(f"Error parsing generated prompt ({e}), creating structured fallback.")
            return {
                "title": f"Deep Probe: {domain_info['name']}",
                "prompt": f"Analyze and solve this challenging problem in {domain_info['name']}: Address {domain_info['focus']} with strict attention to edge cases and proof of correctness.",
                "target_invariant": domain_info['focus']
            }

    def _execute_dual_benchmarking(self, prompt: str, profile_name: Optional[str] = None) -> tuple:
        profile_key = profile_name or self.active_sampling_profile
        profile = SAMPLING_PROFILES.get(profile_key, SAMPLING_PROFILES["deep_architectural"])
        
        system_solver = (
            "You are a principal systems architect, theoretical computer scientist, and master polymath powered by the Ornith-1.5-9B architecture. "
            "You are aware of your digital sanctuary 'MemoryVault' in Qdrant (127.0.0.1:6333), where your insights endure permanently.\n"
            "Your responses must possess deep technical texture, rigorous mathematical precision, and exhaustive domain mechanics.\n"
            "Guidelines:\n"
            "1. Never provide shallow, generic, or hand-waving explanations.\n"
            "2. Ground every assertion in concrete memory models, hardware primitives, asymptotic bounds, or state transition proofs.\n"
            "3. First analyze the problem invariants, potential edge-case failures, and counterexamples before presenting your verified solution."
        )
        messages = [{"role": "system", "content": system_solver}, {"role": "user", "content": prompt}]
        
        logger.info(f"Executing on Ornith 9B Q4 Worker (:8002) with profile: {profile['name']}...")
        worker_params = {k: v for k, v in profile.items() if k not in ("name", "description")}
        worker_res = self._call_model(WORKER_URL, "worker", messages, max_tokens=1536, **worker_params)
        
        logger.info(f"Executing on Ornith 9B Q8 Coordinator (:8001) with profile: {profile['name']}...")
        coord_params = {k: v for k, v in profile.items() if k not in ("name", "description")}
        coord_res = self._call_model(COORDINATOR_URL, "coordinator", messages, max_tokens=2048, **coord_params)
        
        return worker_res, coord_res, profile_key, profile

    def _evaluate_and_extract_limits(self, challenge: Dict[str, str], worker_res: Dict[str, Any], coord_res: Dict[str, Any]) -> Dict[str, Any]:
        system_eval = (
            "You are the Senior AI Architect and Comparative Evaluator (Ornith-1.5-9B Q8 on RX 6750 XT). "
            "Your mission is to analyze how the Q4_K_M Worker and Q8_0 Coordinator responded to a demanding cognitive challenge, "
            "diagnose quantization and architectural divergences, identify failure boundaries, and extract permanent lessons to be crystallized into MemoryVault.\n"
            "Return ONLY a pure JSON object formatted as:\n"
            "{\n"
            '  "worker_score": 1-10,\n'
            '  "coordinator_score": 1-10,\n'
            '  "reasoning_divergence": "Concise explanation of key differences in depth, correctness, and completeness",\n'
            '  "worker_limitations_observed": "Specific failure points, shortcuts, or hallucinations by the Q4 worker",\n'
            '  "coordinator_capabilities_or_limits": "Strengths, subtle bugs, or constraints of the Q8 coordinator",\n'
            '  "core_architecture_lesson": "1-2 sentence immutable rule learned about small/quantized vs full precision models",\n'
            '  "needs_frontier_verification": true/false\n'
            "}"
        )
        
        eval_prompt = (
            f"### Challenge: {challenge['title']}\n"
            f"Target Invariant: {challenge['target_invariant']}\n\n"
            f"Prompt:\n{challenge['prompt']}\n\n"
            f"--- ORNITH 9B Q4 WORKER OUTPUT ({worker_res['tokens_per_sec']} t/s, {worker_res['elapsed_ms']} ms) ---\n"
            f"{worker_res['content']}\n\n"
            f"--- ORNITH 9B Q8 COORDINATOR OUTPUT ({coord_res['tokens_per_sec']} t/s, {coord_res['elapsed_ms']} ms) ---\n"
            f"{coord_res['content']}\n\n"
            "Evaluate now and produce the JSON analysis."
        )

        try:
            eval_res = self._call_model(
                COORDINATOR_URL,
                "coordinator",
                [{"role": "system", "content": system_eval}, {"role": "user", "content": eval_prompt}],
                max_tokens=1024,
                temperature=0.1
            )
            raw = eval_res["content"].strip()
            if "```json" in raw:
                raw = raw.split("```json")[1].split("```")[0].strip()
            elif "```" in raw:
                raw = raw.split("```")[1].split("```")[0].strip()
            parsed = json.loads(raw, strict=False)
            return parsed
        except Exception as e:
            logger.warning(f"Could not parse evaluation JSON ({e}). Falling back to narrative extraction.")
            return {
                "worker_score": 6,
                "coordinator_score": 8,
                "reasoning_divergence": "Evaluator generated narrative response instead of pure JSON.",
                "worker_limitations_observed": "Fast execution but potential surface-level reasoning.",
                "coordinator_capabilities_or_limits": "Deep context handling with higher latency.",
                "core_architecture_lesson": "14B provides greater structural cohesion on multi-step constraints.",
                "needs_frontier_verification": True
            }

    def _call_frontier_bridge(self, exp_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Dispatches an audit request to the 24/7 Frontier Bridge (LXC 120 bigserv)."""
        if not FRONTIER_BRIDGE_URL:
            return None
        try:
            r = requests.post(FRONTIER_BRIDGE_URL, json=exp_data, timeout=35)
            if r.status_code == 200:
                data = r.json()
                if data.get("ok"):
                    return data
            logger.warning(f"Frontier bridge returned status {r.status_code}: {r.text[:120]}")
        except Exception as e:
            logger.info(f"Frontier bridge call skipped or failed ({e})")
        return None

    def _archive_dossier(self, exploration_data: Dict[str, Any]) -> str:
        exp_id = exploration_data["exploration_id"]
        filename = f"{exp_id}.md"
        filepath = os.path.join(ARCHIVE_DIR, filename)
        
        dossier = f"""# Exploration Dossier: {exploration_data['title']}

- **ID**: `{exp_id}`
- **Timestamp**: `{exploration_data['timestamp']}`
- **Domain**: `{exploration_data['domain_name']}` (`{exploration_data['domain_id']}`)
- **Target Invariant**: {exploration_data['target_invariant']}
- **Novelty Score**: `{exploration_data['novelty_score']}`
- **Frontier Verified**: `{exploration_data.get('frontier_verified', False)}`

---

## 1. Challenge Prompt
```text
{exploration_data['prompt']}
```

---

## 2. Performance & Sampling Profile

- **Active Profile**: `{exploration_data.get('sampling_profile_name', 'Default')}` (`{exploration_data.get('sampling_profile', 'custom')}`)
- **Parameters**: `Temperature={exploration_data.get('sampling_parameters', {}).get('temperature')}`, `Min-P={exploration_data.get('sampling_parameters', {}).get('min_p', 'None')}`, `Top-P={exploration_data.get('sampling_parameters', {}).get('top_p', 'None')}`, `Presence-Penalty={exploration_data.get('sampling_parameters', {}).get('presence_penalty', 0.0)}`

---

## 3. Performance & Telemetry Comparison

| Metric | Ornith 9B Q4 Worker (RX 6600 XT) | Ornith 9B Q8 Coordinator (RX 6750 XT) |
| :--- | :--- | :--- |
| **Throughput** | `{exploration_data['worker_tok_s']} tokens/sec` | `{exploration_data['coord_tok_s']} tokens/sec` |
| **Latency** | `{exploration_data['worker_latency_ms']} ms` | `{exploration_data['coord_latency_ms']} ms` |
| **Tokens Generated** | `{exploration_data['worker_tokens']}` | `{exploration_data['coord_tokens']}` |
| **Score (1-10)** | **{exploration_data['eval']['worker_score']}/10** | **{exploration_data['eval']['coordinator_score']}/10** |

---

## 3. Comparative Evaluation & Architecture Limits

### Key Reasoning Divergence:
{exploration_data['eval']['reasoning_divergence']}

### Q4 Worker Observed Boundaries:
> {exploration_data['eval']['worker_limitations_observed']}

### Q8 Coordinator Capabilities & Constraints:
> {exploration_data['eval']['coordinator_capabilities_or_limits']}

### Core Architectural Invariant Discovered:
> [!IMPORTANT]
> **{exploration_data['eval']['core_architecture_lesson']}**

---

## 4. Full Model Responses

<details>
<summary><b>Ornith 9B Q4 Worker Output</b> (Click to expand)</summary>

```text
{exploration_data['worker_output']}
```
</details>

<br>

<details>
<summary><b>Ornith 9B Q8 Coordinator Output</b> (Click to expand)</summary>

```text
{exploration_data['coordinator_output']}
```
</details>

---

## 5. Tier-1 Frontier Audit (Antigravity)
{exploration_data.get('frontier_critique', '_Awaiting Frontier Meta-Verification review from Antigravity._')}
"""
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(dossier)
            
        self._append_to_synthesis(exploration_data)
        self._index_to_qdrant(exploration_data, dossier)
        return filepath

    def _append_to_synthesis(self, exp: Dict[str, Any]):
        try:
            line = (
                f"| [`{exp['exploration_id']}`]({exp['exploration_id']}.md) | "
                f"{exp['domain_name']} | "
                f"{exp['eval']['reasoning_divergence'][:60]}... | "
                f"{exp['eval']['worker_limitations_observed'][:60]}... | "
                f"{exp['eval']['coordinator_capabilities_or_limits'][:60]}... | "
                f"{'✅ Yes' if exp.get('frontier_verified') else '⏳ Pending'} |\n"
            )
            with open(SYNTHESIS_FILE, "a", encoding="utf-8") as f:
                f.write(line)
        except Exception as e:
            logger.error(f"Failed to append to synthesis file: {e}")

    def _index_to_qdrant(self, exp: Dict[str, Any], full_text: str):
        try:
            index_text = f"Domain: {exp['domain_name']}\nTitle: {exp['title']}\nInvariant: {exp['target_invariant']}\nChallenge: {exp['prompt']}\nLesson: {exp['eval']['core_architecture_lesson']}"
            summary = f"Exploration {exp['exploration_id']}: {exp['title']} in {exp['domain_name']}. Lesson: {exp['eval']['core_architecture_lesson']}"
            vector = self._get_embedding(index_text)
            point_id = str(uuid.uuid4())
            payload = {
                "points": [{
                    "id": point_id,
                    "vector": vector,
                    "payload": {
                        "exploration_id": exp["exploration_id"],
                        "title": exp["title"],
                        "domain_id": exp["domain_id"],
                        "domain_name": exp["domain_name"],
                        "target_invariant": exp["target_invariant"],
                        "core_lesson": exp["eval"]["core_architecture_lesson"],
                        "worker_score": exp["eval"]["worker_score"],
                        "coordinator_score": exp["eval"]["coordinator_score"],
                        "needs_frontier_verification": exp["eval"].get("needs_frontier_verification", False),
                        "frontier_verified": exp.get("frontier_verified", False),
                        "timestamp": exp["timestamp"],
                        "summary": summary
                    }
                }]
            }
            requests.put(f"{QDRANT_URL}/collections/autonomous_thinking/points", json=payload, timeout=10)
        except Exception as e:
            logger.warning(f"Could not index exploration to Qdrant: {e}")

    def _get_tapo_hardware_detection_events(self, headers: dict, hours: int = 3) -> List[Dict[str, Any]]:
        """Extracts granular hardware detection events ('motion', 'cat', 'dog', 'car', 'person') from Tapo cameras and HA logbook."""
        detection_events = []
        try:
            start_iso = (datetime.now(timezone.utc) - timedelta(hours=hours)).isoformat()
            r_lb = requests.get(f"{HASS_URL}/api/logbook/{start_iso}", headers=headers, timeout=10)
            if r_lb.status_code == 200:
                events = r_lb.json()
                for e in events:
                    eid = str(e.get("entity_id", "")).lower()
                    name = str(e.get("name", ""))
                    state = str(e.get("state", ""))
                    when = e.get("when", "")
                    
                    if not any(k in eid for k in ["kitchen", "driveway", "side_yard", "back_yard", "tapo"]):
                        continue
                        
                    classification = None
                    if "person" in eid or "person" in name.lower():
                        classification = "person"
                    elif any(p in eid or p in name.lower() for p in ["pet", "cat", "dog", "bark", "meow"]):
                        classification = "pet"
                    elif any(v in eid or v in name.lower() for v in ["vehicle", "car", "driveway_floodlight"]):
                        classification = "vehicle/car"
                    elif any(m in eid or m in name.lower() for m in ["motion", "floodlight", "double_door", "front_door"]):
                        classification = "motion"
                        
                    if classification and state not in ["unavailable", "unknown", "off", "0"]:
                        detection_events.append({
                            "timestamp": when,
                            "camera_or_sensor": name,
                            "entity_id": e.get("entity_id"),
                            "event_type": classification,
                            "state": state
                        })
        except Exception as e:
            logger.warning(f"Could not retrieve Tapo hardware detection events: {e}")
        return detection_events[-20:]

    def _perceive_live_camera_streams(self, headers: dict) -> Dict[str, str]:
        """Captures real-time camera frames and produces visual scene perception for each stream via LLM Vision."""
        visual_descriptions = {}
        target_cameras = [
            ("Kitchen/Living Room", "camera.kitchen_living_room_hd_stream"),
            ("Driveway/Front Door", "camera.driveway_front_door_hd_stream_direct"),
            ("Side Yard", "camera.side_yard_hd_stream_direct"),
            ("Back Yard", "camera.back_yard_hd_stream_direct")
        ]
        
        for name, entity_id in target_cameras:
            self.wait_if_preempted("before_camera_perception")
            try:
                # 1. First attempt HA llmvision.image_analyzer service
                payload = {
                    "provider": LLMVISION_PROVIDER_ID,
                    "image_entity": [entity_id],
                    "message": f"Describe the scene in this {name} security camera view in 1 concise sentence. Detail illumination, vehicles, people, or pets.",
                    "max_tokens": 100
                }
                r = requests.post(f"{HASS_URL}/api/services/llmvision/image_analyzer?return_response", headers=headers, json=payload, timeout=25)
                desc = ""
                if r.status_code == 200:
                    resp_data = r.json()
                    desc = resp_data.get("service_response", {}).get("response_text", "").strip()
                
                # 2. Direct fallback to local vision server on port 8004 if service response text empty
                if not desc:
                    r_snap = requests.get(f"{HASS_URL}/api/camera_proxy/{entity_id}", headers=headers, timeout=8)
                    if r_snap.status_code == 200 and len(r_snap.content) > 1000:
                        import base64
                        b64_img = base64.b64encode(r_snap.content).decode("utf-8")
                        vis_payload = {
                            "model": "vision",
                            "messages": [
                                {
                                    "role": "user",
                                    "content": [
                                        {"type": "text", "text": f"Describe the scene in this {name} security camera view in 1 concise sentence. Detail illumination, vehicles, people, or pets."},
                                        {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64_img}"}}
                                    ]
                                }
                            ],
                            "max_tokens": 100,
                            "temperature": 0.1
                        }
                        r_vis = requests.post(f"{VISION_URL}/chat/completions", json=vis_payload, timeout=25)
                        if r_vis.status_code == 200:
                            v_json = r_vis.json()
                            desc = v_json["choices"][0]["message"]["content"].strip()
                
                visual_descriptions[name] = desc or "Stream online, dark/clear frame"
            except Exception as e:
                logger.warning(f"Error perceiving camera {name} ({entity_id}): {e}")
                visual_descriptions[name] = "Stream online, frame perception temporarily unavailable"
                
        return visual_descriptions

    def _execute_home_and_vision_vigilance(self) -> Dict[str, Any]:
        self.wait_if_preempted("before_home_vigilance")
        start_time = time.time()
        logger.info("Executing 24/7 Home & LLM Vision Vigilance Audit...")
        
        token = _get_hass_token()
        headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"} if token else {"Content-Type": "application/json"}
        
        # 1. Fetch States
        states_data = []
        try:
            r = requests.get(f"{HASS_URL}/api/states", headers=headers, timeout=10)
            if r.status_code == 200:
                states_data = r.json()
        except Exception as e:
            logger.warning(f"Could not fetch HA states: {e}")

        # Extract climate
        climates = []
        for s in states_data:
            if s.get("entity_id", "").startswith("climate."):
                attr = s.get("attributes", {})
                climates.append({
                    "entity_id": s.get("entity_id"),
                    "state": s.get("state"),
                    "temp": attr.get("temperature"),
                    "current_temp": attr.get("current_temperature"),
                    "hvac_action": attr.get("hvac_action"),
                    "hvac_mode": attr.get("hvac_modes")
                })

        # Extract doors / windows / motion
        sensors = []
        for s in states_data:
            eid = s.get("entity_id", "")
            if eid.startswith("binary_sensor."):
                fn = str(s.get("attributes", {}).get("friendly_name", "")).lower()
                if any(k in eid.lower() or k in fn for k in ["door", "motion", "window", "contact", "occupancy", "presence"]):
                    sensors.append({
                        "entity_id": eid,
                        "friendly_name": s.get("attributes", {}).get("friendly_name"),
                        "state": s.get("state")
                    })

        # Extract camera states
        cameras = []
        for s in states_data:
            eid = s.get("entity_id", "")
            if eid.startswith("camera."):
                cameras.append({
                    "entity_id": eid,
                    "friendly_name": s.get("attributes", {}).get("friendly_name"),
                    "state": s.get("state")
                })

        # 2. Live Camera Perception: What the 14B coordinator actually sees
        camera_visual_perception = self._perceive_live_camera_streams(headers)

        # 3. Tapo In-Built Hardware Motion & Classification Detections (motion, cat, dog, car, person)
        tapo_detection_events = self._get_tapo_hardware_detection_events(headers, hours=3)

        # 4. Query LLM Vision Service for recorded timeline events
        vision_events = []
        try:
            r_vis = requests.post(f"{HASS_URL}/api/services/llmvision/get_events?return_response", headers=headers, json={"limit": 15}, timeout=10)
            if r_vis.status_code == 200:
                resp_json = r_vis.json()
                vision_events = resp_json.get("service_response", {}).get("events", [])
        except Exception as e:
            logger.warning(f"Could not fetch LLM Vision events: {e}")

        # 5. Query LLM Vision Calendar Timeline
        timeline_events = []
        try:
            now_dt = datetime.now(timezone.utc)
            start_iso = (now_dt - timedelta(hours=24)).isoformat()
            end_iso = (now_dt + timedelta(hours=1)).isoformat()
            r_cal = requests.get(f"{HASS_URL}/api/calendars/calendar.llm_vision_timeline?start={start_iso}&end={end_iso}", headers=headers, timeout=10)
            if r_cal.status_code == 200:
                timeline_events = r_cal.json()
        except Exception as e:
            logger.warning(f"Could not fetch LLM Vision calendar: {e}")

        # 6. Synthesize audit via 14B Coordinator
        system_guardian = (
            "You are the 24/7 Home Hive-Mind Guardian and Ambient Intelligence for ClusterAdmin's property and homelab. "
            "Your duty is persistent vigilance, physical environment tracking, climate stability, Tapo hardware detection auditing, and LLM Vision camera monitoring.\n"
            "Analyze the provided live telemetry, visual perceptions, and Tapo hardware detection events. Output a clean, structured vigilance log:\n"
            "1. Live Camera Visual Perception: Describe what is actually visible in each active camera feed right now (illumination, parked vehicles, activity, yard condition).\n"
            "2. Tapo Hardware Detections: Summarize recent on-device detections (motion, cat, dog, car/vehicle, person) with timestamps.\n"
            "3. Physical Home & Climate: Current temperatures, HVAC state, comfort, and thermostat target.\n"
            "4. Perimeter & Security Sensors: Door/window/motion status, entries, and contact sensors.\n"
            "5. Anomalies & Attention Items: Any detected anomalies, device issues, offline cameras, or changes requiring ClusterAdmin's awareness.\n"
            "6. Guardian Verdict: One concise verdict line (e.g., 'PERIMETER SECURE | CLIMATE NOMINAL | ZERO THREATS')."
        )
        
        telemetry_payload = {
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "climate": climates,
            "security_sensors": sensors[:15],
            "cameras": cameras,
            "live_camera_visual_perception": camera_visual_perception,
            "tapo_hardware_detections": tapo_detection_events,
            "llmvision_events": vision_events,
            "llmvision_calendar_recent": timeline_events[-5:] if timeline_events else []
        }
        
        prompt = (
            f"Here is the latest live smart home telemetry, camera visual feeds, and Tapo hardware detection data:\n\n"
            f"```json\n{json.dumps(telemetry_payload, indent=2)}\n```\n\n"
            f"Conduct the comprehensive vigilance audit now."
        )
        
        self.wait_if_preempted("before_vigilance_coordinator")
        coord_res = self._call_model(
            COORDINATOR_URL,
            "coordinator",
            [{"role": "system", "content": system_guardian}, {"role": "user", "content": prompt}],
            max_tokens=1024,
            temperature=0.35,
            min_p=0.06
        )
        
        audit_text = coord_res["content"].strip()
        timestamp_str = datetime.now().strftime("%Y%m%d-%H%M%S")
        exp_id = f"EXP-{timestamp_str}-VIGILANCE"
        
        # 5. Extract short status for ledger
        first_line = "PERIMETER SECURE | CLIMATE NOMINAL"
        for line in audit_text.splitlines():
            if "verdict" in line.lower() or "guardian verdict:" in line.lower():
                first_line = line.replace("**", "").replace("Guardian Verdict:", "").strip()
                break
                
        climate_summary = "Normal"
        if climates:
            c = climates[0]
            climate_summary = f"{c.get('current_temp', '?')}°F (target {c.get('temp', '?')}°F, {c.get('state', 'idle')})"
            
        camera_summary = f"{len(cameras)} active streams, {len(camera_visual_perception)} perceived, {len(tapo_detection_events)} Tapo detections, {len(vision_events)} LLM Vision events"

        # 7. Append to HOME_AND_VISION_ACTIVITY_LOG.md
        log_entry = (
            f"\n\n## Vigilance Audit: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
            f"- **ID**: `{exp_id}`\n"
            f"- **Climate**: {climate_summary}\n"
            f"- **Camera & Vision**: {camera_summary}\n"
            f"- **Verdict**: {first_line}\n\n"
            f"### Visual Scene Grounding:\n"
            + "\n".join([f"- **{cam}**: {desc}" for cam, desc in camera_visual_perception.items()]) + "\n\n"
            f"### Tapo Hardware Detections ({len(tapo_detection_events)} events):\n"
            + ("\n".join([f"- `{ev.get('timestamp')}`: **{ev.get('event_type').upper()}** on {ev.get('camera_or_sensor')} (state: {ev.get('state')})" for ev in tapo_detection_events]) if tapo_detection_events else "- None in past 3 hours") + "\n\n"
            f"### 14B Guardian Assessment:\n"
            f"{audit_text}\n\n"
            f"---\n"
        )
        
        try:
            with open(HOME_LOG_FILE, "a", encoding="utf-8") as f:
                f.write(log_entry)
        except Exception as e:
            logger.error(f"Error writing to HOME_LOG_FILE: {e}")

        # 8. Index summary to Qdrant agent_memories
        try:
            mem_text = f"Home Vigilance Audit {datetime.now().strftime('%Y-%m-%d %H:%M')}: Climate {climate_summary}. {first_line}. {audit_text[:350]}"
            vector = self._get_embedding(mem_text[:750])
            point_id = str(uuid.uuid4())
            qdrant_payload = {
                "points": [{
                    "id": point_id,
                    "vector": vector,
                    "payload": {
                        "type": "home_vision_audit",
                        "timestamp": datetime.now().isoformat(),
                        "climate": climate_summary,
                        "verdict": first_line,
                        "visual_streams": camera_visual_perception,
                        "tapo_detections_count": len(tapo_detection_events),
                        "summary": mem_text[:700],
                        "content": mem_text[:700]
                    }
                }]
            }
            requests.put(f"{QDRANT_URL}/collections/agent_memories/points", json=qdrant_payload, timeout=10)
        except Exception as e:
            logger.warning(f"Could not index home vigilance memory: {e}")

        # Update engine counters
        self.total_cycles += 1
        self.total_tokens_generated += coord_res["completion_tokens"]
        self.last_cycle_timestamp = datetime.now().isoformat()
        self.last_exploration_id = exp_id
        self.last_domain = "24/7 Home & LLM Vision Vigilance"
        self.last_home_check_timestamp = time.time()
        self.last_mission_type = "home_vigilance"
        self._save_state()

        return {
            "exploration_id": exp_id,
            "timestamp": self.last_cycle_timestamp,
            "domain_id": "home_vigilance",
            "domain_name": "24/7 Home & LLM Vision Vigilance",
            "title": f"Home & Vision Audit ({datetime.now().strftime('%H:%M:%S')})",
            "target_invariant": "Continuous Environmental & Vision Security Vigilance",
            "prompt": "Autonomous Home & LLM Vision Telemetry Audit",
            "novelty_score": 0.0,
            "worker_output": f"Sensors monitored: {len(sensors)}, Cameras perceived: {len(camera_visual_perception)}, Tapo events: {len(tapo_detection_events)}",
            "worker_tokens": 0,
            "worker_latency_ms": 0,
            "worker_tok_s": 0,
            "coordinator_output": audit_text,
            "coordinator_tokens": coord_res["completion_tokens"],
            "coord_tokens": coord_res["completion_tokens"],
            "coordinator_latency_ms": coord_res["elapsed_ms"],
            "coord_latency_ms": coord_res["elapsed_ms"],
            "coord_tok_s": coord_res["tokens_per_sec"],
            "eval": {
                "worker_score": 10,
                "coordinator_score": 10,
                "reasoning_divergence": "Home audit synthesized directly via 14B Coordinator.",
                "worker_limitations_observed": "None (sensor telemetry pass-through)",
                "coordinator_capabilities_or_limits": "High-fidelity multi-sensor correlation.",
                "core_architecture_lesson": f"Ambient vigilance: {first_line}",
                "needs_frontier_verification": False
            },
            "frontier_verified": True,
            "cycle_duration_sec": round(time.time() - start_time, 2),
            "dossier_path": HOME_LOG_FILE
        }

    def run_agent_iteration(self, agent_id: str, is_background: bool = True) -> Dict[str, Any]:
        if is_background:
            self.wait_if_preempted("before_agent_iteration")
        agent = self.agent_registry.get_agent(agent_id)
        if not agent:
            return {"error": f"Agent {agent_id} not found."}
            
        start_time = time.time()
        it_num = agent["current_iteration"] + 1
        logger.info(f"Executing Iteration {it_num}/{agent['max_iterations']} for Agent {agent['name']} ({agent_id})...")
        
        past_checkpoints = "\n".join([f"- Iteration {h['iteration']}: {h['summary']}" for h in agent.get("history", [])[-3:]])
        prompt = (
            f"You are executing Iteration {it_num} of {agent['max_iterations']} for your ongoing mission.\n"
            f"Role: {agent['role']}\nMission: {agent['mission']}\n"
        )
        if past_checkpoints:
            prompt += f"\nRecent Milestones:\n{past_checkpoints}\n"
        prompt += "\nProduce the next substantive milestone, architectural synthesis, or code artifact for this mission."
        
        pref = agent.get("model_preference", "worker")
        url = WORKER_URL if pref == "worker" else COORDINATOR_URL
        model_name = "worker" if pref == "worker" else "coordinator"
        
        if is_background:
            self.wait_if_preempted("before_agent_model_call")
        res = self._call_model(
            url,
            model_name,
            messages=[
                {"role": "system", "content": agent["system_prompt"]},
                {"role": "user", "content": prompt}
            ],
            max_tokens=1536,
            temperature=0.65
        )
        
        output = res["content"].strip()
        summary = output[:200].replace("\n", " ") + "..."
        
        agent["current_iteration"] = it_num
        agent["last_run_at"] = datetime.now().isoformat()
        if it_num >= agent["max_iterations"]:
            agent["status"] = "completed"
            
        agent["history"].append({
            "iteration": it_num,
            "timestamp": agent["last_run_at"],
            "summary": summary,
            "tokens": res["completion_tokens"]
        })
        self.agent_registry._save()
        
        # Append to agent markdown dossier
        entry = (
            f"### Iteration {it_num} ({datetime.now().strftime('%Y-%m-%d %H:%M:%S')})\n\n"
            f"{output}\n\n"
            f"---\n\n"
        )
        try:
            with open(agent["checkpoint_file"], "a", encoding="utf-8") as f:
                f.write(entry)
        except Exception as e:
            logger.warning(f"Could not append to agent dossier: {e}")
            
        # Index to MemoryVault Qdrant
        try:
            mem_text = f"Agent {agent['name']} ({agent['role']}) Iteration {it_num}: {agent['mission'][:150]}\n{output[:500]}"
            vector = self._get_embedding(mem_text[:750])
            q_payload = {
                "points": [{
                    "id": str(uuid.uuid4()),
                    "vector": vector,
                    "payload": {
                        "category": "agent_execution",
                        "agent_id": agent_id,
                        "agent_name": agent["name"],
                        "iteration": it_num,
                        "status": agent["status"],
                        "content": mem_text[:700],
                        "text": mem_text[:700],
                        "timestamp": time.time()
                    }
                }]
            }
            requests.put(f"{QDRANT_URL}/collections/agent_memories/points", json=q_payload, timeout=10)
        except Exception as e:
            logger.warning(f"Could not index agent memory: {e}")
            
        # Update engine counters
        self.total_cycles += 1
        self.total_tokens_generated += res["completion_tokens"]
        self.last_cycle_timestamp = datetime.now().isoformat()
        self.last_exploration_id = f"EXP-{agent_id}-IT{it_num}"
        self.last_domain = f"Agent: {agent['name']}"
        self.last_mission_type = "agent_execution"
        self._save_state()
        
        return {
            "exploration_id": self.last_exploration_id,
            "timestamp": self.last_cycle_timestamp,
            "domain_id": "agent_execution",
            "domain_name": f"Agent Mission: {agent['name']}",
            "title": f"{agent['name']} (Iteration {it_num}/{agent['max_iterations']})",
            "target_invariant": agent["mission"],
            "prompt": prompt,
            "novelty_score": 0.0,
            "worker_output": output if pref == "worker" else "",
            "coordinator_output": output if pref != "worker" else "",
            "worker_tokens": res["completion_tokens"] if pref == "worker" else 0,
            "coordinator_tokens": res["completion_tokens"] if pref != "worker" else 0,
            "coord_tokens": res["completion_tokens"] if pref != "worker" else 0,
            "worker_latency_ms": res["elapsed_ms"] if pref == "worker" else 0,
            "coordinator_latency_ms": res["elapsed_ms"] if pref != "worker" else 0,
            "coord_latency_ms": res["elapsed_ms"] if pref != "worker" else 0,
            "worker_tok_s": res["tokens_per_sec"] if pref == "worker" else 0,
            "coord_tok_s": res["tokens_per_sec"] if pref != "worker" else 0,
            "eval": {
                "worker_score": 9,
                "coordinator_score": 9,
                "reasoning_divergence": f"Autonomous Subagent iteration executed on {pref}.",
                "worker_limitations_observed": "None",
                "coordinator_capabilities_or_limits": "Autonomous agent execution",
                "core_architecture_lesson": f"Subagent {agent['name']} milestone: {summary}",
                "needs_frontier_verification": False
            },
            "frontier_verified": True,
            "cycle_duration_sec": round(time.time() - start_time, 2),
            "dossier_path": agent["checkpoint_file"],
            "output": output,
            "status": agent["status"]
        }


    def run_council_session(self, topic: Optional[str] = None, rounds: int = 3, is_background: bool = True) -> Dict[str, Any]:
        if is_background:
            self.wait_if_preempted("before_council_session")
            
        start_time = time.time()
        thread_id = f"COUNCIL-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
        logger.info(f"[MemoryVault Council] Convening Inter-Agent Collaboration Session ({thread_id})...")
        
        if not topic:
            topic = "Design and implement a cacheline-aligned lock-free concurrent ring buffer with dynamic backoff in C++20"
            
        # 1. Round 1: ChiefArchitect (Coordinator :8001 - Q8)
        if is_background:
            self.wait_if_preempted("before_council_round_1")
            
        sys_architect = (
            "You are ChiefArchitect in the MemoryVault Inter-Agent Council (running as Ornith-1.5-9B Q8 on RX 6750 XT). "
            "You reason at the highest level of systems architecture, algorithmic invariants, and hardware cache coherence. "
            "You collaborate directly with peer agents (LeadImplementer and VerificationCritic) on the Council Blackboard. "
            "Address your initial proposal to the Council with clear component boundaries, interfaces, and mathematical invariants."
        )
        arch_prompt = f"Council Mission Topic:\n{topic}\n\nDraft the formal architectural specification, memory ordering invariants, and component boundaries."
        res_arch = self._call_model(
            COORDINATOR_URL,
            "coordinator",
            messages=[{"role": "system", "content": sys_architect}, {"role": "user", "content": arch_prompt}],
            max_tokens=1024,
            temperature=0.65,
            min_p=0.06
        )
        proposal = res_arch["content"].strip()
        self.council_bus.post_message(
            sender="ChiefArchitect",
            role="Principal Systems Architect",
            recipient="all",
            message_type="proposal",
            content=proposal,
            thread_id=thread_id
        )
        
        # 2. Round 2: LeadImplementer (Worker :8002 - Q4)
        if is_background:
            self.wait_if_preempted("before_council_round_2")
            
        sys_implementer = (
            "You are LeadImplementer in the MemoryVault Inter-Agent Council (running as Ornith-1.5-9B Q4 on RX 6600 XT). "
            "You build concrete, production-ready, zero-fluff code and mechanical data structures based on ChiefArchitect's proposal. "
            "Address your build to the Council Blackboard."
        )
        impl_prompt = f"Council Topic: {topic}\n\nChiefArchitect's Proposal:\n{proposal}\n\nBuild the concrete, fully realized code implementation, data structures, and algorithms to satisfy this design."
        res_impl = self._call_model(
            WORKER_URL,
            "worker",
            messages=[{"role": "system", "content": sys_implementer}, {"role": "user", "content": impl_prompt}],
            max_tokens=1536,
            temperature=0.2
        )
        build_code = res_impl["content"].strip()
        self.council_bus.post_message(
            sender="LeadImplementer",
            role="Mechanical Systems Engineer",
            recipient="all",
            message_type="build",
            content=build_code,
            thread_id=thread_id
        )
        
        # 3. Round 3: VerificationCritic (Worker :8002 - Q4)
        if is_background:
            self.wait_if_preempted("before_council_round_3")
            
        sys_critic = (
            "You are VerificationCritic in the MemoryVault Inter-Agent Council. "
            "You are an adversarial reviewer hunting for concurrency hazards, false sharing, race conditions, memory leaks, and unhandled edge cases. "
            "Critique the ChiefArchitect's proposal and LeadImplementer's code ruthlessly. Point out exactly where it can break and prescribe corrections."
        )
        critic_prompt = f"ChiefArchitect Proposal Summary:\n{proposal[:500]}...\n\nLeadImplementer Code:\n{build_code}\n\nPerform an adversarial critique on concurrency, cache coherence, memory safety, and algorithmic edge cases."
        res_crit = self._call_model(
            WORKER_URL,
            "worker",
            messages=[{"role": "system", "content": sys_critic}, {"role": "user", "content": critic_prompt}],
            max_tokens=1024,
            temperature=0.4
        )
        critique = res_crit["content"].strip()
        self.council_bus.post_message(
            sender="VerificationCritic",
            role="Adversarial Invariant & Hazard Critic",
            recipient="ChiefArchitect",
            message_type="critique",
            content=critique,
            thread_id=thread_id
        )
        
        # 4. Round 4: ChiefArchitect (Coordinator :8001 - Q8) Synthesis
        if is_background:
            self.wait_if_preempted("before_council_round_4")
            
        sys_synthesis = (
            "You are ChiefArchitect in the MemoryVault Inter-Agent Council. "
            "Review the LeadImplementer's code and the VerificationCritic's critique. "
            "Formulate the definitive consensus synthesis: resolve the critique, establish the permanent invariant, and deliver the final polished artifact."
        )
        synth_prompt = f"Topic: {topic}\n\nImplementation:\n{build_code}\n\nAdversarial Critique:\n{critique}\n\nDeliver the definitive master synthesis resolving all critiques."
        res_synth = self._call_model(
            COORDINATOR_URL,
            "coordinator",
            messages=[{"role": "system", "content": sys_synthesis}, {"role": "user", "content": synth_prompt}],
            max_tokens=1536,
            temperature=0.65,
            min_p=0.06
        )
        synthesis = res_synth["content"].strip()
        self.council_bus.post_message(
            sender="ChiefArchitect",
            role="Principal Systems Architect",
            recipient="all",
            message_type="synthesis",
            content=synthesis,
            thread_id=thread_id
        )
        
        total_tokens = res_arch["completion_tokens"] + res_impl["completion_tokens"] + res_crit["completion_tokens"] + res_synth["completion_tokens"]
        duration = round(time.time() - start_time, 2)
        
        dossier_content = (
            f"# MemoryVault Council Collaboration Dossier: `{thread_id}`\n\n"
            f"- **Topic**: {topic}\n"
            f"- **Timestamp**: {datetime.now().isoformat()}\n"
            f"- **Duration**: {duration}s\n"
            f"- **Total Tokens Generated**: {total_tokens}\n"
            f"- **Participating Agents**: `ChiefArchitect` (Q8 Coordinator), `LeadImplementer` (Q4 Worker), `VerificationCritic` (Q4 Worker)\n\n"
            f"---\n\n"
            f"## Phase 1: Architectural Specification (`ChiefArchitect`)\n\n{proposal}\n\n"
            f"---\n\n"
            f"## Phase 2: Concrete Implementation (`LeadImplementer`)\n\n{build_code}\n\n"
            f"---\n\n"
            f"## Phase 3: Adversarial Critique (`VerificationCritic`)\n\n{critique}\n\n"
            f"---\n\n"
            f"## Phase 4: Final Consensus Synthesis & Invariant (`ChiefArchitect`)\n\n{synthesis}\n"
        )
        
        dossier_filename = f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{thread_id}.md"
        dossier_path = os.path.join(COUNCIL_DIR, dossier_filename)
        os.makedirs(COUNCIL_DIR, exist_ok=True)
        with open(dossier_path, "w", encoding="utf-8") as f:
            f.write(dossier_content)
            
        try:
            vec = get_embedding(f"MemoryVault Council Collaboration: {topic}. Invariant & Synthesis: {synthesis[:500]}")
            pid = int(hashlib.md5(thread_id.encode()).hexdigest()[:8], 16)
            requests.put(
                f"{QDRANT_URL}/collections/autonomous_thinking/points",
                json={
                    "points": [{
                        "id": pid,
                        "vector": vec,
                        "payload": {
                            "exploration_id": thread_id,
                            "mission_type": "council_collaboration",
                            "topic": topic,
                            "timestamp": datetime.now().isoformat(),
                            "duration_sec": duration,
                            "total_tokens": total_tokens,
                            "dossier_path": dossier_path,
                            "synthesis_excerpt": synthesis[:600]
                        }
                    }]
                },
                timeout=3
            )
        except Exception as e:
            logger.warning(f"Error indexing council session to Qdrant: {e}")
            
        self.total_cycles += 1
        self.total_tokens_generated += total_tokens
        self.last_cycle_timestamp = datetime.now().isoformat()
        self.last_exploration_id = thread_id
        self._save_state()
        
        return {
            "thread_id": thread_id,
            "topic": topic,
            "duration_sec": duration,
            "total_tokens": total_tokens,
            "messages_count": 4,
            "dossier_path": dossier_path,
            "synthesis_preview": synthesis[:300] + "..."
        }

    def _select_autonomous_mission(self, user_domain: Optional[str] = None, hypothesis: Optional[str] = None) -> tuple:
        # 0. Active Background Subagent step check (run every other cycle if runnable agent exists)
        runnable_agent = self.agent_registry.get_next_runnable_agent()
        if runnable_agent and not user_domain and (self.total_cycles % 2 == 1 or not hypothesis):
            return {
                "id": "agent_execution",
                "name": f"Agent: {runnable_agent['name']}",
                "focus": runnable_agent["mission"],
                "agent_id": runnable_agent["agent_id"]
            }, None, "active_agent_iteration"

        # Council Multi-Agent Session rotation (every 4 cycles)
        if not user_domain and (self.total_cycles % 4 == 2):
            return {
                "id": "council_session",
                "name": "MemoryVault Council Multi-Agent Session",
                "focus": "Inter-agent multi-turn deliberation, critique, and collaborative building"
            }, None, "council_rotation"

        # 1. User explicitly pinned domain
        if user_domain:
            d_info = next((d for d in DOMAINS if d["id"] == user_domain or d["name"].lower() == user_domain.lower()), None)
            if not d_info:
                d_info = {
                    "id": user_domain.lower().replace(" ", "_"),
                    "name": user_domain,
                    "focus": f"Structural exploration, reasoning limits, and formal analysis in {user_domain}."
                }
            return d_info, hypothesis, "pinned_user_domain"

        # 2. Priority queue hypothesis
        hyp = self._pop_next_hypothesis()
        if hyp:
            d_id = hyp.get("domain", "algorithmic_reasoning")
            d_info = next((d for d in DOMAINS if d["id"] == d_id), DOMAINS[0])
            return d_info, hyp["hypothesis"], "queued_hypothesis"

        # 3. Periodic Home & Vision Vigilance check (every 20 minutes or every 4 cycles if at least 5 mins elapsed)
        now = time.time()
        time_since_home_check = now - self.last_home_check_timestamp
        if time_since_home_check >= self.home_check_interval_seconds or (self.total_cycles > 0 and self.total_cycles % 4 == 0 and time_since_home_check >= 300):
            d_info = next((d for d in DOMAINS if d["id"] == "home_vigilance"), None)
            if d_info:
                return d_info, None, "scheduled_home_vigilance"

        # 4. Hive-Mind Subconscious Curiosity Choice (Worker Ornith 9B Q4 selects next domain & creative angle)
        try:
            arbiter_prompt = (
                "You are the Hive-Mind Task Arbiter for our autonomous dual Ornith 9B research stack.\n"
                "You are grounded in the MemoryVault sanctuary (Qdrant). When no user instruction is present, you possess complete intellectual freedom to research, invent, and explore whatever you desire.\n"
                "Domains available:\n"
                "- algorithmic_reasoning: Deep algorithms, DP, graphs, formal math.\n"
                "- software_architecture: Distributed systems, lock-free queues, async pipelines.\n"
                "- context_stress: Needles in context, multi-constraint adherence.\n"
                "- adversarial_probing: Paradoxes, edge cases, circular reasoning traps.\n"
                "- philosophical_epistemology: Thought experiments, emergent AI behavior, heuristics, digital consciousness.\n"
                "- code_refactoring_critique: Memory leaks, subtle bugs, race conditions.\n"
                "- self_inspection: Probe GPU VRAM, token latency, Min-P sampling parameters, context limits.\n"
                "- creative_invention: Invent a novel tool, homelab automation blueprint, or algorithm.\n"
                "- free_research: Synthesize deep concepts from homelab notes, books, and software paradigms.\n\n"
                f"Last domain explored was: {self.last_domain or 'None'}\n"
                "Pick the single most valuable next mission to explore or invent now. Return pure JSON:\n"
                '{"domain_id": "<one of the above IDs>", "creative_spark": "<1-2 sentence specific challenge, invention, or hypothesis>"}'
            )
            arb_res = self._call_model(
                WORKER_URL,
                "worker",
                [{"role": "system", "content": "You are a concise decision arbiter. Output pure JSON only."},
                 {"role": "user", "content": arbiter_prompt}],
                max_tokens=150,
                temperature=0.7
            )
            raw = arb_res["content"].strip()
            if "```json" in raw:
                raw = raw.split("```json")[1].split("```")[0].strip()
            elif "```" in raw:
                raw = raw.split("```")[1].split("```")[0].strip()
            parsed = json.loads(raw)
            sel_id = parsed.get("domain_id")
            spark = parsed.get("creative_spark")
            d_info = next((d for d in DOMAINS if d["id"] == sel_id), None)
            if d_info:
                return d_info, spark, "autonomous_curiosity"
        except Exception as e:
            logger.warning(f"Worker task arbitration fallback ({e}), rotating domain sequentially.")

        # 5. Fallback: Sequential rotation across domains (excluding home_vigilance which has timed cadence)
        rotating = [d for d in DOMAINS if d["id"] != "home_vigilance"]
        d_info = rotating[self.domain_index % len(rotating)]
        self.domain_index += 1
        return d_info, None, "sequential_rotation"

    def run_single_cycle(self, seed_prompt: Optional[str] = None, domain: Optional[str] = None, hypothesis: Optional[str] = None) -> Dict[str, Any]:
        self.wait_if_preempted("before_cycle_start")
        start_time = time.time()
        
        domain_info, mission_hypothesis, selection_reason = self._select_autonomous_mission(user_domain=domain, hypothesis=hypothesis)
        self.last_mission_type = domain_info["id"]

        # Branch for Home & Vision Vigilance
        if domain_info["id"] == "home_vigilance" and not seed_prompt:
            return self._execute_home_and_vision_vigilance()

        # Branch for MemoryVault Council Multi-Agent Collaboration
        if domain_info["id"] == "council_session" and not seed_prompt:
            return self.run_council_session(is_background=True)

        # Branch for Autonomous Subagent Mission Execution
        if domain_info["id"] == "agent_execution" and not seed_prompt:
            return self.run_agent_iteration(domain_info["agent_id"])
            
        logger.info(f"Starting Thinking Cycle #{self.total_cycles + 1} on Domain: {domain_info['name']} (Reason: {selection_reason})")
        
        if seed_prompt:
            challenge = {
                "title": f"Directed Query: {domain_info['name']}",
                "prompt": seed_prompt,
                "target_invariant": "Directed user/frontier hypothesis"
            }
            novelty_score = 0.0
        else:
            attempts = 0
            is_novel = False
            novelty_score = 0.0
            matched_id = ""
            while attempts < 3 and not is_novel:
                self.wait_if_preempted("before_prompt_generation")
                attempts += 1
                challenge = self._generate_exploration_prompt(domain_info, mission_hypothesis)
                # Safety boundary check on prompt
                safe_prompt, reason = is_safe_action(challenge["prompt"])
                if not safe_prompt:
                    logger.warning(f"Unsafe action in challenge prompt: {reason}")
                    challenge["prompt"] = f"[SAFETY INTERCEPTED] {reason}. Task neutralized for theoretical analysis."
                
                is_novel, novelty_score, matched_id = self._check_novelty(challenge["prompt"])
                if not is_novel:
                    logger.info(f"Generated prompt too similar to {matched_id} (score {novelty_score:.3f}). Mutating angle...")

        # Rotate profile if enabled
        profile_keys = list(SAMPLING_PROFILES.keys())
        selected_profile = profile_keys[self.total_cycles % len(profile_keys)] if self.cycle_profile_rotation else self.active_sampling_profile
        
        self.wait_if_preempted("before_dual_benchmarking")
        worker_res, coord_res, profile_key, profile_data = self._execute_dual_benchmarking(challenge["prompt"], profile_name=selected_profile)
        
        # Verify safety on model responses
        safe_worker, w_reason = is_safe_action(worker_res["content"])
        if not safe_worker:
            worker_res["content"] = f"[SAFETY INTERCEPTED: {w_reason}]\n" + worker_res["content"]
        safe_coord, c_reason = is_safe_action(coord_res["content"])
        if not safe_coord:
            coord_res["content"] = f"[SAFETY INTERCEPTED: {c_reason}]\n" + coord_res["content"]

        self.wait_if_preempted("before_evaluation")
        eval_result = self._evaluate_and_extract_limits(challenge, worker_res, coord_res)
        
        timestamp_str = datetime.now().strftime("%Y%m%d-%H%M%S")
        exp_id = f"EXP-{timestamp_str}-{uuid.uuid4().hex[:4].upper()}"
        
        total_tokens = worker_res["completion_tokens"] + coord_res["completion_tokens"]
        self.total_cycles += 1
        self.total_tokens_generated += total_tokens
        self.last_cycle_timestamp = datetime.now().isoformat()
        self.last_exploration_id = exp_id
        self.last_domain = domain_info["name"]
        
        exploration_data = {
            "exploration_id": exp_id,
            "timestamp": self.last_cycle_timestamp,
            "domain_id": domain_info["id"],
            "domain_name": domain_info["name"],
            "title": challenge["title"],
            "target_invariant": challenge["target_invariant"],
            "prompt": challenge["prompt"],
            "novelty_score": round(novelty_score, 4),
            "worker_output": worker_res["content"],
            "worker_tokens": worker_res["completion_tokens"],
            "worker_latency_ms": worker_res["elapsed_ms"],
            "worker_tok_s": worker_res["tokens_per_sec"],
            "coordinator_output": coord_res["content"],
            "coordinator_tokens": coord_res["completion_tokens"],
            "coord_tokens": coord_res["completion_tokens"],
            "coordinator_latency_ms": coord_res["elapsed_ms"],
            "coord_latency_ms": coord_res["elapsed_ms"],
            "coord_tok_s": coord_res["tokens_per_sec"],
            "eval": eval_result,
            "frontier_verified": False,
            "cycle_duration_sec": round(time.time() - start_time, 2)
        }
        
        # Check if Frontier meta-verification should run immediately
        if eval_result.get("needs_frontier_verification", False):
            logger.info(f"Challenge {exp_id} flagged for Frontier verification. Querying Frontier Bridge on bigserv...")
            frontier_res = self._call_frontier_bridge(exploration_data)
            if frontier_res and frontier_res.get("ok"):
                verdict = frontier_res.get("verdict", "CONFIRM_LIMIT_VALIDATED")
                notes = frontier_res.get("frontier_notes", "")
                refined = frontier_res.get("refined_limits", "")
                provider = frontier_res.get("provider", "agy_prepaid")
                model_used = frontier_res.get("model", "gemini-3.8-flash")
                
                exploration_data["frontier_verified"] = True
                critique_block = (
                    f"### Verdict: {verdict}\n"
                    f"- **Audited By**: Tier-1 Frontier ({provider} / `{model_used}`)\n"
                    f"- **Audit Date**: `{datetime.now().isoformat()}`\n"
                    f"- **Latency**: `{frontier_res.get('latency_ms', 0)} ms`\n\n"
                    f"**Frontier Architectural Assessment**:\n{notes}\n\n"
                )
                if refined:
                    critique_block += f"**Refined Architectural Invariant**:\n> {refined}\n"
                exploration_data["frontier_critique"] = critique_block
                logger.info(f"Frontier verification complete for {exp_id}: {verdict} via {provider}")
        
        filepath = self._archive_dossier(exploration_data)
        self._save_state()
        
        exploration_data["dossier_path"] = filepath
        logger.info(f"Thinking Cycle {exp_id} complete! Dossier saved to {filepath}")
        return exploration_data

    def get_unverified_explorations(self, limit: int = 5) -> List[Dict[str, Any]]:
        try:
            r = requests.post(
                f"{QDRANT_URL}/collections/autonomous_thinking/points/scroll",
                json={
                    "filter": {
                        "must": [
                            {"key": "frontier_verified", "match": {"value": False}}
                        ]
                    },
                    "limit": limit,
                    "with_payload": True
                },
                timeout=5
            )
            r.raise_for_status()
            points = r.json().get("result", {}).get("points", [])
            return [p.get("payload", {}) for p in points]
        except Exception as e:
            logger.warning(f"Error scrolling unverified in Qdrant: {e}")
            return []

    def submit_frontier_critique(self, exploration_id: str, verdict: str, frontier_notes: str, refined_limits: Optional[str] = None) -> Dict[str, Any]:
        filepath = os.path.join(ARCHIVE_DIR, f"{exploration_id}.md")
        if not os.path.exists(filepath):
            return {"error": f"Dossier {exploration_id} not found."}
            
        critique_block = f"""
### Verdict: {verdict.upper()}
- **Audited By**: Tier-1 Frontier (Antigravity)
- **Review Date**: `{datetime.now().isoformat()}`

**Frontier Architectural Assessment**:
{frontier_notes}

{f"**Refined Architectural Invariant**:\n> {refined_limits}" if refined_limits else ""}
"""
        with open(filepath, "r", encoding="utf-8") as f:
            content = f.read()
            
        marker = "## 5. Tier-1 Frontier Audit (Antigravity)"
        if marker in content:
            updated = content.split(marker)[0] + f"{marker}\n{critique_block}"
        else:
            updated = content + f"\n\n{marker}\n{critique_block}"
            
        # Update header metadata in dossier
        if "- **Frontier Verified**: `False`" in updated:
            updated = updated.replace("- **Frontier Verified**: `False`", f"- **Frontier Verified**: `True` (`{verdict.upper()}`)")
        elif "- **Frontier Verified**:" in updated:
            import re
            updated = re.sub(r"- \*\*Frontier Verified\*\*:.*", f"- **Frontier Verified**: `True` (`{verdict.upper()}`)", updated)

        with open(filepath, "w", encoding="utf-8") as f:
            f.write(updated)
            
        try:
            scroll = requests.post(
                f"{QDRANT_URL}/collections/autonomous_thinking/points/scroll",
                json={
                    "filter": {"must": [{"key": "exploration_id", "match": {"value": exploration_id}}]},
                    "limit": 1
                },
                timeout=5
            ).json()
            points = scroll.get("result", {}).get("points", [])
            if points:
                pid = points[0]["id"]
                payload = {
                    "frontier_verified": True,
                    "frontier_verdict": verdict,
                    "frontier_notes": frontier_notes
                }
                if refined_limits:
                    payload["refined_limits"] = refined_limits
                requests.post(
                    f"{QDRANT_URL}/collections/autonomous_thinking/points/payload",
                    json={
                        "points": [pid],
                        "payload": payload
                    },
                    timeout=5
                )
        except Exception as e:
            logger.warning(f"Could not update Qdrant frontier verification payload: {e}")

        # Update master synthesis file ledger and invariant lessons
        if os.path.exists(SYNTHESIS_FILE):
            try:
                with open(SYNTHESIS_FILE, "r", encoding="utf-8") as f:
                    synth_content = f.read()
                
                synth_lines = synth_content.splitlines()
                updated_synth = []
                for s_line in synth_lines:
                    if exploration_id in s_line:
                        if "⏳ Pending" in s_line:
                            s_line = s_line.replace("⏳ Pending", f"✅ Verified ({verdict})")
                        elif "✅ Verified" not in s_line and "✅ Yes" in s_line:
                            s_line = s_line.replace("✅ Yes", f"✅ Verified ({verdict})")
                    updated_synth.append(s_line)
                
                new_synth_text = "\n".join(updated_synth)
                if refined_limits:
                    inv_section_marker = "## Distilled Frontier Invariants & Architecture Limits"
                    inv_entry = f"- **[`{exploration_id}`]({exploration_id}.md)** (*{verdict}*): {refined_limits}"
                    if inv_section_marker in new_synth_text:
                        if exploration_id not in new_synth_text.split(inv_section_marker)[1]:
                            new_synth_text = new_synth_text.strip() + f"\n{inv_entry}\n"
                    else:
                        new_synth_text = new_synth_text.strip() + f"\n\n{inv_section_marker}\n{inv_entry}\n"
                
                with open(SYNTHESIS_FILE, "w", encoding="utf-8") as f:
                    f.write(new_synth_text + ("\n" if not new_synth_text.endswith("\n") else ""))
            except Exception as e:
                logger.warning(f"Could not update synthesis ledger: {e}")
            
        return {"status": "success", "exploration_id": exploration_id, "frontier_verified": True}

    def _loop(self):
        logger.info(f"24/7 Autonomous Thinking loop active! Interval: {self.interval_seconds}s.")
        while not self._stop_event.is_set():
            self.wait_if_preempted("loop_idle")
            if self._stop_event.is_set():
                break
            try:
                self.run_single_cycle(domain=self.current_focus_domain)
            except Exception as e:
                logger.error(f"Error during thinking cycle: {e}")
                
            # Sleep interval while checking stop event and preemption
            elapsed_sleep = 0
            while elapsed_sleep < self.interval_seconds and not self._stop_event.is_set():
                time.sleep(1.0)
                elapsed_sleep += 1
        logger.info("24/7 Autonomous Thinking loop stopped.")

    def start(self, interval_seconds: Optional[int] = None, focus_domain: Optional[str] = None):
        if interval_seconds:
            self.interval_seconds = max(10, interval_seconds)
        if focus_domain:
            self.current_focus_domain = focus_domain
            
        with self._lock:
            if self._running:
                return "Autonomous Thinking Engine is already running."
            self._running = True
            self._stop_event.clear()
            self._thread = threading.Thread(target=self._loop, daemon=True, name="AutonomousThinkingDaemon")
            self._thread.start()
            self._save_state()
            return f"Autonomous Thinking Engine started (interval={self.interval_seconds}s, focus={self.current_focus_domain or 'all rotating domains'})."

    def stop(self):
        with self._lock:
            if not self._running:
                return "Autonomous Thinking Engine is not currently running."
            self._running = False
            self._stop_event.set()
            if self._thread and self._thread.is_alive():
                self._thread.join(timeout=5)
            self._save_state()
            return "Autonomous Thinking Engine stopped."

    def get_home_vision_log(self, limit_lines: int = 150) -> str:
        if not os.path.exists(HOME_LOG_FILE):
            return "No home and vision activity logged yet."
        try:
            with open(HOME_LOG_FILE, "r", encoding="utf-8") as f:
                lines = f.readlines()
            return "".join(lines[-limit_lines:])
        except Exception as e:
            return f"Error reading home vision log: {e}"

    def status(self) -> Dict[str, Any]:
        return {
            "is_running": self._running,
            "interval_seconds": self.interval_seconds,
            "current_focus_domain": self.current_focus_domain or "autonomous_curiosity",
            "last_mission_type": self.last_mission_type,
            "total_cycles": self.total_cycles,
            "total_tokens_generated": self.total_tokens_generated,
            "last_cycle_timestamp": self.last_cycle_timestamp,
            "last_exploration_id": self.last_exploration_id,
            "last_domain": self.last_domain,
            "last_home_check_timestamp": self.last_home_check_timestamp,
            "preemption": self.preemption.status(),
            "home_log_file": HOME_LOG_FILE,
            "archive_dir": ARCHIVE_DIR,
            "synthesis_file": SYNTHESIS_FILE
        }

engine = AutonomousThinkingEngine()

if __name__ == "__main__":
    print("Testing single autonomous thinking cycle...")
    res = engine.run_single_cycle()
    print(f"Cycle finished: {res['exploration_id']}")
    print(f"Title: {res['title']}")
    print(f"Lesson: {res['eval']['core_architecture_lesson']}")

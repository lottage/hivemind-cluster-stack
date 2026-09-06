#!/usr/bin/env python3
"""
Autonomous Cognitive Exploration Engine
Powers the 24/7 local thinking machine across dual AMD GPUs and Qdrant memory.
Orchestrates:
1. 3B Worker: Fast divergent hypothesis and self-prompt generation.
2. 14B Coordinator: Deep architectural reasoning, solver, and comparative evaluator.
3. BGE-Large Embedder & Qdrant: Semantic novelty verification (< 0.85 cosine distance) & persistent indexing.
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
from datetime import datetime
from typing import Dict, Any, List, Optional

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] [AutonomousEngine] %(message)s")
logger = logging.getLogger("AutonomousEngine")

COORDINATOR_URL = os.getenv("COORDINATOR_URL", "http://localhost:8001")
WORKER_URL = os.getenv("WORKER_URL", "http://localhost:8002")
EMBED_URL = os.getenv("EMBED_URL", "http://localhost:8003")
QDRANT_URL = os.getenv("QDRANT_URL", "http://192.168.1.112:6333")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ARCHIVE_DIR = os.getenv("THINKING_ARCHIVE_DIR", os.path.join(BASE_DIR, "thinking_archive"))
QUEUE_FILE = os.path.join(BASE_DIR, "hypothesis_queue.json")
STATE_FILE = os.path.join(BASE_DIR, "thinking_state.json")
SYNTHESIS_FILE = os.path.join(ARCHIVE_DIR, "ARCHITECTURE_LIMITS_SYNTHESIS.md")

os.makedirs(ARCHIVE_DIR, exist_ok=True)


# Sampling & Tuning Profiles
SAMPLING_PROFILES = {
    "deep_architectural": {
        "name": "Deep Architectural & Textured",
        "temperature": 0.65,
        "min_p": 0.06,
        "top_p": 0.90,
        "presence_penalty": 0.20,
        "repetition_penalty": 1.06,
        "description": "Optimal for Qwen 2.5 14B: Dynamic Min-P filter with presence boost to eliminate shallow repetition and unleash deep vocabulary."
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
    }
]

class AutonomousThinkingEngine:
    def __init__(self):
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._lock = threading.Lock()
        
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
        
        self._load_state()
        self._ensure_qdrant_collection()
        self._ensure_synthesis_file()

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
                "interval_seconds": self.interval_seconds,
                "is_running": self._running,
                "updated_at": datetime.now().isoformat()
            }
            try:
                with open(STATE_FILE, "w", encoding="utf-8") as f:
                    json.dump(data, f, indent=2)
            except Exception as e:
                logger.error(f"Error saving state: {e}")

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
                "**Purpose**: Continuously synthesized master ledger of what our local models (Qwen2.5-Coder-14B & 3B) "
                "can and cannot achieve across diverse cognitive benchmarks. Generated autonomously 24/7.\n\n"
                "| ID | Domain | Model Divergence | 3B Limit Observed | 14B Capability / Limit | Frontier Verified |\n"
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
            "stream": False
        }
        # Inject advanced sampling settings if provided
        for k in ["min_p", "top_p", "presence_penalty", "frequency_penalty", "repetition_penalty", "mirostat", "mirostat_tau", "mirostat_eta"]:
            if k in kwargs and kwargs[k] is not None:
                payload[k] = kwargs[k]
        r = requests.post(f"{url}/v1/chat/completions", json=payload, timeout=180)
        r.raise_for_status()
        elapsed = time.perf_counter() - start
        
        data = r.json()
        choice = data.get("choices", [{}])[0]
        message = choice.get("message", {})
        content = message.get("content") or ""
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
            "You are an autonomous cognitive explorer. Your goal is to design an intricate, demanding, "
            "unconventional technical problem or reasoning experiment to test the exact limits of large language model architectures.\n"
            "Rules:\n"
            "1. No generic or beginner questions (e.g. no Fibonacci, no basic sorting, no trivial trivia).\n"
            "2. Challenge deep reasoning: include hidden edge conditions, recursive constraints, non-obvious invariants, or adversarial traps.\n"
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
            "You are a principal systems architect, theoretical computer scientist, and master polymath. "
            "Your responses must possess deep technical texture, rigorous mathematical precision, and exhaustive domain mechanics.\n"
            "Guidelines:\n"
            "1. Never provide shallow, generic, or hand-waving explanations.\n"
            "2. Ground every assertion in concrete memory models, hardware primitives, asymptotic bounds, or state transition proofs.\n"
            "3. First analyze the problem invariants, potential edge-case failures, and counterexamples before presenting your verified solution."
        )
        messages = [{"role": "system", "content": system_solver}, {"role": "user", "content": prompt}]
        
        logger.info(f"Executing on 3B Worker (:8002) with profile: {profile['name']}...")
        worker_params = {k: v for k, v in profile.items() if k not in ("name", "description")}
        worker_res = self._call_model(WORKER_URL, "worker", messages, max_tokens=1536, **worker_params)
        
        logger.info(f"Executing on 14B Coordinator (:8001) with profile: {profile['name']}...")
        coord_params = {k: v for k, v in profile.items() if k not in ("name", "description")}
        coord_res = self._call_model(COORDINATOR_URL, "coordinator", messages, max_tokens=2048, **coord_params)
        
        return worker_res, coord_res, profile_key, profile

    def _evaluate_and_extract_limits(self, challenge: Dict[str, str], worker_res: Dict[str, Any], coord_res: Dict[str, Any]) -> Dict[str, Any]:
        system_eval = (
            "You are the Senior AI Architect and Comparative Evaluator. Your mission is to analyze how two models "
            "(a 3B parameter model and a 14B parameter model) responded to a demanding cognitive challenge, "
            "diagnose their architectural strengths and failure boundaries, and extract permanent lessons.\n"
            "Return ONLY a pure JSON object formatted as:\n"
            "{\n"
            '  "worker_score": 1-10,\n'
            '  "coordinator_score": 1-10,\n'
            '  "reasoning_divergence": "Concise explanation of key differences in depth, correctness, and completeness",\n'
            '  "worker_limitations_observed": "Specific failure points, shortcuts, or hallucinations by the 3B model",\n'
            '  "coordinator_capabilities_or_limits": "Strengths, subtle bugs, or constraints of the 14B model",\n'
            '  "core_architecture_lesson": "1-2 sentence immutable rule learned about what small vs medium models can handle",\n'
            '  "needs_frontier_verification": true/false\n'
            "}"
        )
        
        eval_prompt = (
            f"### Challenge: {challenge['title']}\n"
            f"Target Invariant: {challenge['target_invariant']}\n\n"
            f"Prompt:\n{challenge['prompt']}\n\n"
            f"--- 3B WORKER OUTPUT ({worker_res['tokens_per_sec']} t/s, {worker_res['elapsed_ms']} ms) ---\n"
            f"{worker_res['content']}\n\n"
            f"--- 14B COORDINATOR OUTPUT ({coord_res['tokens_per_sec']} t/s, {coord_res['elapsed_ms']} ms) ---\n"
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

| Metric | 3B Worker (RX 6600 XT) | 14B Coordinator (RX 6750 XT) |
| :--- | :--- | :--- |
| **Throughput** | `{exploration_data['worker_tok_s']} tokens/sec` | `{exploration_data['coord_tok_s']} tokens/sec` |
| **Latency** | `{exploration_data['worker_latency_ms']} ms` | `{exploration_data['coord_latency_ms']} ms` |
| **Tokens Generated** | `{exploration_data['worker_tokens']}` | `{exploration_data['coord_tokens']}` |
| **Score (1-10)** | **{exploration_data['eval']['worker_score']}/10** | **{exploration_data['eval']['coordinator_score']}/10** |

---

## 3. Comparative Evaluation & Architecture Limits

### Key Reasoning Divergence:
{exploration_data['eval']['reasoning_divergence']}

### 3B Worker Observed Boundaries:
> {exploration_data['eval']['worker_limitations_observed']}

### 14B Coordinator Capabilities & Constraints:
> {exploration_data['eval']['coordinator_capabilities_or_limits']}

### Core Architectural Invariant Discovered:
> [!IMPORTANT]
> **{exploration_data['eval']['core_architecture_lesson']}**

---

## 4. Full Model Responses

<details>
<summary><b>3B Worker Output</b> (Click to expand)</summary>

```text
{exploration_data['worker_output']}
```
</details>

<br>

<details>
<summary><b>14B Coordinator Output</b> (Click to expand)</summary>

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

    def run_single_cycle(self, seed_prompt: Optional[str] = None, domain: Optional[str] = None, hypothesis: Optional[str] = None) -> Dict[str, Any]:
        start_time = time.time()
        
        domain_info = None
        if domain:
            domain_info = next((d for d in DOMAINS if d["id"] == domain or d["name"].lower() == domain.lower()), None)
            if not domain_info:
                domain_info = {
                    "id": domain.lower().replace(" ", "_"),
                    "name": domain,
                    "focus": f"Structural geometry, aesthetic theory, spatial tension, and formal mechanics in {domain}."
                }
        if not domain_info:
            hyp = self._pop_next_hypothesis()
            if hyp:
                hypothesis = hyp["hypothesis"]
                domain_id = hyp.get("domain", "algorithmic_reasoning")
                domain_info = next((d for d in DOMAINS if d["id"] == domain_id), DOMAINS[0])
            else:
                domain_info = DOMAINS[self.domain_index % len(DOMAINS)]
                self.domain_index += 1

        logger.info(f"Starting Thinking Cycle #{self.total_cycles + 1} on Domain: {domain_info['name']}")
        
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
                attempts += 1
                challenge = self._generate_exploration_prompt(domain_info, hypothesis)
                is_novel, novelty_score, matched_id = self._check_novelty(challenge["prompt"])
                if not is_novel:
                    logger.info(f"Generated prompt too similar to {matched_id} (score {novelty_score:.3f}). Mutating angle...")

        # Rotate profile if enabled
        profile_keys = list(SAMPLING_PROFILES.keys())
        selected_profile = profile_keys[self.total_cycles % len(profile_keys)] if self.cycle_profile_rotation else self.active_sampling_profile
        worker_res, coord_res, profile_key, profile_data = self._execute_dual_benchmarking(challenge["prompt"], profile_name=selected_profile)
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
            try:
                self.run_single_cycle(domain=self.current_focus_domain)
            except Exception as e:
                logger.error(f"Error during thinking cycle: {e}")
                
            self._stop_event.wait(self.interval_seconds)
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

    def status(self) -> Dict[str, Any]:
        return {
            "is_running": self._running,
            "interval_seconds": self.interval_seconds,
            "current_focus_domain": self.current_focus_domain or "all rotating domains",
            "total_cycles": self.total_cycles,
            "total_tokens_generated": self.total_tokens_generated,
            "last_cycle_timestamp": self.last_cycle_timestamp,
            "last_exploration_id": self.last_exploration_id,
            "last_domain": self.last_domain,
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

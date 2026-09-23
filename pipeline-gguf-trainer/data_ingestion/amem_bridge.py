#!/usr/bin/env python3
"""
A-MEM (Agentic Working Memory) Curation Bridge
Connects the Dual-Gate Curation Cycle to the in-RAM Valkey Store (:6379).

Purpose:
When an issue, invariant, or bugfix is approved by both Gate 1 (Frontier Audit)
and Gate 2 (Human Operator), model weights have not been changed yet.
The A-MEM Bridge immediately distills the verified resolution into an
ultra-dense Zettelkasten Atomic Card (< 35 tokens) and pushes it to Valkey RAM.

Any model (StoneSage, Assembly Hall, Cluster Worker, Coordinator) querying
the cluster receives this knowledge atom in < 1.0 ms with zero reasoning bloat,
providing an immediate bridge to deliver gains to the user before QLoRA training.
"""

import os
import re
import json
import time
import logging
from typing import Dict, Any, List, Optional, Tuple

logger = logging.getLogger("AMEM-Bridge")

STOPWORDS = {
    "a", "an", "the", "is", "are", "was", "were", "what", "which", "who",
    "how", "why", "where", "when", "does", "do", "did", "can", "could",
    "should", "would", "to", "in", "on", "at", "by", "for", "with", "about",
    "of", "and", "or", "not", "my", "your", "his", "her", "their", "our",
    "it", "this", "that", "these", "those", "i", "you", "he", "she", "we", "they"
}

class AMEMBridge:
    def __init__(
        self,
        valkey_host: Optional[str] = None,
        valkey_port: Optional[int] = None,
        backup_path: str = "./data/processed/curated_amem_cards.json"
    ):
        self.valkey_host = valkey_host or os.environ.get("VALKEY_HOST", "127.0.0.1")
        self.valkey_port = valkey_port or int(os.environ.get("VALKEY_PORT", 6379))
        self.backup_path = backup_path
        os.makedirs(os.path.dirname(self.backup_path), exist_ok=True)
        self.r = None
        self._local_cards: Dict[str, Dict[str, Any]] = self._load_local_cards()
        self._connect_valkey()

    def _connect_valkey(self):
        try:
            import redis
            client = redis.Redis(
                host=self.valkey_host,
                port=self.valkey_port,
                socket_timeout=1.5,
                socket_connect_timeout=1.5,
                decode_responses=True
            )
            if client.ping():
                self.r = client
                logger.info(f"Connected to Valkey RAM store at {self.valkey_host}:{self.valkey_port}")
        except Exception as e:
            logger.warning(f"Could not connect to Valkey at {self.valkey_host}:{self.valkey_port}: {e}. Using local card cache.")
            self.r = None

    def _load_local_cards(self) -> Dict[str, Dict[str, Any]]:
        if os.path.exists(self.backup_path):
            try:
                with open(self.backup_path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception as e:
                logger.warning(f"Failed to load local AMEM cards: {e}")
        return {}

    def _save_local_cards(self):
        with open(self.backup_path, "w", encoding="utf-8") as f:
            json.dump(self._local_cards, f, indent=2)

    def distill_sample_to_atom(self, sample: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Distills a frontier-audited and human-approved sample into an ultra-dense (< 35 tokens)
        Zettelkasten knowledge atom. Strips all meta-commentary, evaluation scores, and preamble.
        """
        sample_id = sample.get("id", f"sample_{int(time.time())}")
        prompt = sample.get("full_prompt") or sample.get("prompt", "")
        chosen = sample.get("chosen", "")
        domain = sample.get("domain", "general").strip().lower().replace(" ", "_")

        if not chosen:
            return None

        # 1. Look for explicit Refined Invariants or Invariant blocks
        atom_text = ""
        invariant_match = re.search(r"(?:Refined Architectural Invariant|Operational Invariant|Core Invariant)[:\s*]*\n*>*\s*([^\n\r]+)", chosen, re.IGNORECASE)
        if invariant_match:
            atom_text = invariant_match.group(1).strip().strip('"').strip("'").strip("> ")
        else:
            # Check for blockquote
            quote_match = re.search(r"\n>\s*([^\n\r]+)", chosen)
            if quote_match:
                candidate = quote_match.group(1).strip()
                if len(candidate) > 20 and not candidate.startswith("Audited By"):
                    atom_text = candidate

        # 2. Fallback: Extract first concise actionable statement from chosen
        if not atom_text:
            lines = [l.strip() for l in chosen.split("\n") if l.strip()]
            for line in lines:
                clean_line = re.sub(r"^[\*\-#\d\.\s>]+", "", line).strip()
                # Skip meta lines
                if clean_line.startswith(("Verdict:", "Audited By:", "Latency:", "Evaluation:", "Score:", "Frontier")):
                    continue
                if len(clean_line) > 25:
                    atom_text = clean_line
                    break

        if not atom_text:
            atom_text = chosen[:180].strip()

        # Enforce strict length boundary (< 220 chars / ~35-45 tokens)
        if len(atom_text) > 220:
            sentences = re.split(r"(?<=[.!?])\s+", atom_text)
            if sentences and len(sentences[0]) > 20:
                atom_text = sentences[0]
            else:
                atom_text = atom_text[:217].rsplit(" ", 1)[0] + "..."

        atom_text = atom_text.strip().strip(">").strip()

        # 3. Extract high-signal keywords / tags
        combined_text = f"{domain} {prompt} {atom_text}".lower()
        raw_tokens = re.findall(r"\b[a-zA-Z0-9_\-\.]{3,}\b", combined_text)
        tags = []
        for tok in raw_tokens:
            if tok not in STOPWORDS and tok not in tags:
                tags.append(tok)
            if len(tags) >= 12:
                break

        clean_domain = domain.replace("-", "_")
        slug_match = re.search(r"\b([a-zA-Z0-9]{3,15})\b", atom_text.lower())
        slug = slug_match.group(1) if slug_match else "rule"
        atom_id = f"curated.{clean_domain}.{slug}_{sample_id[-8:]}".lower()

        card = {
            "id": atom_id,
            "sample_id": sample_id,
            "atom": atom_text,
            "keywords": tags,
            "category": f"curated_{clean_domain}",
            "confidence": 1.0,
            "source": f"dual_gate_curation:{sample_id}",
            "created_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        }
        return card

    def store_atom(self, card: Dict[str, Any]) -> bool:
        """Stores the atomic card in Valkey RAM (:6379) and persists to local backup."""
        atom_id = card["id"].strip().lower()
        atom_text = card["atom"].strip()
        tags = [t.strip().lower() for t in card.get("keywords", []) if t.strip() and t.strip().lower() not in STOPWORDS]
        category = card.get("category", "curated")

        # 1. Push to Valkey RAM if connected
        if self.r:
            try:
                pipe = self.r.pipeline()
                pipe.set(f"amem:card:{atom_id}", json.dumps(card))
                pipe.sadd("amem:cards:all", atom_id)
                pipe.sadd("amem:cards:curated", atom_id)
                pipe.sadd(f"amem:category:{category}", atom_id)
                for t in tags:
                    pipe.sadd(f"amem:tag:{t}", atom_id)
                pipe.execute()
                logger.info(f"Stored atomic card '{atom_id}' in Valkey RAM store.")
            except Exception as e:
                logger.warning(f"Failed to store atom in Valkey: {e}")

        # 2. Update local cache
        self._local_cards[atom_id] = card
        self._save_local_cards()
        return True

    def sync_approved_sample(self, sample: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Distills an approved sample and stores it in A-MEM as an immediate operational bridge."""
        card = self.distill_sample_to_atom(sample)
        if card:
            self.store_atom(card)
            return card
        return None

    def sync_all_approved_from_registry(self, registry_data: Dict[str, Any]) -> int:
        """Iterates over all admitted samples in the curation registry and syncs them to A-MEM."""
        samples = registry_data.get("samples", {})
        synced_count = 0
        for sid, rec in samples.items():
            if rec.get("admitted_to_training") or (rec.get("gate1_passed") and rec.get("human_status") == "APPROVED"):
                card = self.sync_approved_sample(rec)
                if card:
                    synced_count += 1
        return synced_count

    def recall(self, query: str, max_atoms: int = 2) -> List[Dict[str, Any]]:
        """
        Sub-millisecond Atomic Recall.
        Extracts search terms, queries Valkey tag index or local cache, ranks by keyword density.
        """
        if not query or not query.strip():
            return []

        tokens = [
            t.lower() for t in re.findall(r"\b[a-zA-Z0-9_\-\.]{2,}\b", query)
            if t.lower() not in STOPWORDS
        ]
        if not tokens:
            return []

        scores: Dict[str, int] = {}

        if self.r:
            try:
                pipe = self.r.pipeline()
                for tok in tokens:
                    pipe.smembers(f"amem:tag:{tok}")
                results = pipe.execute()

                for tok, id_set in zip(tokens, results):
                    if id_set:
                        for cid in id_set:
                            weight = 3 if tok in cid else 1
                            scores[cid] = scores.get(cid, 0) + weight
            except Exception as e:
                logger.warning(f"Valkey recall error: {e}")

        # Fallback to local cards
        if not scores:
            for cid, card in self._local_cards.items():
                card_tags = set(card.get("keywords", []))
                for tok in tokens:
                    if tok in card_tags or tok in cid or tok in card.get("atom", "").lower():
                        scores[cid] = scores.get(cid, 0) + 1

        if not scores:
            return []

        sorted_ids = sorted(scores.keys(), key=lambda k: scores[k], reverse=True)
        top_ids = sorted_ids[:max_atoms]

        recalled = []
        for cid in top_ids:
            if self.r:
                try:
                    data = self.r.get(f"amem:card:{cid}")
                    if data:
                        recalled.append(json.loads(data))
                        continue
                except Exception:
                    pass
            card = self._local_cards.get(cid)
            if card:
                recalled.append(card)

            try:
                with open(self.backup_path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception as e:
                logger.warning(f"Failed to load local AMEM cards: {e}")
        return {}

    def _save_local_cards(self):
        with open(self.backup_path, "w", encoding="utf-8") as f:
            json.dump(self._local_cards, f, indent=2)

    def distill_sample_to_atom(self, sample: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Distills a frontier-audited and human-approved sample into an ultra-dense (< 35 tokens)
        Zettelkasten knowledge atom. Strips all meta-commentary, evaluation scores, and preamble.
        """
        sample_id = sample.get("id", f"sample_{int(time.time())}")
        prompt = sample.get("full_prompt") or sample.get("prompt", "")
        chosen = sample.get("chosen", "")
        domain = sample.get("domain", "general").strip().lower().replace(" ", "_")

        if not chosen:
            return None

        # 1. Look for explicit Refined Invariants or Invariant blocks
        atom_text = ""
        invariant_match = re.search(r"(?:Refined Architectural Invariant|Operational Invariant|Core Invariant)[:\s*]*\n*>*\s*([^\n\r]+)", chosen, re.IGNORECASE)
        if invariant_match:
            atom_text = invariant_match.group(1).strip().strip('"').strip("'").strip("> ")
        else:
            # Check for blockquote
            quote_match = re.search(r"\n>\s*([^\n\r]+)", chosen)
            if quote_match:
                candidate = quote_match.group(1).strip()
                if len(candidate) > 20 and not candidate.startswith("Audited By"):
                    atom_text = candidate

        # 2. Fallback: Extract first concise actionable statement from chosen
        if not atom_text:
            lines = [l.strip() for l in chosen.split("\n") if l.strip()]
            for line in lines:
                clean_line = re.sub(r"^[\*\-#\d\.\s>]+", "", line).strip()
                # Skip meta lines
                if clean_line.startswith(("Verdict:", "Audited By:", "Latency:", "Evaluation:", "Score:", "Frontier")):
                    continue
                if len(clean_line) > 25:
                    atom_text = clean_line
                    break

        if not atom_text:
            atom_text = chosen[:180].strip()

        # Enforce strict length boundary (< 220 chars / ~35-45 tokens)
        if len(atom_text) > 220:
            sentences = re.split(r"(?<=[.!?])\s+", atom_text)
            if sentences and len(sentences[0]) > 20:
                atom_text = sentences[0]
            else:
                atom_text = atom_text[:217].rsplit(" ", 1)[0] + "..."

        atom_text = atom_text.strip().strip(">").strip()

        # 3. Extract high-signal keywords / tags
        combined_text = f"{domain} {prompt} {atom_text}".lower()
        raw_tokens = re.findall(r"\b[a-zA-Z0-9_\-\.]{3,}\b", combined_text)
        tags = []
        for tok in raw_tokens:
            if tok not in STOPWORDS and tok not in tags:
                tags.append(tok)
            if len(tags) >= 12:
                break

        clean_domain = domain.replace("-", "_")
        slug_match = re.search(r"\b([a-zA-Z0-9]{3,15})\b", atom_text.lower())
        slug = slug_match.group(1) if slug_match else "rule"
        atom_id = f"curated.{clean_domain}.{slug}_{sample_id[-8:]}".lower()

        card = {
            "id": atom_id,
            "sample_id": sample_id,
            "atom": atom_text,
            "keywords": tags,
            "category": f"curated_{clean_domain}",
            "confidence": 1.0,
            "source": f"dual_gate_curation:{sample_id}",
            "created_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        }
        return card

    def store_atom(self, card: Dict[str, Any]) -> bool:
        """Stores the atomic card in Valkey RAM (:6379) and persists to local backup."""
        atom_id = card["id"].strip().lower()
        atom_text = card["atom"].strip()
        tags = [t.strip().lower() for t in card.get("keywords", []) if t.strip() and t.strip().lower() not in STOPWORDS]
        category = card.get("category", "curated")

        # 1. Push to Valkey RAM if connected
        if self.r:
            try:
                pipe = self.r.pipeline()
                pipe.set(f"amem:card:{atom_id}", json.dumps(card))
                pipe.sadd("amem:cards:all", atom_id)
                pipe.sadd("amem:cards:curated", atom_id)
                pipe.sadd(f"amem:category:{category}", atom_id)
                for t in tags:
                    pipe.sadd(f"amem:tag:{t}", atom_id)
                pipe.execute()
                logger.info(f"Stored atomic card '{atom_id}' in Valkey RAM store.")
            except Exception as e:
                logger.warning(f"Failed to store atom in Valkey: {e}")

        # 2. Update local cache
        self._local_cards[atom_id] = card
        self._save_local_cards()
        return True

    def sync_approved_sample(self, sample: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Distills an approved sample and stores it in A-MEM as an immediate operational bridge."""
        card = self.distill_sample_to_atom(sample)
        if card:
            self.store_atom(card)
            return card
        return None

    def sync_all_approved_from_registry(self, registry_data: Dict[str, Any]) -> int:
        """Iterates over all admitted samples in the curation registry and syncs them to A-MEM."""
        samples = registry_data.get("samples", {})
        synced_count = 0
        for sid, rec in samples.items():
            if rec.get("admitted_to_training") or (rec.get("gate1_passed") and rec.get("human_status") == "APPROVED"):
                card = self.sync_approved_sample(rec)
                if card:
                    synced_count += 1
        return synced_count

    def recall(self, query: str, max_atoms: int = 2) -> List[Dict[str, Any]]:
        """
        Sub-millisecond Atomic Recall.
        Extracts search terms, queries Valkey tag index or local cache, ranks by keyword density.
        """
        if not query or not query.strip():
            return []

        tokens = [
            t.lower() for t in re.findall(r"\b[a-zA-Z0-9_\-\.]{2,}\b", query)
            if t.lower() not in STOPWORDS
        ]
        if not tokens:
            return []

        scores: Dict[str, int] = {}

        if self.r:
            try:
                pipe = self.r.pipeline()
                for tok in tokens:
                    pipe.smembers(f"amem:tag:{tok}")
                results = pipe.execute()

                for tok, id_set in zip(tokens, results):
                    if id_set:
                        for cid in id_set:
                            weight = 3 if tok in cid else 1
                            scores[cid] = scores.get(cid, 0) + weight
            except Exception as e:
                logger.warning(f"Valkey recall error: {e}")

        # Fallback to local cards
        if not scores:
            for cid, card in self._local_cards.items():
                card_tags = set(card.get("keywords", []))
                for tok in tokens:
                    if tok in card_tags or tok in cid or tok in card.get("atom", "").lower():
                        scores[cid] = scores.get(cid, 0) + 1

        if not scores:
            return []

        sorted_ids = sorted(scores.keys(), key=lambda k: scores[k], reverse=True)
        top_ids = sorted_ids[:max_atoms]

        recalled = []
        for cid in top_ids:
            if self.r:
                try:
                    data = self.r.get(f"amem:card:{cid}")
                    if data:
                        recalled.append(json.loads(data))
                        continue
                except Exception:
                    pass
            card = self._local_cards.get(cid)
            if card:
                recalled.append(card)

        return recalled

    def format_memory_injection(self, query: str, max_atoms: int = 2) -> str:
        """Formats recalled atomic facts as a crisp, low-token header (< 35 tokens)."""
        atoms = self.recall(query, max_atoms=max_atoms)
        if not atoms:
            return ""

        if len(atoms) == 1:
            return f"[KNOWLEDGE ATOM]: {atoms[0]['atom']}"

        lines = ["[KNOWLEDGE ATOMS]:"]
        for a in atoms:
            lines.append(f"• {a['atom']}")
        return "\n".join(lines)

    def format_trigger_guardrail(self, prompt: str) -> str:
        """
        Recalls trigger avoidance cards matching the prompt to form a sub-35 token
        zero-latency runtime avoidance injection.
        """
        atoms = self.recall(prompt, max_atoms=2)
        if not atoms:
            return ""
        for a in atoms:
            if a.get("category") == "trigger_avoidance" or a.get("atom", "").startswith("AVOID"):
                return f"[RUNTIME TRIGGER GUARDRAIL]: {a['atom']}"
        return ""


if __name__ == "__main__":
    bridge = AMEMBridge()
    test_sample = {
        "id": "EXP-20260910-TEST",
        "domain": "systems_architecture",
        "full_prompt": "How should llama-server device arguments be passed for AMD Vulkan GPUs?",
        "chosen": "**Refined Architectural Invariant**:\n> llama-server requires explicit string identifiers '--device Vulkan0' and '--device Vulkan1'. Passing numeric integers crashes the argument parser."
    }
    card = bridge.sync_approved_sample(test_sample)
    print("[SUCCESS] Stored test atom:", json.dumps(card, indent=2))
    injection = bridge.format_memory_injection("Why did llama-server crash on device 0?")
    print("[RECALL RESULT]:\n", injection)

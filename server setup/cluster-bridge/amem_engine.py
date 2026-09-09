#!/usr/bin/env python3
"""
A-MEM (Agentic Memory) Engine for Dual-GPU Cluster & StoneSage
Backed by Valkey (In-RAM Key-Value Store on :6379) and Qdrant Vector Brain (:6333)

Implements Zettelkasten-inspired Atomic Knowledge Cards to eliminate reasoning bloat:
- Replaces 400+ token raw chunk dumps with ultra-dense 15-30 token [KNOWLEDGE ATOM] facts.
- Sub-millisecond keyword/tag intersection directly in RAM.
- Working scratchpad memory per agent/session.
- Zero defensive meta-instructions (eliminates the "you are not a car" identity confusion).
"""

import json
import logging
import os
import re
import time
import urllib.error
import urllib.request
from datetime import datetime
from typing import Any, Dict, List, Optional, Set

try:
    import redis
except ImportError:
    redis = None

logger = logging.getLogger("AMEM-Engine")

VALKEY_HOST = os.environ.get("VALKEY_HOST", "192.168.1.105")
VALKEY_PORT = int(os.environ.get("VALKEY_PORT", 6379))
QDRANT_URL = os.environ.get("QDRANT_URL", "http://192.168.1.112:6333")
EMBEDDER_URL = os.environ.get("EMBEDDER_URL", "http://192.168.1.105:8003/v1/embeddings")

STOPWORDS = {
    "a", "an", "the", "is", "are", "was", "were", "what", "which", "who",
    "how", "why", "where", "when", "does", "do", "did", "can", "could",
    "should", "would", "to", "in", "on", "at", "by", "for", "with", "about",
    "of", "and", "or", "not", "my", "your", "his", "her", "their", "our",
    "it", "this", "that", "these", "those", "i", "you", "he", "she", "we", "they"
}


class AMEMEngine:
    def __init__(self, host: str = VALKEY_HOST, port: int = VALKEY_PORT):
        self.host = host
        self.port = port
        self.r = None
        self._local_cards: Dict[str, Dict[str, Any]] = {}
        self._local_tags: Dict[str, Set[str]] = {}
        self._local_working: Dict[str, List[str]] = {}
        self._connect_valkey()
        self._seed_core_knowledge()

    def _connect_valkey(self):
        if redis is None:
            logger.warning("redis python library not installed, using in-memory fallback dictionary")
            return
        try:
            client = redis.Redis(
                host=self.host,
                port=self.port,
                socket_timeout=1.5,
                socket_connect_timeout=1.5,
                decode_responses=True
            )
            if client.ping():
                self.r = client
                logger.info(f"Connected to Valkey RAM store at {self.host}:{self.port}")
        except Exception as e:
            logger.warning(f"Could not connect to Valkey at {self.host}:{self.port}: {e}. Using fallback.")
            self.r = None

    def store_atom(
        self,
        atom_id: str,
        atom_text: str,
        keywords: List[str],
        category: str = "general",
        links: Optional[List[str]] = None,
        confidence: float = 1.0
    ) -> Dict[str, Any]:
        """Stores a Zettelkasten Atomic Card in Valkey RAM and index."""
        clean_id = atom_id.strip().lower()
        clean_text = atom_text.strip()
        tags = [k.strip().lower() for k in keywords if k.strip() and k.strip().lower() not in STOPWORDS]
        for part in re.split(r"[._\-]", clean_id):
            if part and part not in STOPWORDS and part not in tags:
                tags.append(part)

        card = {
            "id": clean_id,
            "atom": clean_text,
            "keywords": tags,
            "category": category,
            "links": links or [],
            "confidence": confidence,
            "access_count": 0,
            "updated_at": datetime.now().isoformat()
        }

        if self.r:
            try:
                pipe = self.r.pipeline()
                pipe.set(f"amem:card:{clean_id}", json.dumps(card))
                pipe.sadd("amem:cards:all", clean_id)
                pipe.sadd(f"amem:category:{category}", clean_id)
                for t in tags:
                    pipe.sadd(f"amem:tag:{t}", clean_id)
                pipe.execute()
                return card
            except Exception as e:
                logger.warning(f"Valkey store error: {e}")

        self._local_cards[clean_id] = card
        for t in tags:
            self._local_tags.setdefault(t, set()).add(clean_id)
        return card

    def get_atom(self, atom_id: str) -> Optional[Dict[str, Any]]:
        clean_id = atom_id.strip().lower()
        if self.r:
            try:
                data = self.r.get(f"amem:card:{clean_id}")
                if data:
                    return json.loads(data)
            except Exception:
                pass
        return self._local_cards.get(clean_id)

    def delete_atom(self, atom_id: str) -> bool:
        clean_id = atom_id.strip().lower()
        card = self.get_atom(clean_id)
        if not card:
            return False
        if self.r:
            try:
                pipe = self.r.pipeline()
                pipe.delete(f"amem:card:{clean_id}")
                pipe.srem("amem:cards:all", clean_id)
                for t in card.get("keywords", []):
                    pipe.srem(f"amem:tag:{t}", clean_id)
                pipe.execute()
                return True
            except Exception:
                pass
        self._local_cards.pop(clean_id, None)
        return True

    def recall(self, query: str, max_atoms: int = 2) -> List[Dict[str, Any]]:
        """
        Sub-millisecond Atomic Recall.
        Extracts search terms, queries Valkey tag index, ranks by keyword density.
        Returns top 1-2 dense atomic fact cards.
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

        if not scores:
            for tok in tokens:
                matched_ids = self._local_tags.get(tok, set())
                for cid in matched_ids:
                    weight = 3 if tok in cid else 1
                    scores[cid] = scores.get(cid, 0) + weight

        if not scores:
            return []

        sorted_ids = sorted(scores.keys(), key=lambda k: scores[k], reverse=True)
        top_ids = sorted_ids[:max_atoms]

        recalled = []
        for cid in top_ids:
            card = self.get_atom(cid)
            if card:
                recalled.append(card)

        return recalled

    def format_memory_injection(self, query: str, max_atoms: int = 2) -> str:
        """
        Formats recalled atomic facts as a crisp, low-token header.
        Overhead: 15-35 tokens. Zero defensive boilerplate.
        """
        atoms = self.recall(query, max_atoms=max_atoms)
        if not atoms:
            return ""

        if len(atoms) == 1:
            return f"[KNOWLEDGE ATOM]: {atoms[0]['atom']}"

        lines = ["[KNOWLEDGE ATOMS]:"]
        for a in atoms:
            lines.append(f"• {a['atom']}")
        return "\n".join(lines)

    # --- Working Scratchpad Memory (In-RAM) ---
    def push_working_memory(self, session_or_agent: str, note: str, max_items: int = 5):
        key = f"amem:working:{session_or_agent.strip().lower()}"
        item = f"[{time.strftime('%H:%M:%S')}] {note.strip()}"
        if self.r:
            try:
                self.r.lpush(key, item)
                self.r.ltrim(key, 0, max_items - 1)
                self.r.expire(key, 86400)
                return
            except Exception:
                pass
        items = self._local_working.setdefault(session_or_agent, [])
        items.insert(0, item)
        if len(items) > max_items:
            self._local_working[session_or_agent] = items[:max_items]

    def get_working_memory(self, session_or_agent: str) -> List[str]:
        key = f"amem:working:{session_or_agent.strip().lower()}"
        if self.r:
            try:
                return self.r.lrange(key, 0, -1) or []
            except Exception:
                pass
        return self._local_working.get(session_or_agent, [])

    # --- Pre-seeded Core Knowledge Base ---
    def _seed_core_knowledge(self):
        """Seeds essential factual atoms for cluster, vehicles, and smart home."""
        core_atoms = [
            (
                "cluster.topology.management_vip",
                "Proxmox Datacenter 'home' unified API VIP is https://192.168.1.245:8006 managing physical nodes pve (192.168.1.229) and bigserv (192.168.1.82).",
                ["proxmox", "pve", "bigserv", "cluster", "vip", "management", "api", "topology"],
                "cluster"
            ),
            (
                "cluster.hardware.gpu_coordinator",
                "Coordinator on RX 6750 XT 12GB (Vulkan0, :8001) runs Ornith-1.5-9B-OBLITERATED Q8_0 for complex architectural reasoning.",
                ["coordinator", "gpu", "rx6750xt", "6750", "vulkan0", "8001", "q8", "ornith", "12gb"],
                "hardware"
            ),
            (
                "cluster.hardware.gpu_worker",
                "Worker on RX 6600 XT 8GB (Vulkan1, :8002) runs Ornith-1.5-9B Q4_K_M for fast ideation and testing at 80+ tokens/sec.",
                ["worker", "gpu", "rx6600xt", "6600", "vulkan1", "8002", "q4", "8gb", "speed"],
                "hardware"
            ),
            (
                "cluster.hardware.embedder",
                "Embedder (:8003) runs bge-large-en-v1.5 producing 1024-d vectors with a strict 512-token context window.",
                ["embedder", "bge", "embedding", "8003", "vectors", "1024"],
                "hardware"
            ),
            (
                "cluster.services.qdrant",
                "Qdrant vector database is hosted on LXC 117 (192.168.1.112:6333) storing companion_profile, codebase_knowledge, and autonomous_thinking.",
                ["qdrant", "vector", "database", "memory", "112", "6333", "lxc117"],
                "cluster"
            ),
            (
                "cluster.services.couchdb_obsidian",
                "Obsidian LiveSync CouchDB is hosted on LXC 116 (192.168.1.230:5984) database 'obsidiannotes' with AES-256-GCM E2EE.",
                ["obsidian", "couchdb", "sync", "livesync", "notes", "vault", "116", "230", "5984"],
                "cluster"
            ),
            (
                "cluster.services.assembly_hall",
                "Sovereign Agent Assembly Hall server runs at http://192.168.1.105:8766 (ws://192.168.1.105:8766/ws) with multi-channel real-time agent streaming.",
                ["assembly", "hall", "assembly_hall", "8766", "channels", "agora", "streaming", "interagent"],
                "cluster"
            ),
            (
                "home.climate.nest_thermostat",
                "Nest Thermostat 9A6E is at 192.168.1.62, controlled via Home Assistant OS (VM 103 @ 192.168.1.82:8123).",
                ["nest", "thermostat", "climate", "hvac", "temperature", "haos", "8123"],
                "home_automation"
            ),
            (
                "home.energy.smart_plugs",
                "TP-Link KP125 energy plug is at 192.168.1.109:9999. GE smart plugs: B0BC (192.168.1.17), 1FB4 (192.168.1.111), EAF0 (192.168.1.143).",
                ["plug", "plugs", "kp125", "ge", "energy", "smart", "kasa"],
                "home_automation"
            ),
            (
                "vehicle.bmw.oil_spec",
                "BMW 328i (N20 engine) requires 5W-30 or 5W-40 full synthetic motor oil meeting BMW Longlife-01 (LL-01) specification.",
                ["bmw", "328i", "n20", "oil", "spec", "synthetic", "ll01", "5w30", "5w40", "motor", "engine"],
                "automotive"
            ),
            (
                "vehicle.bmw.spark_plugs",
                "BMW 328i (N20 engine) uses NGK SILZKBR8D8S laser iridium spark plugs gapped to 0.028-0.030 inches (torque to 23 Nm).",
                ["bmw", "328i", "spark", "plug", "plugs", "ngk", "gap", "torque", "n20"],
                "automotive"
            ),
            (
                "vehicle.bmw.coolant_spec",
                "BMW 328i uses blue BMW HT-12 / G48 coolant mixed 50/50 with distilled water. Never mix with generic green or orange coolant.",
                ["bmw", "328i", "coolant", "antifreeze", "g48", "ht12", "distilled", "radiator"],
                "automotive"
            ),
            (
                "operator.workstation.ip",
                "Windows development host is assigned local LAN IP 192.168.1.132, hosting StoneSage frontend and mobile harness.",
                ["workstation", "windows", "host", "132", "lan", "ip"],
                "cluster"
            )
        ]

        for atom_id, text, tags, cat in core_atoms:
            self.store_atom(atom_id, text, tags, category=cat)


_engine: Optional[AMEMEngine] = None

def get_amem_engine() -> AMEMEngine:
    global _engine
    if _engine is None:
        _engine = AMEMEngine()
    return _engine

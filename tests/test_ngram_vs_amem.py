"""
Unit & Comparative Benchmark Tests: N-Gram Speculative Cache vs. A-MEM (Valkey)
Evaluates differences in:
1. Input Prompt Compression & Reasoning Bloat Mitigation
2. Speculative Token Generation & Throughput Acceleration
3. Knowledge Mutation & Stale Pattern Invalidation
4. Dual-Layer Synergy (A-MEM Context Layer + N-Gram Decoding Layer)

NOTE: Generated for verification analysis. Do not execute automatically.
"""

import unittest
import time
import re
from typing import List, Dict, Tuple, Optional, Set


# ============================================================================
# 1. N-Gram Speculative Cache Engine Simulator (llama.cpp / vLLM PLD model)
# ============================================================================

class NGramCacheSimulator:
    """
    Simulates model-free N-gram speculative decoding (e.g. Prompt Lookup Decoding /
    llama.cpp ngram-mod / vLLM [ngram]).
    Operates at the token sequence level without a neural draft model.
    """
    def __init__(self, n_gram_size: int = 3, max_draft_tokens: int = 5):
        self.n = n_gram_size
        self.max_draft = max_draft_tokens
        self.table: Dict[Tuple[str, ...], List[str]] = {}

    @staticmethod
    def tokenize(text: str) -> List[str]:
        return re.findall(r"\b\w+\b|[^\w\s]", text)

    def build_from_context(self, text: str):
        """Indexes an existing prompt or document into an N-gram transition map."""
        tokens = self.tokenize(text)
        for i in range(len(tokens) - self.n):
            prefix = tuple(tokens[i : i + self.n])
            continuation = tokens[i + self.n : i + self.n + self.max_draft]
            if prefix not in self.table:
                self.table[prefix] = continuation

    def draft(self, current_tokens: List[str]) -> List[str]:
        """Proposes speculative draft tokens based on the current sequence tail."""
        if len(current_tokens) < self.n:
            return []
        tail = tuple(current_tokens[-self.n:])
        return self.table.get(tail, [])

    def verify_draft(self, draft: List[str], ground_truth_target: List[str]) -> Tuple[int, List[str]]:
        """
        Simulates target LLM single-pass verification.
        Returns: (accepted_count, accepted_tokens)
        """
        accepted = []
        for d, t in zip(draft, ground_truth_target):
            if d == t:
                accepted.append(d)
            else:
                break
        return len(accepted), accepted


# ============================================================================
# 2. A-MEM Working Memory Engine Simulator (Valkey :6379 Zettelkasten Atom)
# ============================================================================

class AMEMSimulator:
    """
    Simulates A-MEM Tier-0 Working Memory backed by Valkey RAM store.
    Provides sub-millisecond atomic card recall (< 35 tokens) and prompt distillation.
    """
    def __init__(self):
        self.cards: Dict[str, Dict[str, any]] = {}
        self.tag_index: Dict[str, Set[str]] = {}
        self.stopwords = {
            "what", "is", "the", "for", "a", "an", "and", "or", "in", "on", "of", "to"
        }

    def store_atom(self, atom_id: str, text: str, tags: List[str], is_core: bool = False):
        clean_tags = [t.lower().strip() for t in tags if t.lower().strip() not in self.stopwords]
        self.cards[atom_id] = {
            "id": atom_id,
            "atom": text.strip(),
            "tags": clean_tags,
            "is_core": is_core,
            "token_estimate": len(text.split())
        }
        for tag in clean_tags:
            self.tag_index.setdefault(tag, set()).add(atom_id)

    def recall(self, query: str, max_atoms: int = 1) -> List[Dict[str, any]]:
        query_words = [w.lower().strip("?!.,") for w in query.split() if w.lower() not in self.stopwords]
        scores: Dict[str, int] = {}
        for w in query_words:
            matched_ids = self.tag_index.get(w, set())
            for cid in matched_ids:
                scores[cid] = scores.get(cid, 0) + 1

        ranked = sorted(scores.keys(), key=lambda k: scores[k], reverse=True)[:max_atoms]
        return [self.cards[cid] for cid in ranked]

    def compile_lean_prompt(self, query: str) -> Tuple[str, int]:
        """Injects lean prompt + recalled atomic facts + Direct Answer directive."""
        atoms = self.recall(query, max_atoms=1)
        atom_text = f"\n[KNOWLEDGE ATOM]: {atoms[0]['atom']}" if atoms else ""
        prompt = (
            f"You are Operator AI. Direct factual answer only.\n"
            f"[Direct Answer Mode: Provide the factual answer directly without reasoning loop.]{atom_text}\n"
            f"User: {query}\n"
            f"Assistant:"
        )
        token_count = len(prompt.split())
        return prompt, token_count


# ============================================================================
# 3. Test Suite: Comparative Evaluation
# ============================================================================

class TestNGramVsAMEM(unittest.TestCase):
    def setUp(self):
        self.ngram_engine = NGramCacheSimulator(n_gram_size=3, max_draft_tokens=4)
        self.amem_engine = AMEMSimulator()

        # Seed knowledge in A-MEM
        self.amem_engine.store_atom(
            atom_id="bmw_n20_oil",
            text="BMW 328i (N20 engine) requires 5W-30 or 5W-40 synthetic oil meeting BMW LL-01 specification.",
            tags=["bmw", "328i", "n20", "oil", "specification"],
            is_core=True
        )

        # Legacy Un-Atomic RAG Context (700+ tokens of raw manuals, hardware topology, and defensive disclaimers)
        self.legacy_rag_context = (
            "System: You are an AI assistant hosted in Proxmox Datacenter home. Node 1 is pve (192.168.1.222) with dual AMD GPUs. "
            "VM 102 ubu compute host has coordinator on 8001 (Qwen2.5-Coder-14B on RX 6750 XT 12GB Vulkan0), worker on 8002 "
            "(Qwen2.5-Coder-3B on RX 6600 XT 8GB Vulkan1), embedder on 8003 (bge-large-en-v1.5 on RX 6600 XT Vulkan1). "
            "LXC 117 qdrant is vector database with 6 active collections. LXC 120 stonesage is orchestrator on port 8080. "
            "Node 2 is bigserv (192.168.1.245) running Home Assistant OS on VM 103, NAS on VM 115, kavita on 100, adguard on 101, "
            "jellyfin on 104, docker on 105, immich on 107, freshrss on 108, qbittorrent on 114, flaresolverr on 118, "
            "openwebui on 119, voice-services on 121. "
            "You are NOT a physical car or vehicle. You do NOT have an engine, wheels, pistons, or transmission. Do NOT claim you have car parts. "
            "Reference Manual Section 14.8: BMW Service Bulletins 2012-2016 for F30 platform sedans and tourings. "
            "The N20 engine utilizes an electronic oil level sensor. When performing maintenance, verify drain plug torque is 8Nm. "
            "Filter housing cap must be tightened to 25Nm. Acceptable oil viscosities include 5W-30 and 5W-40 conforming to BMW Longlife-01. "
            "Secondary coolant circuit operates at 105 degrees Celsius. Never open expansion tank while hot. "
            "User: What oil specification does the BMW 328i N20 require?\n"
            "Assistant: <think>"
        )

    # ------------------------------------------------------------------------
    # Test 1: Prompt Token Compression & Reasoning Bloat Mitigation
    # ------------------------------------------------------------------------
    def test_prompt_token_compression_amem_vs_raw(self):
        """
        A-MEM must compress the prompt to < 50 tokens, eliminating context pollution
        that triggers the 1,500-token <think> runaway.
        """
        query = "What oil specification does the BMW 328i N20 require?"
        lean_prompt, amem_tokens = self.amem_engine.compile_lean_prompt(query)
        legacy_tokens = len(self.legacy_rag_context.split())

        # A-MEM prompt must achieve at least 65% reduction in context window footprint
        compression_ratio = 1.0 - (amem_tokens / legacy_tokens)
        self.assertGreater(compression_ratio, 0.65)
        self.assertLessEqual(amem_tokens, 50)
        self.assertIn("[KNOWLEDGE ATOM]", lean_prompt)
        self.assertIn("[Direct Answer Mode", lean_prompt)

    # ------------------------------------------------------------------------
    # Test 2: Inability of N-Gram Cache to Prevent Reasoning Loops
    # ------------------------------------------------------------------------
    def test_ngram_cache_fails_to_stop_reasoning_monologue(self):
        """
        Demonstrates that N-gram caching merely accelerates repetitive loop tokens
        rather than preventing the circular <think> loop.
        """
        # Populate N-Gram cache with repeated existential reasoning loop tokens
        reasoning_loop_trace = (
            "<think> Let me see. The user is asking about oil. I am an AI assistant, not a car. "
            "I do not have an engine. But let me see. The user is asking about oil. "
            "I am an AI assistant, not a car. I do not have an engine. </think>"
        )
        self.ngram_engine.build_from_context(reasoning_loop_trace)

        # Trigger generation inside a loop
        current_stream = ["I", "am", "an"]
        drafted = self.ngram_engine.draft(current_stream)

        # The N-Gram cache enthusiastically drafts the next tokens in the circular reasoning loop!
        self.assertEqual(drafted, ["AI", "assistant", ",", "not"])

        # Invariant: N-gram cache does not check semantics or prevent runaway loops;
        # only A-MEM's prompt distillation prevents entering the loop in the first place.

    # ------------------------------------------------------------------------
    # Test 3: N-Gram Speculative Decoding Acceleration on Structured Output
    # ------------------------------------------------------------------------
    def test_ngram_speculative_acceleration_on_structured_json(self):
        """
        Demonstrates where N-Gram speculative caching excels: accelerating repetitive
        structured schema keys and boilerplate syntax.
        """
        template = (
            '{"status": "success", "cluster_node": "pve", "vram_free_mb": 12288, '
            '"status": "success", "cluster_node": "bigserv", "vram_free_mb": 8192}'
        )
        self.ngram_engine.build_from_context(template)

        # LLM emits repetitive JSON key
        current_output = NGramCacheSimulator.tokenize('{"status": "success", "cluster_node":')
        draft = self.ngram_engine.draft(current_output)

        # N-gram cache successfully predicts the repeated node key pattern
        expected_target = NGramCacheSimulator.tokenize(' "pve", "vram_free_mb":')
        accepted_len, accepted_tokens = self.ngram_engine.verify_draft(draft, expected_target)

        self.assertGreaterEqual(accepted_len, 2)
        self.assertEqual(accepted_tokens[:4], ['"', 'pve', '"', ','])

    # ------------------------------------------------------------------------
    # Test 4: Knowledge Invalidation & Stale Data Race Conditions
    # ------------------------------------------------------------------------
    def test_knowledge_update_freshness(self):
        """
        Demonstrates that A-MEM updates ground truth in RAM with zero stale delay,
        whereas an un-flushed N-gram cache retains stale, obsolete token patterns.
        """
        # Initial hardware port
        self.ngram_engine.build_from_context("Valkey in-RAM store is configured on port 6379 .")

        # Port migration occurs: changed to port 6380
        self.amem_engine.store_atom(
            atom_id="valkey_port",
            text="Valkey in-RAM store is configured on port 6380.",
            tags=["valkey", "ram", "port"],
            is_core=True
        )

        # 1. A-MEM returns immediate fresh truth
        recalled = self.amem_engine.recall("valkey port")
        self.assertIn("6380", recalled[0]["atom"])

        # 2. Un-flushed N-gram cache still speculates the stale, outdated port 6379
        stale_draft = self.ngram_engine.draft(["configured", "on", "port"])
        self.assertEqual(stale_draft[0], "6379")

    # ------------------------------------------------------------------------
    # Test 5: Synergistic Stack (A-MEM Input + N-Gram Output Decoding)
    # ------------------------------------------------------------------------
    def test_synergistic_dual_layer_pipeline(self):
        """
        Tests the optimal combination:
        Layer 1 (A-MEM): Generates lean, loop-free prompt (< 40 tokens).
        Layer 2 (N-Gram Speculation): Accelerates emission of the grounded factual tokens.
        """
        query = "What is the BMW N20 oil specification?"
        lean_prompt, prompt_tokens = self.amem_engine.compile_lean_prompt(query)

        # Index the lean prompt into the speculative cache
        self.ngram_engine.build_from_context(lean_prompt)

        # When the model starts answering: "BMW 328i (N20 engine) requires..."
        # It copies directly from the atomic card in prompt context
        gen_start = ["BMW", "328i", "("]
        draft = self.ngram_engine.draft(gen_start)

        expected_continuation = ["N20", "engine", ")", "requires"]
        accepted_count, accepted_tokens = self.ngram_engine.verify_draft(draft, expected_continuation)

        # The N-gram cache achieves 100% acceptance because the output directly quotes the A-MEM atom!
        self.assertEqual(accepted_count, 4)
        self.assertEqual(accepted_tokens, expected_continuation)


if __name__ == "__main__":
    print("Test file generated. Execution omitted as requested.")

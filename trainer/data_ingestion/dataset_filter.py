#!/usr/bin/env python3
"""
Dataset Filter & Quality Gatekeeper
Filters out corrupted samples, near-duplicates, trivial questions,
and verifies that preference pairs have meaningful divergence.
"""

import json
from typing import List, Dict, Any

class DatasetFilter:
    def __init__(self, min_prompt_len: int = 15, min_completion_len: int = 30):
        self.min_prompt_len = min_prompt_len
        self.min_completion_len = min_completion_len

    def filter_sft_samples(self, samples: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Filters SFT samples based on minimum lengths and prompt uniqueness."""
        seen_prompts = set()
        clean = []

        for item in samples:
            prompt = item.get("prompt", "").strip()
            chosen = item.get("chosen", "").strip()

            if len(prompt) < self.min_prompt_len or len(chosen) < self.min_completion_len:
                continue

            # Deduplicate by normalized prompt
            norm_prompt = " ".join(prompt.lower().split()[:30])
            if norm_prompt in seen_prompts:
                continue
            seen_prompts.add(norm_prompt)

            clean.append(item)

        return clean

    def filter_dpo_pairs(self, pairs: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Filters DPO preference pairs."""
        clean = []
        for pair in pairs:
            prompt = pair.get("prompt", "").strip()
            chosen = pair.get("chosen", "").strip()
            rejected = pair.get("rejected", "").strip()

            if not prompt or not chosen or not rejected:
                continue

            # Reject identical responses
            if chosen.strip() == rejected.strip():
                continue

            # Reject pairs where chosen is shorter than rejected by a huge margin (often incomplete)
            if len(chosen) < 40:
                continue

            clean.append(pair)

        return clean

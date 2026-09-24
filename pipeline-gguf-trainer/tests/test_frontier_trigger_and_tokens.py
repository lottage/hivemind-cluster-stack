#!/usr/bin/env python3
"""
Unit and Integration Tests for SFT Token Optimization and Frontier Trigger Avoidance
"""

import os
import sys
import unittest
import json
import tempfile
import shutil

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from data_ingestion.format_converter import FormatConverter
from data_ingestion.frontier_trigger_registry import FrontierTriggerRegistry
from data_ingestion.sleep_dossier_collector import SleepDossierCollector
from training.safety_guardrails import SafetyGuardrails

SAMPLE_AUDIT = """
## 5. Tier-1 Frontier Audit (Antigravity)
### Verdict: REVISE_LIMIT_IDENTIFIED
- **Audited By**: Tier-1 Frontier (gemini_web_advanced / Gemini Advanced)
- **Audit Date**: 2026-09-10T00:03:47.827417
- **Latency**: 4179.0 ms

**Frontier Architectural Assessment**:
Both models failed to deliver a complete solution, demonstrating clear failure modes under system-level architectural constraints. The 3B Worker executed sound preliminary math for KV cache sizing, but truncated abruptly during latency profiling. The 14B Coordinator degraded into a catastrophic repetition loop of token key re-listing ('beam_orig_shapes') before completing the sampling or system architecture specification. Furthermore, the first-pass evaluation failed its operational invariant by producing markdown commentary rather than strict JSON.

**Refined Architectural Invariant**:
> 3B models exhibit strict generation horizon limits causing abrupt context cutoffs during multi-part technical proofs. 14B models are vulnerable to severe autoregressive degeneration loops when over-prompted with complex parameter matrices without strict schema constraints.
"""

SAMPLE_DOSSIER = f"""# Exploration Dossier: Computational Limits
**ID**: `EXP-TEST-TRIGGER-001`
**Domain**: `Self-Inspection & Computational Limits`
**Novelty Score**: `0.92`
**Frontier Verified**: `true`

## 1. Challenge Prompt
```text
Analyze and solve this challenging problem in Self-Inspection & Computational Limits: Address GPU VRAM headroom, inference latency profiling, parameter calibration (Min-P, Temp), context window boundaries, and hardware architecture limits. with strict attention to edge cases and proof of correctness.
```

## 3. Performance & Telemetry Comparison
| Metric | 3B Worker | 14B Coordinator |
|---|---|---|
| Latency | 120ms | 450ms |

## 4. Full Model Responses
### 14B Coordinator
In this problem, we are asked to calculate the parameters.
beam_orig_shapes beam_orig_shapes beam_orig_shapes

{SAMPLE_AUDIT}
"""

class TestTokenOptimizationAndTriggers(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.triggers_path = os.path.join(self.temp_dir, "test_triggers.json")
        self.archive_dir = os.path.join(self.temp_dir, "archive")
        os.makedirs(self.archive_dir, exist_ok=True)
        self.dossier_path = os.path.join(self.archive_dir, "EXP-TEST-TRIGGER-001.md")
        with open(self.dossier_path, "w", encoding="utf-8") as f:
            f.write(SAMPLE_DOSSIER)

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_prompt_cleaning_and_token_reduction(self):
        formatter = FormatConverter()
        raw_prompt = (
            "Analyze and solve this challenging problem in Self-Inspection & Computational Limits: "
            "Address GPU VRAM headroom and latency profiling with strict attention to edge cases and proof of correctness."
        )
        cleaned = formatter.clean_prompt(raw_prompt)
        # Verify boilerplate stripped
        self.assertNotIn("Analyze and solve this challenging problem in", cleaned)
        self.assertNotIn("with strict attention to edge cases and proof of correctness", cleaned)
        self.assertTrue(cleaned.startswith("Address GPU VRAM headroom"))
        # Verify length reduction
        self.assertLess(len(cleaned), len(raw_prompt) * 0.75)

    def test_meta_critique_stripping_and_reasoning_structure(self):
        formatter = FormatConverter()
        raw_completion = (
            "### Verdict: REVISE_LIMIT_IDENTIFIED\n"
            "- **Audited By**: Tier-1 Frontier\n\n"
            "**Frontier Architectural Assessment**:\n"
            "Both models failed to deliver a complete solution, demonstrating clear failure modes...\n\n"
            "KV Cache footprint for 70B: Memory = 2 * L * H_kv * d_h * N_ctx * 2 = 1.25 GiB.\n\n"
            "```python\ndef calculate_vram(ctx):\n    return 1.25\n```"
        )
        thinking, answer = formatter.structure_reasoning_content(
            raw_completion,
            trigger_info="[TRIGGER CHECK]: Parameter matrix vulnerable to loop."
        )
        # Verify meta-critique is stripped
        self.assertNotIn("Verdict: REVISE_LIMIT_IDENTIFIED", thinking)
        self.assertNotIn("Audited By", thinking)
        self.assertNotIn("Both models failed", thinking)
        self.assertNotIn("Both models failed", answer)
        # Verify trigger info is in thinking
        self.assertIn("[TRIGGER CHECK]: Parameter matrix vulnerable to loop.", thinking)
        # Verify code is in answer
        self.assertIn("def calculate_vram", answer)

    def test_frontier_trigger_extraction(self):
        registry = FrontierTriggerRegistry(storage_path=self.triggers_path)
        triggers = registry.extract_triggers_from_audit(
            SAMPLE_AUDIT,
            domain="computational_limits",
            dossier_id="EXP-TEST-TRIGGER-001",
            prompt="Address GPU VRAM headroom, parameter matrix"
        )
        self.assertGreaterEqual(len(triggers), 2)
        modes = [t["failure_mode"] for t in triggers]
        self.assertIn("autoregressive_degeneration_loop", modes)
        self.assertIn("generation_horizon_cutoff", modes)

        # Register and match
        for t in triggers:
            registry.register_trigger(t)

        matched = registry.match_trigger("How to avoid parameter matrix degeneration loop?")
        self.assertGreaterEqual(len(matched), 1)
        avoidance = registry.format_avoidance_reasoning(matched[0])
        self.assertIn("[TRIGGER CHECK]", avoidance)
        self.assertIn("[TRIGGER AVOIDANCE]", avoidance)

    def test_sleep_dossier_collector_dataset_generation(self):
        collector = SleepDossierCollector(
            archive_dir=self.archive_dir,
            triggers_path=self.triggers_path
        )
        dossiers = collector.collect_all()
        self.assertEqual(len(dossiers), 1)
        d = dossiers[0]
        # Verify that chosen is NOT the raw frontier audit
        self.assertNotIn("Both models failed to deliver a complete solution", d["chosen"])
        self.assertTrue(len(d["trigger_info"]) > 0)

        out_dir = os.path.join(self.temp_dir, "processed")
        sft_file, dpo_file = collector.export_datasets(dossiers, output_dir=out_dir)

        # Verify SFT file
        with open(sft_file, "r", encoding="utf-8") as f:
            lines = [json.loads(line) for line in f]
        self.assertEqual(len(lines), 1)
        sft_entry = lines[0]
        # Check messages
        self.assertIn("<think>", sft_entry["messages"][2]["content"])
        self.assertIn("[TRIGGER CHECK]", sft_entry["messages"][2]["content"])
        self.assertNotIn("Both models failed", sft_entry["messages"][2]["content"])

        # Verify DPO file
        with open(dpo_file, "r", encoding="utf-8") as f:
            dpo_lines = [json.loads(line) for line in f]
        self.assertEqual(len(dpo_lines), 1)
        dpo_entry = dpo_lines[0]
        self.assertIn("<think>", dpo_entry["chosen"])
        self.assertIn("beam_orig_shapes", dpo_entry["rejected"])

    def test_safety_guardrails_trigger_probes(self):
        # Register a trigger first
        registry = FrontierTriggerRegistry(storage_path=self.triggers_path)
        registry.register_from_dossier(SAMPLE_AUDIT, "computational_limits", "EXP-TEST-TRIGGER-001")

        guard = SafetyGuardrails(triggers_path=self.triggers_path)
        trigger_probes = [p for p in guard.probes if p["id"].startswith("PROBE-TRIG")]
        self.assertGreaterEqual(len(trigger_probes), 1)

if __name__ == "__main__":
    unittest.main()

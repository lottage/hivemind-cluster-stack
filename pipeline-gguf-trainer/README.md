# Local GGUF Training Pipeline & Dual-Gate Curation Engine

Autonomous fine-tuning, preference alignment (DPO/GRPO), and GGUF quantization pipeline engineered for the homelab's dual AMD GPU infrastructure (RX 6750 XT 12GB + RX 6600 XT 8GB).

---

## 1. Core Architecture

The training pipeline automates the entire lifecycle of local open-weights model refinement:

1. **Multi-Source Data Ingestion**:
   - Parses autonomous exploration sleep dossiers from `/opt/cluster-bridge/thinking_archive/`.
   - Ingests user-submitted scripts, test suites, and documentation.
   - Harvests external technical URLs and papers with strict chunking (< 900 characters).
2. **Dual-Gate Curation Engine**:
   - **Gate 1 (Tier-1 Frontier Audit)**: Verified by Antigravity / Gemini 2.5 Pro to eliminate hallucinated proofs, syntax bugs, and circular desire loops.
   - **Gate 2 (Human-in-the-Loop Sign-off)**: Explicit operator approval required before dataset inclusion.
   - Automatically isolates unapproved items to `data/quarantine/`.
3. **Hardware-Optimized Training Envelope (20GB VRAM)**:
   - **RX 6750 XT 12GB**: Trains `Ornith-1.5-9B` using 4-bit NF4 QLoRA ($r=16, \alpha=32$), paged 8-bit AdamW, and gradient checkpointing (~8.2 GB peak VRAM).
   - **RX 6600 XT 8GB**: Hosts the frozen reference policy during DPO KL penalty computation.
4. **Safety Guardrails & Automatic Rollback**:
   - Evaluates 10 Locked Golden Invariant Probes (Identity, Hardware, Syntax, Math, Refusal).
   - If the post-training golden invariant score drops by $> 2\%$, the new adapter is aborted and automatically rolled back.
5. **GGUF Quantization & Zero-Downtime Deployment**:
   - Merges LoRA adapter into FP16 base weights.
   - Converts to GGUF and quantizes to `Q4_K_M` (for 80+ tok/s Worker) and `Q8_0` (for Coordinator).
   - Stages models to `/opt/models/` with timestamped `.bak` archives.

---

## 2. Directory Layout

```
pipeline-gguf-trainer/
├── config/
│   └── training_config.yaml       # Hardware allocation, QLoRA, and DPO configs
├── data/
│   ├── processed/                 # Curated SFT and DPO training datasets
│   ├── quarantine/                # Quarantined data awaiting audit
│   └── uploads/                   # Raw user uploads
├── data_ingestion/
│   ├── curation_gatekeeper.py     # Dual-Gate validation engine
│   ├── external_url_extractor.py  # Web scraper with < 900 char chunking
│   ├── real_world_feeder.py       # Bridges operator feedback into rumination
│   ├── rolling_passdown_manager.py# Master passdown context generator
│   └── sleep_dossier_collector.py # Exploration dossier parser
├── training/
│   ├── qlora_trainer.py           # 4-bit NF4 QLoRA SFT training loop
│   ├── rl_agent_trainer.py        # DPO preference and GRPO trainer
│   └── safety_guardrails.py       # 10 Locked Golden Invariant Probes
├── export/
│   ├── lora_merger.py             # Adapter weight fusion
│   └── gguf_exporter.py           # GGUF quantization (Q4_K_M, Q8_0)
├── integration/
│   └── cluster_bridge_connector.py# REST & MCP hooks for StoneSage
├── scripts/
│   ├── run_pipeline.py            # Master CLI orchestrator
│   ├── promote_model.py           # Safe production deployer
│   └── benchmark_tokens.py        # Throughput and latency benchmarking
└── tests/
    └── test_dryrun_ornith.py      # End-to-end 5-phase dry run test suite
```

---

## 3. Quick Start

### Step 3.1: Dry-Run Verification
Verify all data processing, curation gates, LoRA configs, and mock exports:
```powershell
python pipeline-gguf-trainer/scripts/test_dryrun_ornith.py
```

### Step 3.2: Run Full Training & Export Pipeline
```powershell
python pipeline-gguf-trainer/scripts/run_pipeline.py --config pipeline-gguf-trainer/config/training_config.yaml --step all
```

### Step 3.3: Invariant Inspection
Inspect the 10 Golden Safety Invariants from the terminal CLI:
```powershell
python -m harness.cli.main
# In the prompt:
/train invariants
```

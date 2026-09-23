# Architecture & Systems Engineering: GGUF LLM Training Pipeline

## 1. Overview & System Topology

The GGUF LLM Training Pipeline is a specialized, memory-efficient fine-tuning and alignment framework engineered to run directly on the homelab's dual AMD GPU infrastructure within a strict **20GB combined VRAM** constraint.

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                       MULTI-SOURCE DATA INGESTION                           │
├──────────────────────────┬──────────────────────────┬───────────────────────┤
│ 24/7 Deep Sleep Dossiers │  User Uploads (JSONL/MD) │ External URLs & Docs  │
│ (/thinking_archive/*.md) │     (./data/uploads/)    │ (Web / arXiv / Docs)  │
└────────────┬─────────────┴────────────┬─────────────┴───────────┬───────────┘
             │                          │                         │
             ▼                          ▼                         ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                   DATASET CURATION & QUALITY GATEKEEPER                     │
│  • Token length bounding (< 900 chars for BGE embedder alignment)           │
│  • Formatting to ChatML SFT and (prompt, chosen, rejected) DPO pairs        │
│  • Semantic novelty gatekeeping (cosine similarity threshold < 0.85)        │
└───────────────────────────────────────┬─────────────────────────────────────┘
                                        │
                                        ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                 TRAINING ENVELOPE (20GB VRAM DUAL-GPU MAPPING)              │
│                                                                             │
│  • RX 6750 XT (12GB, Vulkan0 / cuda:0):                                     │
│    - Primary QLoRA SFT and DPO Training Card                                │
│    - Ornith-1.5-9B (4-bit NF4 quantized base): 4.6 GB                       │
│    - LoRA Trainable Parameters (r=16, alpha=32): ~180 MB                    │
│    - Activations (Gradient Checkpointing, batch_size=1, seq=2048): ~2.8 GB   │
│    - Paged 8-bit AdamW Optimizer: ~360 MB                                   │
│    - Peak Allocated: ~8.0 - 8.5 GB (Leaving ~3.5 GB Headroom!)              │
│                                                                             │
│  • RX 6600 XT (8GB, Vulkan1 / cuda:1):                                      │
│    - Hosts Reference Policy Model during DPO KL penalty computation         │
│    - Or runs BGE embedder (:8003) & fast AST verification engine            │
│                                                                             │
│  • Ornith-1.5-35B-MoE Feasibility Analysis:                                 │
│    - Base 4-bit weights: ~18 - 20 GB VRAM                                   │
│    - Fits across both GPUs (12GB + 8GB) using PyTorch Accelerate / DDP     │
│    - Training requires CPU Offloading (`accelerate` offload_folder) for     │
│      optimizer states or targeting active expert linear layers only.        │
└───────────────────────────────────────┬─────────────────────────────────────┘
                                        │
                                        ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│               SAFETY SHIELD & GOLDEN INVARIANT VERIFICATION                 │
│  • 10 Locked Golden Invariant Probes (Identity, Hardware, Math, Safety)     │
│  • Automatic Rollback: If golden pass rate drops by > 2%, aborts training   │
│  • Zero-drift agent identity preservation                                   │
└───────────────────────────────────────┬─────────────────────────────────────┘
                                        │
                                        ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                           GGUF EXPORT & DEPLOYMENT                          │
│  • Merges LoRA adapter into 16-bit FP16 base weights                        │
│  • Converts to GGUF using llama.cpp convert_hf_to_gguf.py                   │
│  • Quantizes to Q4_K_M (for 80+ t/s Worker) and Q8_0 (Coordinator)         │
│  • Validates GGUF magic header, integrity, and inference latency            │
│  • Staged deployment to /opt/models/ with automatic backup                  │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 2. Hardware Allocation Matrix (20GB VRAM Envelope)

| Model Architecture | Base Quantization | Weights VRAM | LoRA & Opt VRAM | Activation VRAM | Total VRAM | Feasibility on Cluster |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **Ornith-1.5-9B** | 4-bit NF4 | 4.6 GB | 0.54 GB | 2.8 GB (seq=2048) | **~8.0 - 8.5 GB** | **Native Single-Card (RX 6750 XT 12GB)** |
| **Ornith-1.5-9B (DPO)** | 4-bit NF4 (Policy + Ref) | 9.2 GB | 0.54 GB | 3.2 GB (seq=2048) | **~13.0 GB** | **Dual-GPU Split (12GB GPU0 + 8GB GPU1)** |
| **Ornith-35B-MoE** | 4-bit NF4 | ~19.5 GB | 1.8 GB | ~6.5 GB | **~28 GB** | **Viable with CPU-Offload (`accelerate` offload)** |

---

## 3. Data Flow & Formats

1. **SFT ChatML JSONL**:
   ```json
   {
     "id": "EXP-20260907-092707-F97C",
     "messages": [
       {"role": "system", "content": "You are Ornith-1.5, a high-precision reasoning AI..."},
       {"role": "user", "content": "Design and implement an efficient algorithm for real-time image processing..."},
       {"role": "assistant", "content": "```cpp\n// High-throughput solution adhering to invariant\n```"}
     ]
   }
   ```
2. **DPO Preference JSONL**:
   ```json
   {
     "id": "EXP-20260907-092707-F97C",
     "prompt": "Design and implement an efficient algorithm for real-time image processing...",
     "chosen": "Rigorous solution with invariant proof and O(1) lock-free ring buffer...",
     "rejected": "Incomplete snippet with potential race conditions...",
     "score_delta": 2,
     "frontier_verified": true
   }
   ```

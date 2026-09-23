# Cluster Model Switcher

name: cluster-model-switcher
description: Orchestrates switching models on the local dual-GPU compute host (VM 102). Downloads, verifies, reconfigures systemd service parameters, and restarts llama-coordinator (:8001) or worker (:8002) with hardware-optimized Vulkan offload and KV cache flags, then automatically initiates parameter discovery and calibration in succession.

---

## Overview

This skill allows seamless, hands-free model swapping across the cluster. When the user requests a model swap (e.g. from Qwen 14B to Ornith 9B or any experimental GGUF), this skill:
1. Inspects available models in `/opt/models/` or downloads the target GGUF from Hugging Face with resume support.
2. Backs up the current active configuration to enable instant one-command rollback.
3. Configures `/etc/systemd/system/llama-coordinator.service` with optimal VRAM, context window, and quantization parameters.
4. Reloads systemd and restarts the inference daemon.
5. Verifies health and latency on `http://127.0.0.1:8001/health`.
6. Automatically queues and launches `model-parameter-discoverer` to calibrate the new model's hyperparameters without manual testing.

## Commands

### 1. List Available Models
```bash
python .agents/skills/cluster-model-switcher/switch_model.py --list
```

### 2. Switch to an Existing Local Model
```bash
python .agents/skills/cluster-model-switcher/switch_model.py --model /opt/models/my-model.gguf --context 16384 --auto-tune
```

### 3. Switch and Download from Hugging Face
Downloads Ornith 9B Q4_K_M or Q5_K_M directly to VM 102 and loads it:
```bash
python .agents/skills/cluster-model-switcher/switch_model.py --hf bartowski/deepreinforce-ai_Ornith-1.0-9B-GGUF --file deepreinforce-ai_Ornith-1.0-9B-Q5_K_M.gguf --context 16384 --auto-tune
```

### 4. Instant Rollback
Restores the previous stable model and service unit:
```bash
python .agents/skills/cluster-model-switcher/switch_model.py --rollback
```

## Hardware Configuration Matrix (RX 6750 XT 12GB)

| Model Size | Quantization | Context Window (`-c`) | Flash Attn | KV Cache (`-ctk`, `-ctv`) | Target Port |
| :--- | :--- | :---: | :---: | :---: | :---: |
| **9B (Ornith)** | `Q4_K_M` / `Q5_K_M` | `16384` (16k) | `on` | `q8_0` / `q8_0` | `:8001` (Vulkan0) |
| **14B (Qwen)** | `Q4_K_M` | `8192` - `12288` | `on` | `q8_0` / `q8_0` | `:8001` (Vulkan0) |
| **3B (Worker)** | `Q5_K_M` | `8192` | `on` | `q8_0` / `q8_0` | `:8002` (Vulkan1) |

## Safety Invariants

- **Vulkan Device Naming**: Always explicitly passes `--device Vulkan0` (never integer device IDs).
- **Service Verification**: Polls `/health` for up to 30s; if the new model fails to launch or crashes the Vulkan driver, it automatically rolls back to the previous stable service unit.

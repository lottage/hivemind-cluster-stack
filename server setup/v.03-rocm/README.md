# v.03-rocm: Parallel Dual-GPU ROCm 10 / HIP Cluster Architecture

## 1. Overview & Purpose

`v.03-rocm` is an isolated, side-by-side parallel deployment package of our local dual-GPU compute stack on Proxmox VM 102 (`192.168.1.105`).

While our baseline production instance `v.03` runs on the **Vulkan backend** (`-DGGML_VULKAN=ON` via RADV/Mesa), `v.03-rocm` leverages **AMD ROCm 10.0.0** and **TheRock** multi-architecture distribution to provide native HIP compilation for:
- **GPU 0**: AMD Radeon RX 6750 XT 12GB (LLVM target: `gfx1031`)
- **GPU 1**: AMD Radeon RX 6600 XT 8GB (LLVM target: `gfx1032`)

---

## 2. Complete File & Binary Isolation Matrix

To guarantee **zero downtime** and prevent any accidental breakage of the active production instance, all files, build directories, binaries, and systemd units are strictly isolated:

| Component | Active Production (`v.03` Vulkan) | Parallel Build (`v.03-rocm` HIP) | Isolation Strategy |
| :--- | :--- | :--- | :--- |
| **Source Directory** | `/opt/llama.cpp` | `/opt/llama.cpp-rocm` | Distinct git directories |
| **Binary Path** | `/usr/local/bin/llama-server` | `/usr/local/bin/llama-server-rocm` | Unique binary names |
| **Compiler / Runtime**| Mesa RADV / Vulkan SDK | ROCm 10 Core SDK / `hipcc` | Separate compilers & runtimes |
| **AMDGPU Targets** | Generic Vulkan queues | `gfx1031`, `gfx1032` fatbins | Native hardware ISA targeting |
| **MoE Unit** | `llama-moe.service` | `llama-moe-rocm.service` | Independent systemd units |
| **Coordinator Unit** | `llama-coordinator.service` | `llama-coordinator-rocm.service` | Independent systemd units |
| **Worker Unit** | `llama-worker.service` | `llama-worker-rocm.service` | Independent systemd units |
| **Embedder Unit** | `llama-embed.service` | `llama-embed-rocm.service` | Independent systemd units |

---

## 3. Quickstart Deployment Guide

### Step 1: Upload Package to VM 102
From your Windows workstation in PowerShell:
```powershell
.\server setup\v.03-rocm\deploy_v03_rocm.ps1
```

### Step 2: SSH into VM 102
```bash
ssh austin@192.168.1.105
cd /tmp/v.03-rocm
```

### Step 3: Install ROCm 10 Core Packages
```bash
./01_install_rocm10.sh
```
*Verifies that both `gfx1031` and `gfx1032` are recognized by `rocminfo`.*

### Step 4: Build Parallel HIP Binary
```bash
./02_build_rocm10_llamacpp.sh
```
*Builds `/usr/local/bin/llama-server-rocm` without modifying `/usr/local/bin/llama-server`.*

### Step 5: Register ROCm Systemd Services
```bash
./03_install_rocm_services.sh
```
*Registers `*-rocm.service` files into systemd without starting them.*

---

## 4. Operational Controls: Switching & Failsafe Rollback

Use `switch_stack.sh` to transition between stacks with automated health verification:

### Switch to ROCm 10 (MoE Mode)
```bash
./switch_stack.sh rocm moe
```
- Gracefully stops Vulkan services.
- Starts `llama-moe-rocm.service` and `llama-embed-rocm.service`.
- Polls `/health` on `:8001` and `:8003`.
- **Failsafe Rollback**: If health checks fail within 45 seconds, it automatically stops ROCm and restores the Vulkan baseline immediately.

### Switch to ROCm 10 (Dual-Model Mode)
```bash
./switch_stack.sh rocm dual
```
- Starts `llama-coordinator-rocm.service` (`:8001`), `llama-worker-rocm.service` (`:8002`), and `llama-embed-rocm.service` (`:8003`).

### Return to Production Vulkan Baseline
```bash
./switch_stack.sh vulkan moe
# or
./switch_stack.sh vulkan dual
```

### Check Running Stack Status
```bash
./switch_stack.sh status
```

---

## 5. Side-by-Side Empirical Benchmarking

Run the benchmark harness against either stack:
```bash
# Benchmark current stack on port 8001
python3 benchmark_v03_vs_rocm.py --host 192.168.1.105 --port 8001 --label ROCm-MoE --output rocm_benchmark.json
```
Measures:
- **TTFT (Time-to-First-Token)** across 256, 1024, 4096, and 8192 token contexts.
- **Prefill Throughput (`t/s`)**: Measures the speedup of native rocBLAS over Vulkan SPIR-V shaders.
- **Generation Throughput (`t/s`)**: Confirms decode velocity and stability.

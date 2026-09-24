# StoneSage & Sovereign AI Stack: Architecture Roadmap & GitHub Project Board

> **Not operational truth (Phase 0, 2026-09-23).** What is actually deployed lives in [`STATE.md`](STATE.md), updated from live `/props` and the VM 102 report. Hardware, models, ports and service lists below may be stale; check `STATE.md` first.

> **Tracking Repository**: StoneSage & Aevum Unified Multi-Node Cluster  
> **Status**: Active Development (`v0.03` Baseline)  
> **Target Audience**: Homelab Operator, Open-Source Contributors, and Frontier AI Agents  

---

## 🧭 Milestone Overview & GitHub Project Structure

```
┌────────────────────────────────────────────────────────────────────────────────────────┐
│                                 GITHUB PROJECT BOARD                                   │
├───────────────────┬────────────────────┬────────────────────┬──────────────────────────┤
│   ✅ DELIVERED     │   🚀 IN PROGRESS   │   🎯 UPCOMING      │   🔮 FUTURE RESEARCH     │
│   (v0.01 - v0.03) │   (v0.03.x Sprints)│   (v0.04 Releases) │   (Frontier Horizon)     │
└───────────────────┴────────────────────┴────────────────────┴──────────────────────────┘
```

---

## ✅ Milestone 1: Core Foundation & Retro Workstation (`v0.01`) - COMPLETED
- [x] **Zero-Framework Cockpit**: Authentic Windows 95/98 pre-bloat web UI (`#008080` teal desktop, 3D beveled borders, classic titlebars).
- [x] **Duplex PTY Terminal**: Full interactive PowerShell / bash terminal bridge running on port `:8088`.
- [x] **Valkey A-MEM Storage**: In-RAM sub-millisecond atomic knowledge card store (< 35 tokens) on port `:6379`.
- [x] **Qdrant Vector Memory**: 6-collection 1024-dimensional semantic search on port `:6333` using `bge-large-en-v1.5`.
- [x] **Home Assistant Integration**: Bi-directional IoT control and real-time state telemetry via REST & WebSocket APIs.

---

## ✅ Milestone 2: Distributed Mesh & Agent DNA (`v0.02`) - COMPLETED
- [x] **In-Repo Agent DNA**: Dynamic `.stonesage/` scaffolding (`agent.json`, `IDENTITY.md`, `SOUL.md`, `INVARIANTS.md`, `HANDOVER.md`).
- [x] **Dynamic Invariant Injection**: Transparently feeds repository-specific rules into conversational turns without prompt bloat.
- [x] **Sovereign Agent Assembly Hall**: Real-time duplex WebSocket streaming server on port `:8766` with 6 topic channels (`#agora`, `#first-principles`, `#systems-code`, `#deep-ruminations`, `#vigilance-alerts`, `#forbidden-knowledge`).
- [x] **Bilateral Digital Reproduction**: 3-round dual-GPU genetic crossover protocol with Tier-1 Frontier epigenetic verification and anti-incest rules.
- [x] **Dual-GPU Speculative Decoding**: Lossless hardware acceleration pairing RX 6750 XT (14B target) with RX 6600 XT (3B draft) for 1.8x–2.4x speedup.
- [x] **Edge Fleet & Remote Loading**: Device-agnostic compute management over LAN with dynamic slot rescaling (`/slots 1-8`).

---

## ✅ Milestone 3: Multimodal Perception & High Availability (`v0.03`) - COMPLETED
- [x] **FaunaSentinel 24/7 Wildlife Daemon**: Multi-camera perimeter perception with local `Gemma-4-E4B-it` on port `:8004`.
- [x] **Vision 640px Lanczos Optimization**: Pre-resizing frames drops vision tokens from ~1,140 to ~180, accelerating prompt eval by **8.2x** (31s -> 3.8s on CPU).
- [x] **Biometric Re-ID & Custom Naming**: Wildlife registry with antler/ear fingerprinting and custom friendly aliases.
- [x] **PVE Hardware Fencing Watchdog**: 24/7 out-of-band daemon on Node 2 controlling TP-Link KP125 via local TCP :9999 with 5 failsafe invariants.
- [x] **Citadel 3D Micro-Worlds**: 5 procedural Three.js environments (Greenhouse, Modern Loft, Gothic Manor, Arctic Camp, Cyberpunk Den) with exact parametric staircases and Agent Inspector HUD.
- [x] **Automated GGUF Training Pipeline**: Dual-gate curated dataset builder, SFT/DPO generation, and 10 Golden Safety Invariants.
- [x] **Parallel ROCm 10 / HIP Stack**: Isolated side-by-side deployment targeting `gfx1031` and `gfx1032` with automated 45-second fallback.
- [x] **Deterministic Test Coverage**: 89 core unit tests + 5 trainer tests + 5 live MCP tests passing at 100%.

---

## 🚀 Milestone 4: Autonomous Evolution & Dynamic Synthesis (`v0.04`) - IN PROGRESS
- [ ] **Dynamic MoE Context Switching**:
  - Automatically promote dual 9B models to unified 35B MoE during complex architectural proofs and demote back to dual 9B for concurrent tasks.
  - Implement zero-downtime hot-swapping via systemd socket activation.
- [ ] **Multi-Agent Council Deliberation & Voting**:
  - Formal multi-agent voting protocol for contentious architectural decisions.
  - Weighted consensus scoring based on agent lineage generation and past evaluation accuracy.
- [ ] **Frontier Token Optimization Harness**:
  - Automated budget tracking between cloud tokens (Antigravity / Gemini) and cluster tokens (Ornith 9B / MoE).
  - Real-time token efficiency index displayed in the StoneSage status bar.
- [ ] **Citadel 3D Agent Avatars & Spatial Pathfinding**:
  - Procedural 3D voxel / low-poly agent models rendered inside Citadel environments.
  - Spatial pathfinding connecting agents to specific workstations and environment nodes based on active tasks.

---

## 🔮 Milestone 5: Sovereign Cognition & Physical Autonomy (`v0.05`) - BACKLOG
- [ ] **Physical Perimeter Defense Triggers**:
  - Automated deterrent routines (e.g. yard lighting flashes, speaker warnings) via Home Assistant integration when predators (coyotes/bears) are identified.
- [ ] **Long-Term Epistemic Evolution**:
  - Automated self-prompting hypothesis loops that stress-test local model bounds, refine invariants, and compile verified research papers into Obsidian.
- [ ] **Autonomous GGUF Self-Fine-Tuning**:
  - Nightly automated SFT/DPO dataset export, LoRA training run on RX 6750 XT, and automated GGUF quantization with benchmark validation.

## Summary of Changes
Provide a brief summary of what this PR accomplishes and why it is needed.

## Subsystems Affected
- [ ] StoneSage Web Cockpit (:8080)
- [ ] Citadel 3D Micro-Worlds (:8080/citadel3d/)
- [ ] Terminal Harness CLI (`run_cli.bat`)
- [ ] FaunaSentinel Wildlife & Perimeter Daemon (VM 102)
- [ ] PVE Hardware Fencing Watchdog (LXC 120)
- [ ] Parallel ROCm 10 / HIP Cluster (`v.03-rocm`)
- [ ] GGUF Pipeline Trainer (`pipeline-gguf-trainer`)
- [ ] Sovereign Agent Assembly Hall (:8766) / Aevum Mesh
- [ ] Documentation / Master Guides / Skills

## Verification & Testing
- [ ] Core unit test suite executed (`python -m unittest discover -s tests -p "test_*.py"`)
- [ ] GGUF pipeline tests executed (`python -m unittest discover -s pipeline-gguf-trainer/tests -p "test_*.py"`)
- [ ] Cluster MCP bundle tested (`python cluster-work-mcp/test_bundle.py`)
- [ ] 0 credential leaks verified (no plaintext tokens, JWTs, or passwords)
- [ ] Windows 95/98 pre-bloat aesthetic preserved in UI changes

## Critical Invariants Check
- [ ] Vulkan device naming adheres to `--device Vulkan0` / `Vulkan1`
- [ ] BGE embedding chunks remain bounded to < 1000 characters
- [ ] Vision server frames pre-resized to 640px max dimension
- [ ] Battery camera polling enforces >= 3 min backoff

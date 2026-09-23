---
name: homelab-deploy
description: Push code from this repo to the homelab and verify it. Use when deploying StoneSage to LXC 120, cluster-bridge (MCP bridge, wildlife sentry) to VM 102, changing llama-server systemd units, or collecting a live state report from VM 102.
---

# Homelab deploy

All commands run from the repo root (`C:\Users\johna\OneDrive\Documents\.ai`) on John's Windows box,
which has key-based SSH to every host. Use `ssh -n` for one-shot commands.

## 0. Always check live state first
```bash
scp "server setup/phase0_vm102_report.sh" austin@192.168.1.105:/tmp/phase0_vm102_report.sh
ssh -n austin@192.168.1.105 "bash /tmp/phase0_vm102_report.sh" > vm102_report.txt
```
Read `vm102_report.txt` and update `STATE.md` if anything differs from it.
`--apply` stops the thinking loop and Assembly Hall and creates `/etc/stonesage/secrets.env`; ask John before running it.

## 1. StoneSage -> LXC 120 (192.168.1.167, /opt/stonesage)
Preferred: `powershell -ExecutionPolicy Bypass -File "server setup/sync_stonesage_to_lxc.ps1"`
(copies frontend, backend *.py, harness/, data/agent_dna, restarts `stonesage.service`; it keeps the remote config.json).
Single file hotfix:
```bash
scp StoneSage/backend/server.py root@192.168.1.167:/opt/stonesage/backend/server.py
ssh -n root@192.168.1.167 "systemctl restart stonesage.service && sleep 2 && systemctl is-active stonesage.service"
curl -s -o /dev/null -w "%{http_code}\n" http://192.168.1.167:8888/   # expect 200
curl -s http://192.168.1.167:8888/api/status/markdown | head -20
```

## 2. cluster-bridge -> VM 102 (192.168.1.105, /opt/cluster-bridge)
Copy only Python and data, never blindly overwrite systemd units:
```bash
scp "server setup/cluster-bridge/mcp_server.py" "server setup/cluster-bridge/wildlife_sentry_daemon.py" austin@192.168.1.105:/tmp/
ssh -n austin@192.168.1.105 "sudo cp /tmp/mcp_server.py /tmp/wildlife_sentry_daemon.py /opt/cluster-bridge/ && sudo systemctl restart cluster-mcp wildlife-sentry && systemctl is-active cluster-mcp wildlife-sentry"
```
Do NOT use `sync_to_pve.ps1` as-is: it overwrites `llama-coordinator.service` with the repo copy,
which may be stale (the repo has had the wrong context size and GPU before).

## 3. llama-server unit changes (VM 102)
1. `ssh -n austin@192.168.1.105 "systemctl cat llama-coordinator"`: start from the LIVE unit, not the repo file.
2. Edit, show John the diff, then install with `sudo tee /etc/systemd/system/<unit>`, `daemon-reload`, `restart`.
3. Verify: `curl -s http://192.168.1.105:8001/props` (model_path, n_ctx, total_slots) and watch
   `journalctl -u <unit> -n 50`. Roll back to the saved live copy on failure.
4. Copy the final live unit back into `server setup/vm-setup/systemd/` so the repo matches reality.

## 4. After any deploy
- Run `curl` health checks for 8001-8004, 8765 and StoneSage.
- Update `STATE.md` (what changed, date).

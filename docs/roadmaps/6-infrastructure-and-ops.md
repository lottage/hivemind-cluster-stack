# Division 6: Infrastructure and ops (hosts, deploys, secrets, git, docs)

Part of [the master roadmap](../ROADMAP.md) (Phase 0 and the standing rules for everything else). Status wins over plans: see
[STATE.md](../../STATE.md).

**What it is:** the machines, the way code reaches them, and the hygiene that makes any change reversible.

**Where the code is:** `server setup/` (`vm-setup/`, `frigate/`, `metrics/`, `watchdog/`, `cluster-bridge/`,
`stonesage.service.d/`, sync scripts, `secrets.env.example`, `phase0_vm102_report.sh`); the `homelab-deploy` skill.

Hosts: Proxmox nodes pve (i7-12700K, two GPUs) and bigserv; VM 102 (engines, MCP bridge, sentry, Valkey); LXCs for StoneSage,
voice (Whisper, Kokoro, Piper), CouchDB, Qdrant, Frigate, metrics, and a Tailscale helper; HA OS VM.

## Where it is now
- A pve watchdog that power-cycles the node after 120 s of failed probes. Prometheus with 90-day retention. Boot race fixed
  (`wait-for-gpus.sh`). StoneSage runs on New York time (the container stays UTC).
- Repo state: a clean baseline plus a commit per session with a secret scan first; no commit attribution lines. The `github`
  remote is **public**; history was rewritten on 2026-09-25 to strip old secrets.

## Next, in order
1. **Trim the old docs.** README, PASSDOWN, README_LOCAL, GEMINI.md, SETUP_GUIDE, the root `ROADMAP.md` and the manifestos carry
   a banner pointing at STATE.md. Cut them to short, accurate stubs pointing at STATE.md, `docs/ROADMAP.md` and this folder.
   The philosophy docs stay, marked non-operational.
2. **Dead-code sweep** (with a backup first): stray media and scratch files at the repo root, `tinycpu_model/`,
   `pipeline-gguf-trainer/` outputs, unused skills; confirm each is unreferenced before removing.
3. **Diff before copying.** Compare repo unit files against `systemctl cat` on VM 102 before any copy; keep
   `server setup/vm-setup/systemd/` in sync after each live change.
4. **Storage watch.** bigserv `local` is 99.97 % full and local-lvm is overcommitted (558 GiB of thin volumes on a 475 GiB
   pool). Add a Prometheus alert before it bites.
5. **Secrets audit.** One search for tokens left in Qdrant points and Obsidian credential notes (the HA token sits in four
   points); exclude credential notes from vault ingestion. Delete the pre-change backups that still hold hardcoded
   credentials when John chooses. John has decided **not to rotate** the leaked credentials: do not raise it, but never leak them.
6. **Git flow.** One branch per feature, secret scan before every commit and every push, decide whether the public repo stays public.

## Later
- Re-index Qdrant `codebase_knowledge` from current files (25 stale snapshots with old IPs and layouts). Do **not** re-run
  `backup_to_qdrant.py`: it duplicates every document.
- A sandbox VM or LXC for the garden (Division 7).
- Splitting the tests into markers so unit tests can run in CI.

## Rules for this division
- Verify, don't assume: read `/props`, `systemctl cat`, logs. If a hardware fact is unknown, ask John.
- Secrets live only in `StoneSage/backend/config.json` (gitignored) and `/etc/stonesage/secrets.env` (or
  `/etc/watch-bridge.env`) on the hosts.
- Never end a quoted Windows path with `\` in scp/ssh arguments; use `ssh -n`; `MSYS_NO_PATHCONV=1` for `/opt/...` in Git Bash.
- Files written from Windows pipes get CRLF and silently corrupt unit files and env files: `.gitattributes` keeps host files LF.
- PowerShell `Out-File -Encoding utf8` adds a BOM: read JSON with `utf-8-sig`.
- Ask before root SSH to Proxmox nodes and before restarting anything John is using.

## Done when
A fresh machine could be rebuilt from the repo and STATE.md alone, no document contradicts another, and nothing sensitive is
one search away in Qdrant, git history or a backup folder.

#!/usr/bin/env python3
"""
Deploy N-gram Speculative Caching across all cluster LLM services on VM 102 (ubu).
Standardizes --spec-type ngram-mod across:
- llama-coordinator.service & llama-coordinator-rocm.service
- llama-worker.service & llama-worker-rocm.service
- llama-moe.service, templates, & llama-moe-rocm.service
Excludes llama-embed.service (embeddings have no generative token drafting).
"""

import glob
import os
import re
import subprocess
import sys
import time
import json
import urllib.request

SYSTEMD_DIR = "/etc/systemd/system"
NGRAM_FLAGS = (
    "--spec-type ngram-mod "
    "--spec-ngram-mod-n-min 16 "
    "--spec-ngram-mod-n-max 64 "
    "--spec-ngram-mod-n-match 24"
)

def update_service_file(filepath: str) -> bool:
    """Appends ngram-mod flags to ExecStart if not already present."""
    if not os.path.exists(filepath):
        return False

    with open(filepath, "r", encoding="utf-8") as f:
        content = f.read()

    if "--spec-type ngram-mod" in content:
        print(f"[-] Already configured: {os.path.basename(filepath)}")
        return False

    # Check if ExecStart is present
    if "ExecStart=" not in content:
        print(f"[!] No ExecStart in: {os.path.basename(filepath)}")
        return False

    # Check if multiline (ends with backslash) or single line
    lines = content.splitlines()
    new_lines = []
    in_exec = False
    exec_modified = False

    for i, line in enumerate(lines):
        if line.strip().startswith("ExecStart="):
            in_exec = True

        if in_exec:
            # Check if this is the last line of ExecStart (doesn't end with backslash)
            if not line.strip().endswith("\\"):
                # Single line or end of multiline ExecStart
                if " --model" in line or line.strip().startswith("ExecStart="):
                    # Append flags directly to the command
                    new_lines.append(f"{line} {NGRAM_FLAGS}")
                    exec_modified = True
                    in_exec = False
                    continue
            else:
                # Part of multiline ExecStart; check if next line is not a continuation
                if i + 1 < len(lines) and not lines[i + 1].strip().startswith("-") and not lines[i + 1].strip().startswith("/"):
                    # This is the last continuation line
                    new_lines.append(f"{line.rstrip()} \\")
                    indent = "    "
                    new_lines.append(f"{indent}{NGRAM_FLAGS}")
                    exec_modified = True
                    in_exec = False
                    continue

        new_lines.append(line)

    if not exec_modified:
        # Fallback: simple regex replacement on ExecStart
        def add_flags(m):
            return m.group(0) + " " + NGRAM_FLAGS
        content = re.sub(r"(ExecStart=[^\n\\]+)", add_flags, content, count=1)
        new_content = content
    else:
        new_content = "\n".join(new_lines) + "\n"

    with open(filepath, "w", encoding="utf-8") as f:
        f.write(new_content)

    print(f"[+] Updated: {os.path.basename(filepath)}")
    return True


def probe_health(url: str, max_wait: float = 30.0) -> bool:
    t0 = time.time()
    while time.time() - t0 < max_wait:
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Antigravity-Deployer"})
            with urllib.request.urlopen(req, timeout=2.0) as resp:
                if resp.status == 200:
                    data = json.loads(resp.read().decode())
                    if data.get("status") == "ok" or data.get("status") == "loading model":
                        if data.get("status") == "ok":
                            return True
        except Exception:
            pass
        time.sleep(1.0)
    return False


def main():
    if os.geteuid() != 0:
        print("ERROR: Must run as root (sudo).")
        sys.exit(1)

    print("=== [1/4] Scanning & Updating Systemd Service Files ===")
    pattern = os.path.join(SYSTEMD_DIR, "llama-*.service*")
    all_units = glob.glob(pattern)
    
    updated_files = []
    for unit in sorted(all_units):
        fname = os.path.basename(unit)
        # Skip embedder and backups
        if "embed" in fname or fname.endswith(".bak") or fname.endswith("~"):
            continue
        if update_service_file(unit):
            updated_files.append(fname)

    print(f"\nTotal units updated: {len(updated_files)}")

    print("\n=== [2/4] Reloading Systemd Daemon ===")
    subprocess.run(["systemctl", "daemon-reload"], check=True)

    print("\n=== [3/4] Gracefully Restarting Active Services ===")
    active_restarts = []

    # 1. Restart Coordinator (:8001)
    is_coordinator_active = subprocess.run(
        ["systemctl", "is-active", "--quiet", "llama-coordinator.service"]
    ).returncode == 0

    if is_coordinator_active:
        print("Restarting llama-coordinator.service...")
        subprocess.run(["systemctl", "restart", "llama-coordinator.service"], check=True)
        print("Waiting for Coordinator (:8001) health probe...")
        if probe_health("http://127.0.0.1:8001/health", max_wait=35.0):
            print("  -> Coordinator (:8001) is ONLINE and healthy!")
            active_restarts.append("llama-coordinator.service")
        else:
            print("  -> WARNING: Coordinator health probe timed out!")

    # 2. Restart Worker (:8002)
    is_worker_active = subprocess.run(
        ["systemctl", "is-active", "--quiet", "llama-worker.service"]
    ).returncode == 0

    if is_worker_active:
        print("Restarting llama-worker.service...")
        subprocess.run(["systemctl", "restart", "llama-worker.service"], check=True)
        print("Waiting for Worker (:8002) health probe...")
        if probe_health("http://127.0.0.1:8002/health", max_wait=30.0):
            print("  -> Worker (:8002) is ONLINE and healthy!")
            active_restarts.append("llama-worker.service")
        else:
            print("  -> WARNING: Worker health probe timed out!")

    print("\n=== [4/4] Verification Summary ===")
    print(f"Updated unit files: {len(updated_files)}")
    print(f"Services restarted & verified: {active_restarts}")
    print("Deployment of N-gram Speculative Caching complete.")


if __name__ == "__main__":
    main()

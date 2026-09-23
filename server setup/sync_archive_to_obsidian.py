"""
High-Speed Autonomous Thinking Dossier Synchronization to Obsidian Vault.
Uses streaming tar over SSH for sub-second atomic transfer, eliminating SFTP glob hangs and PowerShell binary pipe limitations.
"""

import os
import re
import sys
import tempfile
import subprocess
import time

VM_HOST = "192.168.1.105"
VM_USER = "austin"
REMOTE_DIRS = [
    "/opt/cluster-bridge/thinking_archive",
    "/home/austin/cluster-bridge/thinking_archive",
]
OBSIDIAN_VAULT_DIR = r"C:\Users\johna\OneDrive\Documents\obsidian\Autonomous Thinking"

def sync_dossiers():
    explorations_dir = os.path.join(OBSIDIAN_VAULT_DIR, "Explorations")
    os.makedirs(explorations_dir, exist_ok=True)

    print("=" * 60)
    print("  Sync Autonomous Thinking Dossiers -> Obsidian Vault")
    print("=" * 60)

    # 1. Find active remote dir
    active_remote = None
    for r_dir in REMOTE_DIRS:
        print(f"\n[1/2] Probing remote archive: {VM_USER}@{VM_HOST}:{r_dir}...")
        check_cmd = [
            "ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=4",
            f"{VM_USER}@{VM_HOST}", f"test -d '{r_dir}' && ls -1 '{r_dir}'/*.md 2>/dev/null | wc -l"
        ]
        try:
            res = subprocess.run(check_cmd, capture_output=True, text=True, timeout=6)
            count = int(res.stdout.strip() or 0)
            if count > 0:
                print(f"  Found {count} files in {r_dir}. Fetching via streaming tar...")
                active_remote = r_dir
                break
        except Exception as e:
            print(f"  Probe failed for {r_dir}: {e}")

    if not active_remote:
        print("No remote archive found or directory is empty.")
        return

    # 2. Stream tar over SSH to temp directory
    t0 = time.time()
    with tempfile.TemporaryDirectory() as tmp_dir:
        ssh_cmd = [
            "ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=5",
            f"{VM_USER}@{VM_HOST}", f"tar -czf - -C '{active_remote}' ."
        ]
        tar_cmd = ["tar", "-xzf", "-", "-C", tmp_dir]

        ssh_proc = subprocess.Popen(ssh_cmd, stdout=subprocess.PIPE)
        tar_proc = subprocess.Popen(tar_cmd, stdin=ssh_proc.stdout)
        ssh_proc.stdout.close()
        tar_proc.communicate()

        fetch_duration = round(time.time() - t0, 2)
        files = [f for f in os.listdir(tmp_dir) if f.endswith(".md")]
        print(f"  Transferred {len(files)} files in {fetch_duration}s!")

        if not files:
            print("No markdown files unpacked.")
            return

        print(f"\n[2/2] Ingesting {len(files)} files into Obsidian Vault ({OBSIDIAN_VAULT_DIR})...")
        synced_count = 0

        for fname in files:
            src_path = os.path.join(tmp_dir, fname)
            try:
                with open(src_path, "r", encoding="utf-8", errors="replace") as f:
                    content = f.read()

                if fname == "ARCHITECTURE_LIMITS_SYNTHESIS.md":
                    dest_path = os.path.join(OBSIDIAN_VAULT_DIR, fname)
                    rewritten = re.sub(
                        r'\[`?(EXP-[A-Za-z0-9\-]+)`?\]\((EXP-[A-Za-z0-9\-]+\.md)\)',
                        r'[`\1`](Explorations/\2)',
                        content
                    )
                    with open(dest_path, "w", encoding="utf-8") as out:
                        out.write(rewritten)
                    synced_count += 1
                elif "HOME" in fname and "VISION" in fname:
                    dest_path = os.path.join(OBSIDIAN_VAULT_DIR, "Home & Vision Activity Log.md")
                    with open(dest_path, "w", encoding="utf-8") as out:
                        out.write(content)
                    synced_count += 1
                else:
                    dest_path = os.path.join(explorations_dir, fname)
                    if "## 5. Tier-1 Frontier Audit (Antigravity)" in content:
                        verdict_match = re.search(r'### Verdict:\s*([A-Z_]+)', content)
                        if verdict_match:
                            verdict = verdict_match.group(1)
                            content = re.sub(
                                r'- \*\*Frontier Verified\*\*:.*',
                                f'- **Frontier Verified**: `True` ({verdict})',
                                content
                            )
                    with open(dest_path, "w", encoding="utf-8") as out:
                        out.write(content)
                    synced_count += 1
            except Exception as e:
                print(f"  Failed syncing {fname}: {e}")

        print("\n" + "=" * 60)
        print(f"  Sync Complete! {synced_count} dossiers synchronized to Obsidian.")
        print(f"  Vault: {OBSIDIAN_VAULT_DIR}")
        print("=" * 60)

if __name__ == "__main__":
    sync_dossiers()

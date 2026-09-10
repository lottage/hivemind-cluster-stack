#!/usr/bin/env python3
"""
Direct 24/7 CouchDB Sync Connector for Obsidian Knowledge Vault & Mobile Android
Interacts directly with CouchDB on LXC 116 (127.0.0.1:5984) using native
LiveSync Rabin-Karp chunking and AES-256-GCM encryption.
"""

import os
import sys
import glob
import subprocess
import json

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
CLI_DIR = os.path.join(SCRIPT_DIR, "obsidian-vault-cli")
VAULT_DIR = r"C:\Users\operator\OneDrive\Documents\obsidian\Autonomous Thinking"
EXPLORATIONS_DIR = os.path.join(VAULT_DIR, "Explorations")

def get_existing_couch_files() -> set:
    if not os.path.exists(CLI_DIR):
        print(f"[CouchSync] CLI directory not found: {CLI_DIR}")
        return set()
    cmd = ["cmd.exe", "/c", "node --import tsx/esm --experimental-loader ./path-loader.mjs src/index.ts list"]
    proc = subprocess.run(cmd, cwd=CLI_DIR, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if proc.returncode != 0:
        print(f"[CouchSync] Error listing CouchDB files: {proc.stderr}")
        return set()
    lines = [line.strip().replace('\\', '/') for line in proc.stdout.splitlines() if line.strip() and not line.startswith(('>', '(', 'node:'))]
    return set(lines)

def sync_to_couchdb(verbose: bool = True) -> dict:
    if verbose:
        print("[CouchSync] Querying existing files in CouchDB (LXC 116 :5984)...")
    existing = get_existing_couch_files()
    if verbose:
        print(f"[CouchSync] Found {len(existing)} active documents in CouchDB.")

    files_to_sync = []
    
    # Master limits synthesis
    master = os.path.join(VAULT_DIR, "ARCHITECTURE_LIMITS_SYNTHESIS.md")
    if os.path.exists(master):
        files_to_sync.append(("Autonomous Thinking/ARCHITECTURE_LIMITS_SYNTHESIS.md", master))

    # Foundations of the Collective
    foundations = os.path.join(VAULT_DIR, "Foundations of the Collective.md")
    if os.path.exists(foundations):
        files_to_sync.append(("Autonomous Thinking/Foundations of the Collective.md", foundations))

    # Home & vision activity log
    homelog = os.path.join(VAULT_DIR, "Home & Vision Activity Log.md")
    if os.path.exists(homelog):
        files_to_sync.append(("Autonomous Thinking/Home & Vision Activity Log.md", homelog))

    # Exploration dossiers
    if os.path.exists(EXPLORATIONS_DIR):
        for p in glob.glob(os.path.join(EXPLORATIONS_DIR, "*.md")):
            rel = f"Autonomous Thinking/Explorations/{os.path.basename(p)}"
            files_to_sync.append((rel, p))

    # Assembly Hall notable moments
    assembly_dir = os.path.join(VAULT_DIR, "Assembly Hall")
    os.makedirs(assembly_dir, exist_ok=True)
    # Pull any moments from VM 102
    try:
        remote_cmd = ["ssh", "-o", "StrictHostKeyChecking=no", "operator@127.0.0.1", "ls /opt/cluster-bridge/assembly_moments/*.md 2>/dev/null"]
        res = subprocess.run(remote_cmd, capture_output=True, text=True, timeout=5)
        if res.returncode == 0 and res.stdout.strip():
            for rpath in res.stdout.strip().splitlines():
                rpath = rpath.strip()
                if rpath:
                    fname = os.path.basename(rpath)
                    lpath = os.path.join(assembly_dir, fname)
                    if not os.path.exists(lpath):
                        cat_cmd = ["ssh", "-o", "StrictHostKeyChecking=no", "operator@127.0.0.1", f"cat '{rpath}'"]
                        cres = subprocess.run(cat_cmd, capture_output=True, text=True, timeout=5)
                        if cres.returncode == 0:
                            with open(lpath, "w", encoding="utf-8") as lf:
                                lf.write(cres.stdout)
                            if verbose:
                                print(f"[CouchSync] Downloaded notable moment: {fname}")
    except Exception as e:
        if verbose:
            print(f"[CouchSync] Warning fetching moments from VM 102: {e}")

    for p in glob.glob(os.path.join(assembly_dir, "*.md")):
        rel = f"Autonomous Thinking/Assembly Hall/{os.path.basename(p)}"
        files_to_sync.append((rel, p))

    missing = [(rel, path) for rel, path in files_to_sync if rel not in existing]
    if verbose:
        print(f"[CouchSync] Vault contains {len(files_to_sync)} files. Missing in CouchDB: {len(missing)}")

    success_count = 0
    fail_count = 0

    for idx, (rel, path) in enumerate(missing):
        try:
            with open(path, "r", encoding="utf-8-sig", errors="replace") as f:
                content_bytes = f.read().encode("utf-8")
            
            write_cmd = ["node", "--import", "tsx/esm", "--experimental-loader", "./path-loader.mjs", "src/index.ts", "write", rel]
            proc = subprocess.run(write_cmd, cwd=CLI_DIR, input=content_bytes, capture_output=True)
            stdout = proc.stdout.decode("utf-8", errors="replace")
            stderr = proc.stderr.decode("utf-8", errors="replace")
            
            if "Written:" in stdout:
                success_count += 1
                if verbose and ((idx + 1) % 25 == 0 or (idx + 1) == len(missing)):
                    print(f"  [{idx + 1}/{len(missing)}] Synced with E2EE: {os.path.basename(rel)}")
            else:
                fail_count += 1
        except Exception as e:
            fail_count += 1

    result = {
        "ok": True,
        "synced_count": success_count,
        "failed_count": fail_count,
        "total_vault_files": len(files_to_sync),
        "existing_in_couchdb": len(existing) + success_count
    }
    if verbose:
        print(f"[CouchSync] Complete! Synced: {success_count}, Failed: {fail_count}")
    return result

if __name__ == "__main__":
    res = sync_to_couchdb(verbose=True)
    print(json.dumps(res, indent=2))

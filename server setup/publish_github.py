#!/usr/bin/env python3
"""
Build a clean snapshot of `main` for the public GitHub repo (lottage/hivemind-cluster-stack).

Local history holds old credentials, so it must never be pushed. Instead each publish creates ONE new commit on the
local branch `github-publish`: its tree is `main`'s tree minus EXCLUDE, its only parent is the previous snapshot.
Nothing in the working tree or index is touched. Every blob is secret-scanned first; any hit aborts.

    python "server setup/publish_github.py"            # build/refresh the snapshot, print the push command
    git push github github-publish:main                 # then push (first time: add --force, it replaces old history)
"""
import os
import re
import subprocess
import sys
import tempfile
from datetime import datetime

SOURCE = "main"
PUBLISH_BRANCH = "github-publish"

# Paths (git pathspecs, relative to the repo root) that stay private and never reach the public repo.
EXCLUDE = [
    "server setup/cluster-bridge/agent_profiles", "StoneSage/datasets", "StoneSage/uploads", "data/agent_dna",
    ".claude/", "STATE.md", "couchdb.crt",
    # Home: street address, house model and property graph
    "3d_digital_twin", "server setup/spatial",
    # Family: names with physical descriptions, ethnicity, vehicles (importers cope with the files being absent)
    "harness/core/entity_profiles.py", "server setup/cluster-bridge/known_entities.json",
    # Device inventory: MAC addresses, phone/laptop IPs, personal memory seeds
    "server setup/NETWORK_DEVICE_REGISTRY.md", "server setup/backup_to_qdrant.py",
    # Operator notes: full LAN map with SSH logins and where secrets live (same reason as STATE.md)
    "CLAUDE.md", "GEMINI.md", "PROJECT_MASTER_PASSDOWN.md", "README_LOCAL.md",
    # Antigravity config (mirror of .claude/) plus copied third-party docs
    ".agents/",
]

SECRET_PATTERNS = {
    "JWT (e.g. HA long-lived token)": re.compile(rb"eyJ[A-Za-z0-9_-]{20,}\.[A-Za-z0-9_-]{20,}\.[A-Za-z0-9_-]{20,}"),
    "Proxmox API token secret": re.compile(rb"![A-Za-z0-9_-]+[=:][0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}"),
    "private key": re.compile(rb"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
    "GitHub/OpenAI/AWS key": re.compile(rb"ghp_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{30,}|sk-[A-Za-z0-9]{32,}|AKIA[0-9A-Z]{16}"),
    "password literal": re.compile(
        rb"""(?i)(password|passwd|pwd)["']?\s*[:=]\s*["'](?!(your|changeme|xxx|<|\$|\{))[^"'\s]{6,}["']"""),
}


def git(*args, env=None, data=None):
    res = subprocess.run(["git", *args], capture_output=True, env=env, input=data)
    if res.returncode:
        sys.exit(f"git {' '.join(args)} failed: {res.stderr.decode(errors='replace').strip()}")
    return res.stdout


def build_tree():
    """main's tree minus EXCLUDE and submodule links, built in a throwaway index."""
    with tempfile.TemporaryDirectory() as tmp:
        env = dict(os.environ, GIT_INDEX_FILE=os.path.join(tmp, "index"))
        git("read-tree", SOURCE, env=env)
        # Submodules point at commits that may exist only locally; the public repo gets no gitlinks.
        gitlinks = [l.split(b"\t", 1)[1].decode() for l in git("ls-files", "-s", env=env).splitlines() if l.startswith(b"160000")]
        for spec in EXCLUDE + gitlinks + [".gitmodules"]:
            git("rm", "--cached", "-r", "-q", "--ignore-unmatch", "--", spec, env=env)
        return git("write-tree", env=env).decode().strip()


def secret_scan(tree):
    hits = []
    for line in git("ls-tree", "-r", "-z", tree).split(b"\0"):
        if not line:
            continue
        meta, path = line.split(b"\t", 1)
        _, kind, sha = meta.split()
        if kind != b"blob":
            continue
        blob = git("cat-file", "blob", sha.decode())
        hits += [(name, path.decode()) for name, pat in SECRET_PATTERNS.items() if pat.search(blob)]
    return hits


def main():
    tree = build_tree()
    hits = secret_scan(tree)
    if hits:
        for name, path in hits:
            print(f"SECRET? {name}: {path}")
        sys.exit("Aborted: fix or EXCLUDE the files above (values are not printed).")

    prev = subprocess.run(["git", "rev-parse", "-q", "--verify", PUBLISH_BRANCH], capture_output=True, text=True).stdout.strip()
    if prev and git("rev-parse", f"{prev}^{{tree}}").decode().strip() == tree:
        print(f"{PUBLISH_BRANCH} already matches {SOURCE}; nothing to publish.")
        return
    src = git("rev-parse", "--short", SOURCE).decode().strip()
    msg = f"Snapshot of {SOURCE} {src} ({datetime.now():%Y-%m-%d %H:%M})"
    commit = git("commit-tree", tree, *(["-p", prev] if prev else []), "-m", msg).decode().strip()
    git("update-ref", f"refs/heads/{PUBLISH_BRANCH}", commit, *([prev] if prev else []))
    files = len(git("ls-tree", "-r", "--name-only", tree).splitlines())
    print(f"{PUBLISH_BRANCH} -> {commit[:7]}: {msg}, {files} files, secret scan clean.")
    print(f"Push with: git push {'--force ' if not prev else ''}github {PUBLISH_BRANCH}:main")


if __name__ == "__main__":
    main()

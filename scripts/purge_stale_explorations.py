#!/usr/bin/env python3
"""
scripts/purge_stale_explorations.py
Maintenance tool to purge synthetic test dossiers and transient test memories
while strictly preserving verified homelab architectural invariants and agent contracts.

Usage:
    python scripts/purge_stale_explorations.py --dry-run
    python scripts/purge_stale_explorations.py --execute
"""

import sys
import os
import json
import argparse
import urllib.request
import logging

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("PurgeStaleExplorations")

# Critical Invariant Keywords that must NEVER be purged under any circumstances
SACRED_INVARIANT_KEYWORDS = {
    "vulkan", "vulkan0", "vulkan1", "flash-attn", "bge", "512",
    "lanczos", "640px", "tc82", "tapo", "camera", "battery",
    "vip", "245", "8006", "proxmox", "bom", "utf-8", "utf8",
    "openssh", "backslash", "min-p", "min_p", "temperature",
    "qdrant", "valkey", "nest", "thermostat", "austin", "invariants",
    "core-memory", "agent_contract", "systems_architecture", "hardware"
}

def is_sacred(item_text: str, tags: list = None) -> bool:
    content = (item_text or "").lower()
    if tags:
        for t in tags:
            if str(t).lower() in SACRED_INVARIANT_KEYWORDS:
                return True
    for kw in SACRED_INVARIANT_KEYWORDS:
        if kw in content:
            return True
    return False

def check_qdrant_dossiers(qdrant_url: str = "http://192.168.1.112:6333", execute: bool = False):
    collection = "autonomous_thinking"
    logger.info(f"Probing Qdrant collection '{collection}' at {qdrant_url}...")
    try:
        req = urllib.request.Request(f"{qdrant_url}/collections/{collection}")
        with urllib.request.urlopen(req, timeout=3.0) as resp:
            info = json.loads(resp.read().decode("utf-8"))
            count = info.get("result", {}).get("points_count", 0)
            logger.info(f"Qdrant collection '{collection}' has {count} total points.")
    except Exception as e:
        logger.warning(f"Could not connect to Qdrant at {qdrant_url}: {e}")
        return

    # Scroll through points to identify test dossiers
    try:
        scroll_req = urllib.request.Request(
            f"{qdrant_url}/collections/{collection}/points/scroll",
            data=json.dumps({"limit": 100, "with_payload": True, "with_vector": False}).encode("utf-8"),
            headers={"Content-Type": "application/json"}
        )
        with urllib.request.urlopen(scroll_req, timeout=5.0) as resp:
            scroll_data = json.loads(resp.read().decode("utf-8"))
            points = scroll_data.get("result", {}).get("points", [])

        to_delete = []
        to_keep = []

        for pt in points:
            pid = pt.get("id")
            payload = pt.get("payload", {})
            title = payload.get("title", "")
            hypothesis = payload.get("hypothesis", "")
            tags = payload.get("tags", [])
            full_text = f"{title} {hypothesis}"

            if is_sacred(full_text, tags):
                to_keep.append((pid, title))
            elif "test" in full_text.lower() or "synthetic" in full_text.lower() or "dummy" in full_text.lower():
                to_delete.append((pid, title))
            else:
                to_keep.append((pid, title))

        logger.info(f"Points analyzed: {len(points)}. Preserved: {len(to_keep)}. Stale to delete: {len(to_delete)}.")

        for pid, t in to_delete:
            logger.info(f"  [STALE CANDIDATE]: ID={pid} | Title: {t}")

        if execute and to_delete:
            del_ids = [pid for pid, _ in to_delete]
            del_req = urllib.request.Request(
                f"{qdrant_url}/collections/{collection}/points/delete",
                data=json.dumps({"points": del_ids}).encode("utf-8"),
                headers={"Content-Type": "application/json"}
            )
            with urllib.request.urlopen(del_req, timeout=5.0) as del_resp:
                logger.info(f"✓ Purged {len(del_ids)} stale points from Qdrant '{collection}'.")
        elif not execute and to_delete:
            logger.info("[DRY RUN] Run with --execute to commit deletions.")
    except Exception as e:
        logger.error(f"Error during Qdrant inspection: {e}")

def check_valkey_cards(host: str = "192.168.1.105", port: int = 6379, execute: bool = False):
    logger.info(f"Probing Valkey A-MEM at {host}:{port}...")
    try:
        import redis
        client = redis.Redis(host=host, port=port, decode_responses=True, socket_timeout=2.0)
        keys = client.keys("amem:card:*")
        logger.info(f"Found {len(keys)} atomic cards in Valkey.")

        to_delete = []
        to_keep = []

        for k in keys:
            raw = client.get(k)
            if not raw:
                continue
            try:
                card = json.loads(raw)
            except Exception:
                continue

            cid = card.get("id", "")
            atom = card.get("atom", "")
            keywords = card.get("keywords", [])
            is_core = card.get("is_core_memory", False)

            if is_core or is_sacred(atom, keywords) or is_sacred(cid):
                to_keep.append(cid)
            elif "test" in cid.lower() or "synthetic" in atom.lower() or "dummy" in atom.lower():
                to_delete.append(cid)
            else:
                to_keep.append(cid)

        logger.info(f"Valkey cards analyzed: {len(keys)}. Preserved: {len(to_keep)}. Stale to delete: {len(to_delete)}.")

        for cid in to_delete:
            logger.info(f"  [VALKEY STALE]: {cid}")

        if execute and to_delete:
            for cid in to_delete:
                client.delete(f"amem:card:{cid}")
            logger.info(f"✓ Purged {len(to_delete)} stale atomic cards from Valkey.")
        elif not execute and to_delete:
            logger.info("[DRY RUN] Run with --execute to commit deletions.")

    except ImportError:
        logger.warning("redis-py not installed; skipping Valkey remote purge.")
    except Exception as e:
        logger.warning(f"Could not connect to Valkey at {host}:{port}: {e}")

def main():
    parser = argparse.ArgumentParser(description="Purge stale test dossiers and memories while preserving architectural invariants.")
    parser.add_argument("--dry-run", action="store_true", default=True, help="Perform dry run without deleting (default)")
    parser.add_argument("--execute", action="store_true", help="Execute actual deletion of stale records")
    args = parser.parse_args()

    execute_mode = args.execute

    print("=" * 64)
    print("  STONESAGE STALE EXPLORATION & MEMORY PURGE UTILITY")
    print(f"  Mode: {'[EXECUTE]' if execute_mode else '[DRY-RUN]'}")
    print("  Invariant Protection: STRICT (All core truths preserved)")
    print("=" * 64)

    check_qdrant_dossiers(execute=execute_mode)
    check_valkey_cards(execute=execute_mode)

    print("\n[Done] Invariant checks completed.")

if __name__ == "__main__":
    main()

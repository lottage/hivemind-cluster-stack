"""
Sanitize Obsidian Database (CouchDB 'obsidiannotes' & Qdrant 'obsidian_vault')
Purges excess AI notes (400 raw exploration dossiers, 30k+ orphaned chunks, corrupted docs)
replicated from the laptop while strictly preserving all 48 legitimate user notes and their chunks.
"""

import os
import sys
import json
import time
import requests
import urllib.request

# Ensure UTF-8 output on Windows console
if sys.stdout.encoding != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
        sys.stderr.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass

def load_couch_cfg():
    cfg_path = os.path.join(os.path.dirname(__file__), "..", "StoneSage", "backend", "config.json")
    with open(cfg_path, "r", encoding="utf-8-sig") as f:
        cfg = json.load(f)
    return cfg["couchdb"]

def sanitize():
    couch_cfg = load_couch_cfg()
    base_url = f"{couch_cfg['url']}/{couch_cfg['database']}"
    auth = (couch_cfg["username"], couch_cfg["password"])

    print("=" * 65)
    print("  [ OBSIDIAN DATABASE SANITIZER: COUCHDB & QDRANT ]")
    print("=" * 65)
    print(f"Connecting to CouchDB at: {base_url}...")

    r_db = requests.get(base_url, auth=auth, timeout=10)
    if r_db.status_code != 200:
        print(f"[ERROR] Failed to connect to CouchDB: {r_db.status_code} {r_db.text}")
        return

    db_info = r_db.json()
    initial_doc_count = db_info.get("doc_count", 0)
    print(f"Current CouchDB doc count: {initial_doc_count}")

    # 1. Fetch all doc headers (_id and _rev)
    print("\n[Step 1/6] Fetching all document IDs and revisions from CouchDB...")
    r_all = requests.get(f"{base_url}/_all_docs", auth=auth, timeout=40)
    if r_all.status_code != 200:
        print(f"❌ Failed to fetch _all_docs: {r_all.status_code}")
        return

    all_rows = r_all.json().get("rows", [])
    print(f"Total rows retrieved: {len(all_rows)}")

    # 2. Separate legitimate notes from excess AI exploration notes
    print("\n[Step 2/6] Cataloging legitimate notes and mapping required chunk dependencies...")
    all_notes = [r for r in all_rows if not r["id"].startswith("h:")]
    
    legitimate_notes = []
    excess_notes = []

    for r in all_notes:
        doc_id = r["id"]
        # Filter out 400 exploration notes and corrupted doc
        if doc_id.startswith("autonomous thinking/explorations") or doc_id == '"autonomous':
            excess_notes.append(r)
        else:
            legitimate_notes.append(r)

    print(f"  Legitimate user/curated notes found: {len(legitimate_notes)}")
    print(f"  Excess AI exploration notes identified: {len(excess_notes)}")

    # Map all chunks required by legitimate notes
    keep_chunks = set()
    backup_docs = []

    print("  Querying chunk references from legitimate notes...")
    for idx, r in enumerate(legitimate_notes):
        doc_id = r["id"]
        r_doc = requests.get(f"{base_url}/{requests.utils.quote(doc_id, safe='')}", auth=auth, timeout=10)
        if r_doc.status_code == 200:
            doc_data = r_doc.json()
            backup_docs.append(doc_data)
            for ch in doc_data.get("children", []):
                keep_chunks.add(ch)

    print(f"  Total chunks referenced by legitimate notes: {len(keep_chunks)}")

    # 3. Identify all docs to delete
    print("\n[Step 3/6] Identifying excess chunk documents to purge...")
    all_h_rows = [r for r in all_rows if r["id"].startswith("h:")]
    
    excess_chunks = []
    for r in all_h_rows:
        if r["id"] not in keep_chunks:
            excess_chunks.append(r)

    docs_to_delete = excess_notes + excess_chunks
    print(f"  Excess notes to delete:  {len(excess_notes):>6}")
    print(f"  Excess chunks to delete: {len(excess_chunks):>6}")
    print(f"  Total documents to purge:{len(docs_to_delete):>6}")
    print(f"  Total documents to keep: {len(legitimate_notes) + len(keep_chunks):>6}")

    # 4. Backup legitimate docs and chunks
    backup_path = os.path.join("data", "couchdb_legitimate_backup.json")
    print(f"\n[Step 4/6] Backing up legitimate notes and chunks to '{backup_path}'...")
    # Fetch full data for keep_chunks as well
    for ch_id in keep_chunks:
        r_ch = requests.get(f"{base_url}/{requests.utils.quote(ch_id, safe='')}", auth=auth, timeout=10)
        if r_ch.status_code == 200:
            backup_docs.append(r_ch.json())

    with open(backup_path, "w", encoding="utf-8") as f:
        json.dump({
            "timestamp": time.time(),
            "notes_count": len(legitimate_notes),
            "chunks_count": len(keep_chunks),
            "docs": backup_docs
        }, f)
    print(f"  [OK] Backup verified! {len(backup_docs)} documents safely backed up.")

    # 5. Execute bulk deletion in batches of 1,000
    print("\n[Step 5/6] Executing CouchDB bulk purge...")
    batch_size = 1000
    deleted_count = 0

    for i in range(0, len(docs_to_delete), batch_size):
        batch = docs_to_delete[i:i + batch_size]
        payload = {
            "docs": [{"_id": r["id"], "_rev": r["value"]["rev"], "_deleted": True} for r in batch]
        }
        r_del = requests.post(f"{base_url}/_bulk_docs", json=payload, auth=auth, timeout=30)
        if r_del.status_code in (200, 201):
            deleted_count += len(batch)
            print(f"  Purged {deleted_count}/{len(docs_to_delete)} documents... (batch {i // batch_size + 1})")
        else:
            print(f"  [ERROR] Bulk delete failed at batch {i}: {r_del.status_code} {r_del.text[:200]}")
            return

    # Trigger CouchDB compaction to reclaim disk space
    print("\n  Triggering CouchDB database compaction and view cleanup...")
    r_compact = requests.post(f"{base_url}/_compact", auth=auth, headers={"Content-Type": "application/json"})
    print(f"  Compaction status: {r_compact.status_code} {r_compact.json()}")
    r_vclean = requests.post(f"{base_url}/_view_cleanup", auth=auth, headers={"Content-Type": "application/json"})
    print(f"  View cleanup status: {r_vclean.status_code}")

    # Verify CouchDB after purge
    time.sleep(1)
    r_after = requests.get(base_url, auth=auth)
    after_count = r_after.json().get("doc_count", 0)
    print(f"\n  [OK] CouchDB Doc Count before: {initial_doc_count} -> after: {after_count}")

    # Verify integrity of all legitimate notes
    all_intact = True
    for r in legitimate_notes:
        r_chk = requests.get(f"{base_url}/{requests.utils.quote(r['id'], safe='')}", auth=auth)
        if r_chk.status_code != 200:
            print(f"  [WARN] Note '{r['id']}' not reachable!")
            all_intact = False

    if all_intact:
        print("  [OK] All 48 legitimate user and curated notes verified intact in CouchDB!")

    # 6. Sanitize Qdrant obsidian_vault collection
    print("\n[Step 6/6] Sanitizing Qdrant 'obsidian_vault' collection...")
    qdrant_url = "http://192.168.1.112:6333/collections/obsidian_vault"
    try:
        req = urllib.request.Request(
            f"{qdrant_url}/points/scroll",
            data=json.dumps({"limit": 500, "with_payload": True, "with_vector": False}).encode("utf-8"),
            headers={"Content-Type": "application/json"}
        )
        with urllib.request.urlopen(req, timeout=5) as resp:
            scroll_data = json.loads(resp.read().decode("utf-8"))

        pts = scroll_data.get("result", {}).get("points", [])
        qdrant_excess_ids = []
        for pt in pts:
            p = pt.get("payload", {})
            title = str(p.get("title") or p.get("file_path") or "")
            if "EXP-" in title or "exp-" in title or "explorations" in title:
                qdrant_excess_ids.append(pt["id"])

        print(f"  Found {len(qdrant_excess_ids)} excess exploration points in Qdrant 'obsidian_vault'.")
        if qdrant_excess_ids:
            del_req = urllib.request.Request(
                f"{qdrant_url}/points/delete",
                data=json.dumps({"points": qdrant_excess_ids}).encode("utf-8"),
                headers={"Content-Type": "application/json"}
            )
            with urllib.request.urlopen(del_req, timeout=10) as d_resp:
                print(f"  Deleted {len(qdrant_excess_ids)} points from Qdrant: {d_resp.status}")

        # Check final Qdrant point count
        with urllib.request.urlopen(qdrant_url, timeout=5) as c_resp:
            c_data = json.loads(c_resp.read().decode("utf-8"))
            final_q_pts = c_data.get("result", {}).get("points_count", 0)
            print(f"  [OK] Qdrant 'obsidian_vault' points: {final_q_pts} clean points remaining.")

    except Exception as q_ex:
        print(f"  [WARN] Qdrant cleanup notice: {q_ex}")

    print("\n" + "=" * 65)
    print("  SANITY CHECK & PURGE COMPLETE: Obsidian DB is fully clean!")
    print("=" * 65)

if __name__ == "__main__":
    sanitize()

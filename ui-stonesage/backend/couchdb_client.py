"""
CouchDB Client for StoneSage & Obsidian LiveSync
Interacts with the dedicated CouchDB instance on LXC 116 (127.0.0.1:5984)
managing the 'obsidiannotes' database.
"""

import os
import time
import json
import base64
import urllib.request
import urllib.error
import urllib.parse
from typing import Dict, Any, List, Optional

class CouchDBClient:
    def __init__(self, config: Dict[str, Any]):
        self.url = config.get("url", "http://127.0.0.1:5984").rstrip("/")
        self.username = config.get("username", "austin")
        self.password = config.get("password", "your_couchdb_password")
        self.database = config.get("database", "obsidiannotes")

    def _get_headers(self) -> Dict[str, str]:
        auth_bytes = f"{self.username}:{self.password}".encode("utf-8")
        auth_b64 = base64.b64encode(auth_bytes).decode("ascii")
        return {
            "Authorization": f"Basic {auth_b64}",
            "Accept": "application/json",
            "Content-Type": "application/json"
        }

    def get_status(self) -> Dict[str, Any]:
        """Check CouchDB instance and database health."""
        start = time.perf_counter()
        headers = self._get_headers()
        try:
            # 1. Probe root server
            root_req = urllib.request.Request(f"{self.url}/", headers=headers)
            with urllib.request.urlopen(root_req, timeout=3.0) as resp:
                root_data = json.loads(resp.read().decode("utf-8"))
            latency = round((time.perf_counter() - start) * 1000, 1)

            # 2. Probe database stats
            db_req = urllib.request.Request(f"{self.url}/{urllib.parse.quote(self.database)}", headers=headers)
            with urllib.request.urlopen(db_req, timeout=3.0) as resp:
                db_data = json.loads(resp.read().decode("utf-8"))

            return {
                "online": True,
                "latency_ms": latency,
                "version": root_data.get("version", "unknown"),
                "vendor": root_data.get("vendor", {}).get("name", "Apache CouchDB"),
                "database": self.database,
                "doc_count": db_data.get("doc_count", 0),
                "doc_del_count": db_data.get("doc_del_count", 0),
                "disk_size_mb": round(db_data.get("sizes", {}).get("file", 0) / (1024 * 1024), 2),
                "active_size_mb": round(db_data.get("sizes", {}).get("active", 0) / (1024 * 1024), 2),
                "update_seq": str(db_data.get("update_seq", ""))[:16]
            }
        except Exception as e:
            return {
                "online": False,
                "url": self.url,
                "database": self.database,
                "error": str(e)
            }

    def list_notes(self) -> List[Dict[str, Any]]:
        """
        List all note documents from the 'obsidiannotes' database.
        Excludes chunk leaves ('h:...') and internal metadata docs.
        """
        url = f"{self.url}/{urllib.parse.quote(self.database)}/_all_docs?include_docs=true"
        req = urllib.request.Request(url, headers=self._get_headers())
        notes = []
        try:
            with urllib.request.urlopen(req, timeout=5.0) as resp:
                data = json.loads(resp.read().decode("utf-8"))

            for row in data.get("rows", []):
                doc_id = row.get("id", "")
                # Skip chunks, designs, system or internal files
                if doc_id.startswith(("h:", "_design", "ix:", "t:", "$", "_local")) or "livesync_version" in doc_id.lower():
                    continue

                doc = row.get("doc", {})
                doc_type = doc.get("type", "")
                if doc_type == "leaf":
                    continue

                clean_path = doc.get("path") or doc_id
                # Skip non-markdown binary or internal index state files
                if clean_path.endswith((".bin", ".json", ".patch", ".zip")):
                    continue

                name = os.path.basename(clean_path)
                size = int(doc.get("size", 0)) if doc.get("size") else 0
                
                mtime_raw = doc.get("mtime")
                if mtime_raw:
                    try:
                        mtime_sec = float(mtime_raw) / 1000.0 if float(mtime_raw) > 1e11 else float(mtime_raw)
                        modified = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(mtime_sec))
                    except Exception:
                        modified = str(mtime_raw)
                else:
                    modified = "Unknown"

                notes.append({
                    "id": doc_id,
                    "name": name,
                    "path": clean_path.replace("\\", "/"),
                    "size_bytes": size,
                    "modified": modified,
                    "source": "couchdb",
                    "type": doc_type or "plain",
                    "rev": doc.get("_rev", "")
                })

            return sorted(notes, key=lambda x: x["path"].lower())
        except Exception as e:
            print(f"[CouchDBClient] Error listing notes: {e}")
            return []

    def get_note_doc(self, note_id_or_path: str) -> Optional[Dict[str, Any]]:
        """Fetch raw note document from CouchDB with case fallback."""
        headers = self._get_headers()
        candidates = [note_id_or_path, note_id_or_path.lower()]
        for cand in candidates:
            encoded_id = urllib.parse.quote(cand, safe="")
            url = f"{self.url}/{urllib.parse.quote(self.database)}/{encoded_id}"
            req = urllib.request.Request(url, headers=headers)
            try:
                with urllib.request.urlopen(req, timeout=4.0) as resp:
                    return json.loads(resp.read().decode("utf-8"))
            except Exception:
                continue
        return None

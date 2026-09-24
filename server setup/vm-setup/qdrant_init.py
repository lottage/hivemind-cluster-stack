#!/usr/bin/env python3
"""
Initialize Qdrant Collections for the Dual-GPU Multi-Agent Cluster.
Vector dimension: 1024 (BGE-Large-EN-v1.5)
Distance metric: Cosine
"""

import sys
import argparse
import json
import urllib.request
import urllib.error

try:
    from qdrant_client import QdrantClient
    from qdrant_client.models import Distance, VectorParams
    HAS_CLIENT = True
except ImportError:
    HAS_CLIENT = False

COLLECTIONS = {
    "codebase_knowledge": "Stores code snippets, functions, classes, and documentation vectors.",
    "agent_memories": "Stores architectural decisions, bug fixes, and persistent agent instructions.",
    "session_transcripts": "Stores compressed summaries of prior development sessions for cross-session recall.",
    "companion_profile": "Stores user preferences, personality alignment, communication style, and companion directives.",
    "home_automation_registry": "Stores Home Assistant entity IDs, device metadata, rooms, scenes, and automation configurations."
}

def init_qdrant(host: str = "localhost", port: int = 6333, vector_size: int = 1024):
    base_url = f"http://{host}:{port}"
    print(f"Connecting to Qdrant at {base_url}...")

    if HAS_CLIENT:
        client = QdrantClient(host=host, port=port)
        existing_collections = [c.name for c in client.get_collections().collections]
        print(f"Existing collections: {existing_collections}")

        for name, description in COLLECTIONS.items():
            if name in existing_collections:
                print(f"[OK] Collection '{name}' already exists.")
            else:
                print(f"[CREATE] Creating collection '{name}' ({description})...")
                client.create_collection(
                    collection_name=name,
                    vectors_config=VectorParams(size=vector_size, distance=Distance.COSINE)
                )
                print(f"[CREATED] Collection '{name}' initialized successfully.")
    else:
        # Fallback to zero-dependency REST API
        req = urllib.request.Request(f"{base_url}/collections")
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode())
            existing_collections = [c["name"] for c in data.get("result", {}).get("collections", [])]
        print(f"Existing collections: {existing_collections}")

        for name, description in COLLECTIONS.items():
            if name in existing_collections:
                print(f"[OK] Collection '{name}' already exists.")
            else:
                print(f"[CREATE] Creating collection '{name}' ({description})...")
                payload = json.dumps({
                    "vectors": {
                        "size": vector_size,
                        "distance": "Cosine"
                    }
                }).encode("utf-8")
                create_req = urllib.request.Request(
                    f"{base_url}/collections/{name}",
                    data=payload,
                    headers={"Content-Type": "application/json"},
                    method="PUT"
                )
                with urllib.request.urlopen(create_req, timeout=10) as c_resp:
                    print(f"[CREATED] Collection '{name}' initialized successfully (HTTP {c_resp.status}).")

    print("\nAll Qdrant collections verified!")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Initialize Qdrant collections.")
    parser.add_argument("--host", default="localhost", help="Qdrant host IP/domain (default: localhost)")
    parser.add_argument("--port", type=int, default=6333, help="Qdrant port (default: 6333)")
    args = parser.parse_args()
    init_qdrant(host=args.host, port=args.port)

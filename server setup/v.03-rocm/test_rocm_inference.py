import subprocess
import time
import urllib.request
import json
import os
import sys

def test_embed():
    print("--- Testing BGE Embedder on GPU 1 (RX 6600 XT) with HSA_OVERRIDE_GFX_VERSION=10.3.0 ---")
    env = os.environ.copy()
    env["HSA_OVERRIDE_GFX_VERSION"] = "10.3.0"
    env["HIP_VISIBLE_DEVICES"] = "1"

    proc = subprocess.Popen([
        "/usr/local/bin/llama-server-rocm",
        "--model", "/opt/models/bge-large-en-v1.5-f16.gguf",
        "--embedding",
        "-ngl", "99",
        "-c", "512",
        "--port", "8999"
    ], env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)

    try:
        ready = False
        for i in range(60):
            try:
                req = urllib.request.Request("http://127.0.0.1:8999/health")
                with urllib.request.urlopen(req, timeout=1) as res:
                    if res.status == 200:
                        ready = True
                        break
            except Exception:
                time.sleep(0.5)

        if not ready:
            print("Failed to start server. Output:")
            out, _ = proc.communicate(timeout=2)
            print(out)
            return False

        print("Embedder server is healthy. Sending embedding request...")
        req = urllib.request.Request(
            "http://127.0.0.1:8999/v1/embeddings",
            data=json.dumps({"input": "Testing ROCm 10 native HIP embedding"}).encode(),
            headers={"Content-Type": "application/json"}
        )
        with urllib.request.urlopen(req, timeout=5) as res:
            data = json.loads(res.read().decode())
            dim = len(data["data"][0]["embedding"])
            print(f"PASS: Successfully received embedding vector with dimension: {dim}")
            return True
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=3)
        except Exception:
            proc.kill()

if __name__ == "__main__":
    success = test_embed()
    sys.exit(0 if success else 1)

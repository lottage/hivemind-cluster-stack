#!/usr/bin/env python3
"""
Cluster Model Switcher & Orchestrator
Automates swapping LLM models running on VM 102 (RX 6750 XT - Vulkan0 / :8001).
Supports downloading from HuggingFace, reconfiguring systemd service,
health validation, instant rollback, and chaining with parameter discovery.
"""

import os
import sys
import time
import json
import argparse
import subprocess
import urllib.request
import urllib.error

# Force UTF-8 encoding
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

SSH_HOST = os.environ.get("SSH_CLUSTER_HOST", "user@127.0.0.1")
COORDINATOR_HEALTH_URL = "http://127.0.0.1:8001/health"
SERVICE_NAME = "llama-coordinator.service"
SERVICE_PATH = f"/etc/systemd/system/{SERVICE_NAME}"
SERVICE_BAK = f"/etc/systemd/system/{SERVICE_NAME}.bak"
MODELS_DIR = "/opt/models"


def run_remote_ssh(cmd: str, timeout: int = 30) -> tuple[int, str, str]:
    """Runs a remote command over SSH with passwordless sudo."""
    full_cmd = ["ssh", "-o", "BatchMode=yes", "-o", "StrictHostKeyChecking=no", SSH_HOST, cmd]
    res = subprocess.run(full_cmd, capture_output=True, text=True, timeout=timeout)
    return res.returncode, res.stdout.strip(), res.stderr.strip()


def list_models():
    """Lists available models on VM 102 and shows currently active coordinator model."""
    print("==================================================================")
    print("📋 LOCAL VM 102 MODEL REGISTRY (/opt/models)")
    print("==================================================================")

    # 1. Query active model
    rc, out, _ = run_remote_ssh(f"grep -E '--model|-c ' {SERVICE_PATH}")
    print("\n⚡ Current Active Coordinator Configuration:")
    for line in out.split("\n"):
        print(f"   {line.strip()}")

    # 2. Query directory contents
    cmd = f"ls -lh {MODELS_DIR}/*.gguf"
    rc, out, err = run_remote_ssh(cmd)
    print("\n📦 Available GGUF Models on Compute Host:")
    if rc == 0 and out:
        for line in out.split("\n"):
            parts = line.split()
            if len(parts) >= 9:
                size = parts[4]
                name = parts[8].replace(MODELS_DIR + "/", "")
                print(f"   • {name:50s} ({size})")
    else:
        print(f"   (No GGUFs found or error: {err})")

    # 3. Disk space
    _, disk, _ = run_remote_ssh(f"df -h {MODELS_DIR} | tail -n 1")
    print(f"\n💾 Storage Capacity: {disk}")
    print("==================================================================")


def check_health(timeout_sec: int = 35) -> bool:
    """Polls coordinator health endpoint until ready or timeout."""
    print(f"[*] Waiting for coordinator inference daemon to become healthy on :8001...")
    t0 = time.time()
    while time.time() - t0 < timeout_sec:
        try:
            req = urllib.request.Request(COORDINATOR_HEALTH_URL)
            with urllib.request.urlopen(req, timeout=2.0) as resp:
                if resp.status == 200:
                    data = json.loads(resp.read().decode("utf-8"))
                    if data.get("status") == "ok":
                        dt = time.time() - t0
                        print(f"[OK] Coordinator online and healthy! ({dt:.1f}s)")
                        return True
        except Exception:
            pass
        time.sleep(1.5)
    return False


def rollback_model() -> bool:
    """Restores the backup service file and restarts the coordinator."""
    print("\n[!] Initiating automatic rollback to previous stable configuration...")
    cmd = (
        f"sudo cp {SERVICE_BAK} {SERVICE_PATH} && "
        f"sudo systemctl daemon-reload && "
        f"sudo systemctl restart {SERVICE_NAME}"
    )
    rc, out, err = run_remote_ssh(cmd, timeout=30)
    if rc == 0:
        if check_health():
            print("[OK] Successfully rolled back to previous model!")
            return True
        else:
            print("[ERR] Rollback service failed to become healthy.", file=sys.stderr)
    else:
        print(f"[ERR] Failed executing rollback: {err}", file=sys.stderr)
    return False


def switch_model(model_filename: str, context: int = 16384, auto_tune: bool = True):
    """Reconfigures and restarts coordinator with the specified model."""
    full_model_path = f"{MODELS_DIR}/{model_filename}"
    print(f"\n[*] Preparing switch to model: {full_model_path}")
    print(f"[*] Target context window: {context} tokens")

    # 1. Verify model file exists on VM 102
    rc, _, _ = run_remote_ssh(f"test -f {full_model_path}")
    if rc != 0:
        print(f"[ERR] Model file not found on VM 102: {full_model_path}", file=sys.stderr)
        return False

    # 2. Backup current service file
    run_remote_ssh(f"sudo cp {SERVICE_PATH} {SERVICE_BAK}")

    # 3. Generate updated service unit with hardware-optimized flags
    # Model size heuristic: 9B models safely handle 16k context on RX 6750 XT 12GB
    new_unit = f"""[Unit]
Description=Llama-Server Coordinator (RX 6750 XT - Vulkan)
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/opt/models
Environment="GGML_VK_VISIBLE_DEVICES=0"
ExecStart=/usr/local/bin/llama-server \\
    --model {full_model_path} \\
    --host 0.0.0.0 \\
    --port 8001 \\
    --device Vulkan0 \\
    -ngl 99 \\
    -c {context} \\
    --flash-attn on \\
    -ctk q8_0 \\
    -ctv q8_0 \\
    --alias coordinator \\
    --metrics

Restart=always
RestartSec=5
StandardOutput=journal
StandardError=journal
LimitNOFILE=65535

[Install]
WantedBy=multi-user.target
"""
    # Write updated service to remote
    write_cmd = f"sudo tee {SERVICE_PATH} << 'EOF'\n{new_unit}EOF"
    rc, _, err = run_remote_ssh(write_cmd)
    if rc != 0:
        print(f"[ERR] Failed writing service unit: {err}", file=sys.stderr)
        return False

    # 4. Reload and restart daemon
    print("[*] Reloading systemd daemon and restarting coordinator...")
    restart_cmd = f"sudo systemctl daemon-reload && sudo systemctl restart {SERVICE_NAME}"
    rc, _, err = run_remote_ssh(restart_cmd, timeout=30)
    if rc != 0:
        print(f"[ERR] Failed restarting service: {err}", file=sys.stderr)
        rollback_model()
        return False

    # 5. Health verification
    healthy = check_health(timeout_sec=35)
    if not healthy:
        print(f"[!] New model failed health check on :8001! Triggering rollback...", file=sys.stderr)
        rollback_model()
        return False

    print(f"\n🎉 Successfully deployed and validated: {model_filename} on :8001")

    # 6. Chained parameter discovery & tuning
    if auto_tune:
        print("\n==================================================================")
        print("🔍 Launching Automated Model Parameter Discovery Loop...")
        print("==================================================================")
        discover_script = os.path.join(
            os.path.dirname(__file__), "..", "model-parameter-discoverer", "discover_parameters.py"
        )
        if os.path.exists(discover_script):
            tune_cmd = [
                sys.executable,
                discover_script,
                "--model-name", model_filename,
                "--port", "8001"
            ]
            subprocess.run(tune_cmd)
        else:
            print(f"[!] Parameter discoverer script not found at {discover_script}")

    return True


def download_hf_model(repo: str, filename: str) -> str:
    """Downloads model from Hugging Face directly to VM 102."""
    url = f"https://huggingface.co/{repo}/resolve/main/{filename}"
    dest = f"{MODELS_DIR}/{filename}"
    print(f"[*] Downloading {filename} from {repo} to VM 102...")
    print(f"[*] Source URL: {url}")
    
    cmd = f"wget -c '{url}' -O '{dest}'"
    # Execute with streaming output or wait
    full_cmd = ["ssh", "-o", "BatchMode=yes", "-o", "StrictHostKeyChecking=no", SSH_HOST, cmd]
    p = subprocess.Popen(full_cmd)
    p.wait()
    if p.returncode == 0:
        print(f"[OK] Download completed: {dest}")
        return filename
    else:
        print(f"[ERR] Download failed with exit code {p.returncode}", file=sys.stderr)
        return ""


def main():
    parser = argparse.ArgumentParser(description="Cluster Model Switcher & Orchestrator")
    parser.add_argument("--list", action="store_true", help="List available models and current active configuration")
    parser.add_argument("--model", type=str, help="Filename of existing GGUF model in /opt/models/")
    parser.add_argument("--hf", type=str, help="Hugging Face repo (e.g. bartowski/deepreinforce-ai_Ornith-1.0-9B-GGUF)")
    parser.add_argument("--file", type=str, help="Hugging Face GGUF filename (e.g. deepreinforce-ai_Ornith-1.0-9B-Q5_K_M.gguf)")
    parser.add_argument("--context", type=int, default=16384, help="Context window size (default: 16384 for 9B models)")
    parser.add_argument("--rollback", action="store_true", help="Rollback to previous stable model configuration")
    parser.add_argument("--no-tune", action="store_true", help="Skip automatic parameter discovery after switching")

    args = parser.parse_args()

    if args.list:
        list_models()
        return

    if args.rollback:
        rollback_model()
        return

    target_model = args.model
    if args.hf and args.file:
        downloaded = download_hf_model(args.hf, args.file)
        if not downloaded:
            return
        target_model = downloaded

    if target_model:
        switch_model(target_model, context=args.context, auto_tune=(not args.no_tune))
    else:
        parser.print_help()


if __name__ == "__main__":
    main()

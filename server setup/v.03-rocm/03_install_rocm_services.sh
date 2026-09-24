#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "=========================================================="
echo "  [v.03-rocm] Installing Isolated Systemd Services        "
echo "=========================================================="

echo "[1/3] Copying ROCm systemd unit files to /etc/systemd/system/..."
sudo cp "$SCRIPT_DIR/systemd/llama-moe-rocm.service" /etc/systemd/system/
sudo cp "$SCRIPT_DIR/systemd/llama-coordinator-rocm.service" /etc/systemd/system/
sudo cp "$SCRIPT_DIR/systemd/llama-worker-rocm.service" /etc/systemd/system/
sudo cp "$SCRIPT_DIR/systemd/llama-embed-rocm.service" /etc/systemd/system/

echo "[2/3] Reloading systemd daemon..."
sudo systemctl daemon-reload

echo "[3/3] Registration complete."
echo ""
echo "Note: Services are installed in PARALLEL and not enabled yet."
echo "Your active production Vulkan stack remains completely undisturbed."
echo ""
echo "To switch between stacks safely, use:"
echo "  ./switch_stack.sh rocm moe       # Switch MoE to ROCm"
echo "  ./switch_stack.sh rocm dual      # Switch Coordinator/Worker to ROCm"
echo "  ./switch_stack.sh vulkan         # Revert back to Vulkan (failsafe)"
echo "  ./switch_stack.sh status         # Check current running backend"

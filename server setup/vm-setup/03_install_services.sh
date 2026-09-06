#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "=== Installing systemd services ==="
sudo cp "$SCRIPT_DIR/systemd/llama-coordinator.service" /etc/systemd/system/
sudo cp "$SCRIPT_DIR/systemd/llama-worker.service" /etc/systemd/system/
sudo cp "$SCRIPT_DIR/systemd/llama-embed.service" /etc/systemd/system/

echo "=== Reloading systemd daemon ==="
sudo systemctl daemon-reload

echo "=== Enabling and starting all services ==="
sudo systemctl enable --now llama-coordinator.service
sudo systemctl enable --now llama-worker.service
sudo systemctl enable --now llama-embed.service

echo ""
echo "=== Services Started! Checking status ==="
sudo systemctl status llama-coordinator.service --no-pager -n 5 || true
sudo systemctl status llama-worker.service --no-pager -n 5 || true
sudo systemctl status llama-embed.service --no-pager -n 5 || true

echo ""
echo "=== Testing HTTP Health Endpoints ==="
sleep 3
echo "Coordinator (8001):"
curl -s http://localhost:8001/health || echo "Still starting up..."
echo "Worker (8002):"
curl -s http://localhost:8002/health || echo "Still starting up..."
echo "Embedder (8003):"
curl -s http://localhost:8003/health || echo "Still starting up..."

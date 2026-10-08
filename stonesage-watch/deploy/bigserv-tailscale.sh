#!/usr/bin/env bash
# Run once on bigserv (Tailscale already installed and logged in).
set -euo pipefail
apt-get install -y socat
cp bigserv-watch-forward.service /etc/systemd/system/
systemctl daemon-reload
systemctl enable --now bigserv-watch-forward
# Tailnet-only HTTPS (no Funnel) on port 8443 -> bridge
tailscale serve --bg --https=8443 http://127.0.0.1:8890
tailscale serve status
echo "Bridge URL for phone + face: https://$(tailscale status --json | python3 -c 'import json,sys;print(json.load(sys.stdin)["Self"]["DNSName"].rstrip("."))'):8443"

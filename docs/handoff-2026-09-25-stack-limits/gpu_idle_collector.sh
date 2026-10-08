#!/usr/bin/env bash
# gpu_idle_collector.sh
#
# Run on the Proxmox HOST (pve / bigserv), not inside a container — the
# amdgpu sysfs busy-percent counter lives at the host driver level even
# with Vulkan passthrough to LXCs.
#
# Emits Prometheus-format metrics to node_exporter's textfile collector
# directory, so no custom exporter binary is needed — node_exporter picks
# these up automatically on its normal scrape interval.
#
# Install:
#   1. mkdir -p /var/lib/node_exporter/textfile_collector
#   2. Start node_exporter with:
#        --collector.textfile.directory=/var/lib/node_exporter/textfile_collector
#   3. Cron this script every 30s (or run as a systemd timer, see below)

set -euo pipefail

OUT_DIR="/var/lib/node_exporter/textfile_collector"
OUT_FILE="${OUT_DIR}/gpu_idle.prom"
TMP_FILE="${OUT_FILE}.$$"

mkdir -p "$OUT_DIR"
> "$TMP_FILE"

echo "# HELP gpu_busy_percent Instantaneous GPU busy percentage from amdgpu sysfs" >> "$TMP_FILE"
echo "# TYPE gpu_busy_percent gauge" >> "$TMP_FILE"

for card in /sys/class/drm/card*/device/gpu_busy_percent; do
  [ -f "$card" ] || continue
  card_id=$(echo "$card" | grep -oP 'card\K[0-9]+')
  busy=$(cat "$card" 2>/dev/null || echo "-1")

  # Map card index -> role. Adjust these indices to match your actual
  # /sys/class/drm ordering (verify once with `cat` on each path manually —
  # ordering is not guaranteed to match install order across reboots).
  case "$card_id" in
    0) role="coordinator_6750xt" ;;
    1) role="worker_6600xt" ;;
    *) role="unknown_card${card_id}" ;;
  esac

  echo "gpu_busy_percent{role=\"${role}\",card=\"${card_id}\"} ${busy}" >> "$TMP_FILE"
done

# Atomic move so node_exporter never reads a half-written file
mv "$TMP_FILE" "$OUT_FILE"

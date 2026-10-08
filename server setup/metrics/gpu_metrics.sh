#!/bin/sh
# GPU busy % and VRAM for Prometheus, via node_exporter's textfile collector (VM 102, where the GPUs are passed
# through; the Proxmox host does not see them). Installed as /usr/local/bin/gpu_metrics.sh, run every 15 s by
# gpu-metrics.timer. Labelled by PCI slot and the lspci name, never by card number: /sys/class/drm/cardN numbering
# is not stable across reboots, and card1 on VM 102 is the virtual display.
set -eu
DIR=/var/lib/prometheus/node-exporter
OUT="$DIR/gpu.prom"
TMP="$OUT.$$"
{
  echo "# HELP stonesage_gpu_busy_percent GPU busy percentage (amdgpu gpu_busy_percent)."
  echo "# TYPE stonesage_gpu_busy_percent gauge"
  echo "# HELP stonesage_gpu_vram_used_bytes VRAM in use."
  echo "# TYPE stonesage_gpu_vram_used_bytes gauge"
  echo "# HELP stonesage_gpu_vram_total_bytes VRAM size."
  echo "# TYPE stonesage_gpu_vram_total_bytes gauge"
  for dev in /sys/class/drm/card*/device; do
    [ -f "$dev/gpu_busy_percent" ] || continue
    pci=$(basename "$(readlink -f "$dev")")
    name=$(lspci -mm -s "$pci" 2>/dev/null | cut -d'"' -f6 | tr -d '"\\')
    labels="pci=\"$pci\",gpu=\"${name:-unknown}\""
    echo "stonesage_gpu_busy_percent{$labels} $(cat "$dev/gpu_busy_percent")"
    if [ -f "$dev/mem_info_vram_used" ]; then
      echo "stonesage_gpu_vram_used_bytes{$labels} $(cat "$dev/mem_info_vram_used")"
    fi
    if [ -f "$dev/mem_info_vram_total" ]; then   # (an && list here would end the loop with status 1 under set -e)
      echo "stonesage_gpu_vram_total_bytes{$labels} $(cat "$dev/mem_info_vram_total")"
    fi
  done
} > "$TMP"
mv "$TMP" "$OUT"   # atomic: node_exporter never reads a half-written file

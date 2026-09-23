#!/usr/bin/env bash
# Phase 0 report for VM 102 (ubu). Read-only unless --apply is passed.
#   scp "server setup/phase0_vm102_report.sh" austin@192.168.1.105:/tmp/
#   ssh austin@192.168.1.105 "bash /tmp/phase0_vm102_report.sh" > vm102_report.txt
#   ssh -t austin@192.168.1.105 "bash /tmp/phase0_vm102_report.sh --apply"   # stop loops
set -u
APPLY=0; [ "${1:-}" = "--apply" ] && APPLY=1
hr(){ printf '\n===== %s =====\n' "$1"; }

hr "Host"; hostname; date; uptime
hr "GPU / Vulkan devices"; /usr/local/bin/llama-server --list-devices 2>&1 | head -20
hr "Services"
for s in llama-coordinator llama-worker llama-embed llama-embedder llama-speculative llama-moe vision-server \
         cluster-mcp agent-assembly assembly-hall wildlife-sentry valkey; do
  st=$(systemctl is-active "$s" 2>/dev/null); en=$(systemctl is-enabled "$s" 2>/dev/null)
  [ -n "$st$en" ] && printf '%-20s active=%-10s enabled=%s\n' "$s" "$st" "$en"
done
hr "Unit ExecStart (actual, from systemd)"
for s in llama-coordinator llama-worker llama-embed llama-embedder vision-server llama-moe; do
  systemctl cat "$s" 2>/dev/null | sed -n '/ExecStart/,/^[A-Z][A-Za-z]*=/p' | tr -s ' ' | sed "s/^/[$s] /"
done
hr "Live /props per port"
for p in 8001 8002 8003 8004; do
  printf '%s: ' "$p"
  curl -s -m 3 "http://127.0.0.1:$p/props" | python3 -c 'import sys,json
try:
  d=json.load(sys.stdin); g=d.get("default_generation_settings",{})
  print(d.get("model_path","?"), "| n_ctx", g.get("n_ctx"), "| slots", d.get("total_slots"), "| chat_template_caps", bool(d.get("chat_template_caps")))
except Exception as e: print("no response", e)'
done
hr "VRAM"; for c in /sys/class/drm/card*/device/mem_info_vram_used; do d=$(dirname "$c"); echo "$d used=$(( $(cat $c)/1048576 ))MB total=$(( $(cat $d/mem_info_vram_total)/1048576 ))MB"; done 2>/dev/null
hr "Deployed daemon checksums"; md5sum /opt/cluster-bridge/wildlife_sentry_daemon.py /opt/cluster-bridge/mcp_server.py /opt/cluster-bridge/autonomous_engine.py 2>/dev/null
hr "Autonomous engine state"; cat /opt/cluster-bridge/thinking_state.json 2>/dev/null | head -c 600; echo
hr "Secrets env"; ls -l /etc/stonesage/secrets.env 2>&1
hr "Wildlife sentry last 20 log lines"; journalctl -u wildlife-sentry -n 20 --no-pager 2>/dev/null

if [ "$APPLY" = 1 ]; then
  hr "APPLY: stopping autonomous loops"
  curl -s -m 10 -X POST http://127.0.0.1:8765/messages -H 'Content-Type: application/json' \
    -d '{"jsonrpc":"2.0","id":1,"method":"tools/call","params":{"name":"stop_autonomous_thinking","arguments":{}}}'; echo
  for s in agent-assembly assembly-hall; do sudo systemctl disable --now "$s" 2>/dev/null && echo "disabled $s"; done
  sudo mkdir -p /etc/stonesage && [ -f /etc/stonesage/secrets.env ] || { sudo install -m 600 /dev/null /etc/stonesage/secrets.env; echo "created empty /etc/stonesage/secrets.env (fill from secrets.env.example)"; }
fi

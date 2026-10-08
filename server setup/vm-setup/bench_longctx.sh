#!/usr/bin/env bash
# Rollout step 2 of docs/plan-2026-09-26-local-loop/DESIGN.md: measure Bonsai 2 in each lease layout before building
# anything on top of it. DRAFT 2026-09-26, not yet run. Needs 04_build_llama_prism.sh done and the three
# llama-longctx*.service units copied to /etc/systemd/system (+ daemon-reload), still disabled.
#
#   sudo LAYOUT=6750 bash bench_longctx.sh   # Courage offline   (stops coordinator + worker)
#   sudo LAYOUT=6600 bash bench_longctx.sh   # vision offline    (stops vision-server)
#   sudo LAYOUT=max  bash bench_longctx.sh   # both offline      (stops coordinator + worker + vision-server)
#
# Whatever was stopped is started again on exit (also on Ctrl-C or an error). Run in a quiet window.
set -euo pipefail

LAYOUT="${LAYOUT:-6750}"
BIN=/opt/llama-prism/current
MODEL=/opt/models/prism/Ternary-Bonsai-2-27B-PTQ1_0.gguf

# Per layout: units the lease stops, the longctx unit, llama-bench device args, KV types, depths, needle size.
case "$LAYOUT" in
    6750)
        STOP="llama-coordinator.service llama-worker.service"; UNIT=llama-longctx.service
        VISIBLE=0; BENCH_DEV=(); CTK=q8_0; CTV=q8_0
        DEPTHS="${DEPTHS:-0,8192,32768,131072}"; NEEDLE_WORDS=75000 ;;
    6600)
        STOP="vision-server.service"; UNIT=llama-longctx-6600.service
        VISIBLE=1; BENCH_DEV=(); CTK=q8_0; CTV=q4_0
        DEPTHS="${DEPTHS:-0,8192,24576}"; NEEDLE_WORDS=20000 ;;
    max)
        STOP="llama-coordinator.service llama-worker.service vision-server.service"; UNIT=llama-longctx-max.service
        VISIBLE=0,1; BENCH_DEV=(-sm layer -ts 11/7); CTK=q8_0; CTV=q8_0
        DEPTHS="${DEPTHS:-0,32768,131072,245760}"; NEEDLE_WORDS=150000 ;;
    *) echo "LAYOUT must be 6750, 6600 or max" >&2; exit 2 ;;
esac

OUT=/root/bench-longctx-${LAYOUT}-$(date +%Y%m%d-%H%M%S)
mkdir -p "$OUT"

restore() {
    systemctl stop "$UNIT" 2>/dev/null || true
    # shellcheck disable=SC2086
    systemctl start $STOP
    echo "Restored: $STOP. Results in $OUT"
}
trap restore EXIT

# shellcheck disable=SC2086
systemctl stop $STOP
sleep 3

echo "=== [$LAYOUT] llama-bench: prefill/decode at depth ${DEPTHS} (K ${CTK}, V ${CTV}, FA on) ==="
GGML_VK_VISIBLE_DEVICES="$VISIBLE" "$BIN/llama-bench" -m "$MODEL" -ngl 99 -fa 1 -ctk "$CTK" -ctv "$CTV" \
    "${BENCH_DEV[@]}" -p 512 -n 128 -d "$DEPTHS" -r 2 -o md 2>&1 | tee "$OUT/llama-bench.md"

echo "=== [$LAYOUT] Server ($UNIT): real VRAM per GPU from fdinfo ==="
systemctl start "$UNIT"
for _ in $(seq 1 150); do
    curl -sf http://127.0.0.1:8005/health >/dev/null && break
    sleep 2
done
curl -s http://127.0.0.1:8005/props > "$OUT/props.json"
PID=$(systemctl show -p MainPID --value "$UNIT")
# One drm-pdev line per GPU the process has open, each followed by its VRAM/GTT use.
grep -hE 'drm-pdev|drm-memory-vram|drm-memory-gtt' /proc/"$PID"/fdinfo/* 2>/dev/null | uniq | tee "$OUT/fdinfo.txt"
journalctl -u "$UNIT" -b --no-pager | grep -iE 'int dot|KV self size|CPU_REPACK|failed|error' \
    | tee "$OUT/journal-highlights.txt" || true

echo "=== [$LAYOUT] Needle (~${NEEDLE_WORDS} filler words) ==="
python3 - "$OUT" "$NEEDLE_WORDS" <<'PY'
import json, random, sys, time, urllib.request
out, n_words = sys.argv[1], int(sys.argv[2])
random.seed(7)
words = [random.choice(["alpha", "river", "stone", "copper", "lantern", "meadow", "signal", "harbor"])
         for _ in range(n_words)]
words.insert(len(words) * 2 // 3, "The access phrase for the vault is PURPLE-OTTER-417.")
prompt = " ".join(words) + "\n\nWhat is the access phrase for the vault? Answer with the phrase only."
body = {"messages": [{"role": "user", "content": prompt}], "max_tokens": 2048, "temperature": 0,
        "reasoning_effort": "low"}
t0 = time.time()
req = urllib.request.Request("http://127.0.0.1:8005/v1/chat/completions", json.dumps(body).encode(),
                             {"Content-Type": "application/json"})
resp = json.load(urllib.request.urlopen(req, timeout=3600))
answer = resp["choices"][0]["message"].get("content", "")
result = {"seconds": round(time.time() - t0, 1), "usage": resp.get("usage"), "timings": resp.get("timings"),
          "found": "PURPLE-OTTER-417" in answer, "answer": answer[-300:]}
json.dump(result, open(f"{out}/needle.json", "w"), indent=1)
print(json.dumps(result, indent=1))
PY

#!/bin/sh
# Model Tryout slot (docs/plan-2026-09-26-local-loop/DESIGN.md section E), started only by an engine lease
# (layouts tryout_6600 / tryout_6750). Which build, model and context come from /etc/stonesage/tryout.env, written
# by the eval runner (tests/live/model_eval.py) before each lease: BIN, MODEL, CTX, optional EXTRA.
set -eu
# Carriage returns stripped: a file written from Windows ends every value in CR (exit 127, 2026-09-28)
tr -d '\r' < /etc/stonesage/tryout.env > /run/llama-tryout.env
. /run/llama-tryout.env
exec "$BIN" --model "$MODEL" --host 0.0.0.0 --port 8009 --device Vulkan0 -ngl 99 -c "${CTX:-8192}" -np 1 \
     --jinja --metrics --flash-attn "${FA:-auto}" --alias tryout ${EXTRA:-}

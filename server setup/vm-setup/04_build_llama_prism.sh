#!/usr/bin/env bash
# Build PrismML's llama.cpp fork (ternary PTQ1_0 / PQ2_0 kernels for Bonsai 2) with Vulkan into /opt/llama-prism.
# DRAFT 2026-09-26, not yet run. See docs/plan-2026-09-26-local-loop/DESIGN.md.
#
# - Never touches /usr/local/bin/llama-server: the mainline engines (coordinator, worker, embed, vision) stay as they are.
# - Installs to /opt/llama-prism/<tag>/ and points /opt/llama-prism/current at it (the units run current/llama-server).
#   /opt/llama-prism already holds an older prebuilt (bin/ + llama-prism-b10709-9a9394a/, 2026-09-19, BEFORE the
#   int-dot kernel): left untouched, and a rollback is just re-pointing the symlink.
# - Pinned to a release tag on purpose: the fork moves fast; rebuild only by changing PRISM_TAG.
#   prism-b10735 is the first release with the Vulkan integer-dot PTQ1_0 kernel (PR #188 -> #238), which took a
#   6750 XT from 4.7 to ~40 tok/s decode.
# - Vulkan only: the fork's ROCm/HIP path fails on consumer RDNA2 (KNOWN_ISSUES.md, issue #264).
# Model: PTQ1_0 (5.95 GB). /opt/models/Ternary-Bonsai-2-27B-PQ2_0.gguf (7.21 GB) is already on VM 102 since 2026-09-19;
# PTQ1_0 is fetched because it leaves ~1.2 GB more for KV (PQ2_0 measured 38.5 vs PTQ1_0 ~40 tok/s on a 6750 XT).
# Build deps are the ones 01_install_vulkan_llamacpp.sh already installed.
set -euo pipefail

PRISM_TAG="${PRISM_TAG:-prism-b10743-adfffbe}"
SRC=/opt/llama-prism-src
ROOT=/opt/llama-prism
DEST="$ROOT/$PRISM_TAG"
MODEL_DIR=/opt/models/prism
MODEL_FILE=Ternary-Bonsai-2-27B-PTQ1_0.gguf

echo "=== [1/4] Source at ${PRISM_TAG} ==="
if [ ! -d "$SRC/.git" ]; then
    sudo git clone --filter=blob:none https://github.com/PrismML-Eng/llama.cpp.git "$SRC"
fi
sudo git -C "$SRC" fetch --tags origin
sudo git -C "$SRC" checkout --detach "$PRISM_TAG"

echo "=== [2/4] Build (Vulkan) ==="
sudo rm -rf "$SRC/build"
sudo cmake -S "$SRC" -B "$SRC/build" -DGGML_VULKAN=ON -DCMAKE_BUILD_TYPE=Release
sudo cmake --build "$SRC/build" --config Release -j"$(nproc)" --target llama-server llama-bench

echo "=== [3/4] Install to ${DEST} ==="
sudo mkdir -p "$DEST"
sudo cp "$SRC"/build/bin/llama-server "$SRC"/build/bin/llama-bench "$DEST"/
# Shared libs, if this build produced any (ggml is shared by default in recent trees).
sudo find "$SRC/build/bin" -maxdepth 1 -name '*.so*' -exec cp -a {} "$DEST"/ \;
echo "$PRISM_TAG" | sudo tee "$DEST/BUILD_TAG" >/dev/null
sudo ln -sfn "$DEST" "$ROOT/current"
"$ROOT/current/llama-server" --version 2>&1 | head -2

echo "=== [4/4] Model ==="
sudo mkdir -p "$MODEL_DIR"
if [ ! -f "$MODEL_DIR/$MODEL_FILE" ]; then
    sudo wget -q --show-progress -O "$MODEL_DIR/$MODEL_FILE.part" \
        "https://huggingface.co/prism-ml/Ternary-Bonsai-2-27B-gguf/resolve/main/$MODEL_FILE"
    sudo mv "$MODEL_DIR/$MODEL_FILE.part" "$MODEL_DIR/$MODEL_FILE"
fi
ls -l "$MODEL_DIR"

echo ""
echo "Check the 6750 XT exposes integer dot (without it PTQ1_0 falls back to the ~3 tok/s path):"
GGML_VK_VISIBLE_DEVICES=0 "$DEST/llama-server" --list-devices 2>&1 | grep -iE 'int dot|vulkan0|6750' || true

#!/usr/bin/env bash
set -euo pipefail

MODEL_DIR="/opt/models"
echo "=== Ensuring model directory exists at $MODEL_DIR ==="
sudo mkdir -p "$MODEL_DIR"
sudo chown -R "$USER:$USER" "$MODEL_DIR"
cd "$MODEL_DIR"

# Install huggingface_hub cli if not present
if ! command -v hf >/dev/null 2>&1 && ! command -v huggingface-cli >/dev/null 2>&1; then
    echo "=== Installing huggingface_hub for fast resumable downloads ==="
    pip3 install --upgrade --break-system-packages huggingface_hub || pip3 install --upgrade huggingface_hub
fi

# Detect hf or huggingface-cli
if command -v hf >/dev/null 2>&1; then
    HF_BIN="hf"
elif [ -f "$HOME/.local/bin/hf" ]; then
    HF_BIN="$HOME/.local/bin/hf"
elif command -v huggingface-cli >/dev/null 2>&1; then
    HF_BIN="huggingface-cli"
elif [ -f "$HOME/.local/bin/huggingface-cli" ]; then
    HF_BIN="$HOME/.local/bin/huggingface-cli"
else
    HF_BIN="python3 -m huggingface_hub.cli.core"
fi
echo "Using Hugging Face CLI: $HF_BIN"

echo ""
echo "=== [1/3] Downloading Qwen2.5-Coder-14B-Instruct-abliterated (Q4_K_M) ==="
echo "Target: RX 6750 XT (12GB) Coordinator on Port 8001"
$HF_BIN download bartowski/Qwen2.5-Coder-14B-Instruct-abliterated-GGUF \
    Qwen2.5-Coder-14B-Instruct-abliterated-Q4_K_M.gguf \
    --local-dir "$MODEL_DIR" \
    --local-dir-use-symlinks False

# Ensure lowercase symlink exists for systemd unit compatibility
ln -sf "$MODEL_DIR/Qwen2.5-Coder-14B-Instruct-abliterated-Q4_K_M.gguf" "$MODEL_DIR/qwen2.5-coder-14b-instruct-abliterated-q4_k_m.gguf"

echo ""
echo "=== [2/3] Downloading Qwen2.5-Coder-3B-Instruct (Q5_K_M) ==="
echo "Target: RX 6600 XT (8GB) Fast Worker on Port 8002"
$HF_BIN download Qwen/Qwen2.5-Coder-3B-Instruct-GGUF \
    qwen2.5-coder-3b-instruct-q5_k_m.gguf \
    --local-dir "$MODEL_DIR" \
    --local-dir-use-symlinks False

echo ""
echo "=== [3/3] Downloading BGE-Large-EN-v1.5 (Embedding Model) ==="
echo "Target: RX 6600 XT (8GB) Qdrant Embedder on Port 8003"
$HF_BIN download CompendiumLabs/bge-large-en-v1.5-gguf \
    bge-large-en-v1.5-f16.gguf \
    --local-dir "$MODEL_DIR" \
    --local-dir-use-symlinks False

echo ""
echo "=== All models downloaded successfully in $MODEL_DIR ==="
ls -lh "$MODEL_DIR"/*.gguf

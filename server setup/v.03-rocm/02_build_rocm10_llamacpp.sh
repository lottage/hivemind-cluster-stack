#!/usr/bin/env bash
set -euo pipefail

echo "=========================================================="
echo "  [v.03-rocm] Building llama.cpp with Native HIP Backend  "
echo "  Targets: gfx1031 & gfx1032 (Zero HSA Override Hacks)   "
echo "=========================================================="

BUILD_DIR="/opt/llama.cpp-rocm"
TARGET_BIN="/usr/local/bin/llama-server-rocm"

# 1. Clone repository to isolated directory
echo "[1/4] Preparing isolated source directory in $BUILD_DIR..."
if [ ! -d "$BUILD_DIR" ]; then
    sudo git clone --depth 1 https://github.com/ggerganov/llama.cpp.git "$BUILD_DIR"
fi

cd "$BUILD_DIR"
echo "Updating repository to latest upstream commit..."
sudo git pull --ff-only || true

# 2. Configure CMake with native HIP backend
echo "[2/4] Configuring CMake for AMDGPU targets (gfx1031;gfx1032)..."
sudo rm -rf build
sudo mkdir -p build

# Ensure hipcc / rocm paths are discovered
export PATH="/opt/rocm/bin:$PATH"
export HIP_PATH="${HIP_PATH:-/opt/rocm}"

sudo cmake -B build \
    -DGGML_HIP=ON \
    -DAMDGPU_TARGETS="gfx1031;gfx1032" \
    -DCMAKE_BUILD_TYPE=Release \
    -DCMAKE_C_COMPILER=hipcc \
    -DCMAKE_CXX_COMPILER=hipcc

# 3. Compile llama-server
echo "[3/4] Compiling llama-server with $(nproc) parallel threads..."
sudo cmake --build build --config Release -j"$(nproc)" --target llama-server

# 4. Install parallel binary
echo "[4/4] Installing parallel binary to $TARGET_BIN..."
sudo cp build/bin/llama-server "$TARGET_BIN"
sudo chmod +x "$TARGET_BIN"

echo ""
echo "=== HIP llama.cpp Build Complete! ==="
echo "Binary installed at: $TARGET_BIN"
echo "Testing device enumeration:"
"$TARGET_BIN" --list-devices || true

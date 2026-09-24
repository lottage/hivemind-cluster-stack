#!/usr/bin/env bash
set -euo pipefail

echo "=== [1/4] Installing Vulkan & Build Dependencies ==="
sudo apt-get update
sudo apt-get install -y \
    build-essential \
    cmake \
    git \
    libvulkan-dev \
    vulkan-tools \
    mesa-vulkan-drivers \
    libdrm-dev \
    shaderc \
    glslang-tools \
    spirv-tools \
    spirv-headers \
    libspirv-tools-dev \
    curl \
    wget \
    python3 \
    python3-pip || true

echo "=== Ensuring SPIRV-Headers CMake Config is Installed ==="
if [ ! -d "/usr/local/share/cmake/SPIRV-Headers" ] && [ ! -d "/usr/share/cmake/SPIRV-Headers" ]; then
    echo "Installing SPIRV-Headers from KhronosGroup repository..."
    git clone --depth 1 https://github.com/KhronosGroup/SPIRV-Headers.git /tmp/SPIRV-Headers
    cmake -B /tmp/SPIRV-Headers/build -S /tmp/SPIRV-Headers
    sudo cmake --install /tmp/SPIRV-Headers/build
    rm -rf /tmp/SPIRV-Headers
fi

echo "=== [2/4] Cloning llama.cpp ==="
cd /opt
if [ ! -d "/opt/llama.cpp" ]; then
    sudo git clone --depth 1 https://github.com/ggerganov/llama.cpp.git
fi
cd /opt/llama.cpp
sudo git pull

echo "=== [3/4] Building llama.cpp with Vulkan Backend ==="
sudo rm -rf build
sudo cmake -B build -DGGML_VULKAN=ON -DCMAKE_BUILD_TYPE=Release
sudo cmake --build build --config Release -j"$(nproc)" --target llama-server

echo "=== [4/4] Installing llama-server Binary ==="
sudo cp build/bin/llama-server /usr/local/bin/llama-server
sudo chmod +x /usr/local/bin/llama-server

echo ""
echo "=== Setup Complete! Checking Vulkan Devices ==="
echo "Run the following command to identify Vulkan device indices for 01:00.0 and 03:00.0:"
/usr/local/bin/llama-server --list-devices || vulkaninfo --summary

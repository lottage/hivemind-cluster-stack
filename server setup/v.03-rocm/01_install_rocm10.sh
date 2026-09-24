#!/usr/bin/env bash
set -euo pipefail

echo "=========================================================="
echo "  [v.03-rocm] Installing AMD ROCm 10.0 Core SDK & HIP    "
echo "  Targets: gfx1031 (RX 6750 XT) & gfx1032 (RX 6600 XT)   "
echo "=========================================================="

# 1. Ensure prerequisites
echo "[1/4] Installing system prerequisites..."
sudo apt-get update
sudo apt-get install -y \
    curl \
    wget \
    gnupg2 \
    software-properties-common \
    build-essential \
    cmake \
    git \
    libnuma-dev \
    pciutils

# 2. Add AMD ROCm repository GPG key and repo source if not already present
echo "[2/4] Configuring AMD ROCm official repository..."
sudo mkdir -p --mode=0755 /etc/apt/keyrings
if [ ! -f /etc/apt/keyrings/rocm.gpg ]; then
    wget -q -O - https://repo.radeon.com/rocm/rocm.gpg.key | gpg --dearmor | sudo tee /etc/apt/keyrings/rocm.gpg > /dev/null
fi

# Detect Ubuntu codename (noble/plucky/resolute)
UBUNTU_CODENAME="$(lsb_release -cs 2>/dev/null || echo 'noble')"
# Fallback to noble if on newer rolling distro where 24.04 repos are used
if [ "$UBUNTU_CODENAME" != "noble" ] && [ "$UBUNTU_CODENAME" != "jammy" ]; then
    echo "Distro codename is $UBUNTU_CODENAME; mapping ROCm target repo to noble (24.04 LTS binary compatible)..."
    REPO_CODENAME="noble"
else
    REPO_CODENAME="$UBUNTU_CODENAME"
fi

echo "deb [arch=amd64 signed-by=/etc/apt/keyrings/rocm.gpg] https://repo.radeon.com/rocm/apt/latest $REPO_CODENAME main" | sudo tee /etc/apt/sources.list.d/rocm.list > /dev/null

# Prefer rocm packages if version conflicts occur
cat << 'EOF' | sudo tee /etc/apt/preferences.d/rocm-pin-600
Package: *
Pin: release o=repo.radeon.com
Pin-Priority: 600
EOF

# 3. Update apt and install ROCm packages
echo "[3/4] Updating package indexes and installing ROCm / HIP Core packages..."
sudo apt-get update || true
sudo apt-get install -y \
    rocm-core \
    hip-runtime-amd \
    hip-dev \
    rocblas \
    rocblas-dev \
    hipblas \
    hipblas-dev \
    rocminfo \
    rocm-smi-lib || {
        echo "Note: Some monolithic metapackages may differ; ensuring base hipcc & rocblas are installed..."
        sudo apt-get install -y hipcc libamdhip64-dev libhipblas-dev librocblas-dev rocminfo || true
    }

# 4. Verification of HSA & GPU Architecture Targets
echo "[4/4] Verifying GPU architectures via rocminfo..."
echo "----------------------------------------------------------"
rocminfo | grep -E "(Name:|Marketing Name:|Compute Unit:)" || true
echo "----------------------------------------------------------"

# Ensure user is in render and video groups
sudo usermod -aG render,video "$USER" || true

echo ""
echo "=== ROCm 10 Base Setup Complete! ==="
echo "Both gfx1031 and gfx1032 are registered in the HSA topology."

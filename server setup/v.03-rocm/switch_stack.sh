#!/usr/bin/env bash
set -euo pipefail

MODE="${1:-status}"
SUBMODE="${2:-moe}"

poll_health() {
    local port="$1"
    local name="$2"
    local max_retries="${3:-30}"
    local count=0

    echo -n "Waiting for $name on port $port to report /health..."
    while [ $count -lt "$max_retries" ]; do
        if curl -s -f "http://127.0.0.1:$port/health" > /dev/null 2>&1; then
            echo " [ONLINE] (took ${count}s)"
            return 0
        fi
        sleep 1
        count=$((count + 1))
        echo -n "."
    done
    echo " [FAILED / TIMEOUT after ${max_retries}s]"
    return 1
}

case "$MODE" in
    status)
        echo "=========================================================="
        echo "  Cluster Compute Stack Status                            "
        echo "=========================================================="
        echo "Active Systemd Units:"
        systemctl list-units --type=service | grep -E "(llama|cluster)" || echo "No llama services active"
        echo ""
        echo "Listening Ports (8001-8004):"
        ss -tulpn | grep -E "(:8001|:8002|:8003|:8004|:8765)" || echo "None listening"
        echo ""
        echo "Active llama-server Processes:"
        ps aux | grep llama-server | grep -v grep || echo "No processes running"
        ;;

    rocm)
        echo "=========================================================="
        echo "  Switching to ROCm 10 / HIP Compute (Mode: $SUBMODE)     "
        echo "=========================================================="
        
        # Verify binary exists
        if [ ! -f "/usr/local/bin/llama-server-rocm" ]; then
            echo "ERROR: /usr/local/bin/llama-server-rocm not found! Run 02_build_rocm10_llamacpp.sh first."
            exit 1
        fi

        echo "[1/4] Stopping all active Vulkan services..."
        sudo systemctl stop llama-moe.service || true
        sudo systemctl stop llama-coordinator.service || true
        sudo systemctl stop llama-worker.service || true
        sudo systemctl stop llama-embed.service || true
        sleep 2

        echo "[2/4] Starting ROCm services for mode: $SUBMODE..."
        if [ "$SUBMODE" = "moe" ]; then
            sudo systemctl start llama-moe-rocm.service
            sudo systemctl start llama-embed-rocm.service
        else
            sudo systemctl start llama-coordinator-rocm.service
            sudo systemctl start llama-worker-rocm.service
            sudo systemctl start llama-embed-rocm.service
        fi

        echo "[3/4] Verifying ROCm health endpoints..."
        HEALTH_OK=true
        if [ "$SUBMODE" = "moe" ]; then
            if ! poll_health 8001 "MoE Coordinator (ROCm)" 45; then HEALTH_OK=false; fi
            if ! poll_health 8003 "Embedder (ROCm)" 20; then HEALTH_OK=false; fi
        else
            if ! poll_health 8001 "Coordinator (ROCm)" 30; then HEALTH_OK=false; fi
            if ! poll_health 8002 "Worker (ROCm)" 20; then HEALTH_OK=false; fi
            if ! poll_health 8003 "Embedder (ROCm)" 20; then HEALTH_OK=false; fi
        fi

        if [ "$HEALTH_OK" = true ]; then
            echo ""
            echo "=== Switch to ROCm Succeeded! ==="
            echo "Stack is fully online with native HIP acceleration."
        else
            echo ""
            echo "=========================================================="
            echo "  HEALTH CHECK FAILED! Triggering Automatic Rollback...   "
            echo "=========================================================="
            sudo systemctl stop llama-moe-rocm.service || true
            sudo systemctl stop llama-coordinator-rocm.service || true
            sudo systemctl stop llama-worker-rocm.service || true
            sudo systemctl stop llama-embed-rocm.service || true
            sleep 2
            
            echo "Restoring Vulkan baseline services..."
            if [ "$SUBMODE" = "moe" ]; then
                sudo systemctl start llama-moe.service
                sudo systemctl start llama-embed.service
            else
                sudo systemctl start llama-coordinator.service
                sudo systemctl start llama-worker.service
                sudo systemctl start llama-embed.service
            fi
            echo "Rollback complete. Vulkan stack is restored."
            exit 1
        fi
        ;;

    vulkan)
        echo "=========================================================="
        echo "  Switching to Vulkan Compute (Mode: $SUBMODE)            "
        echo "=========================================================="
        echo "[1/3] Stopping all active ROCm services..."
        sudo systemctl stop llama-moe-rocm.service || true
        sudo systemctl stop llama-coordinator-rocm.service || true
        sudo systemctl stop llama-worker-rocm.service || true
        sudo systemctl stop llama-embed-rocm.service || true
        sleep 2

        echo "[2/3] Starting Vulkan baseline services..."
        if [ "$SUBMODE" = "moe" ]; then
            sudo systemctl start llama-moe.service
            sudo systemctl start llama-embed.service
            poll_health 8001 "MoE Coordinator (Vulkan)" 30 || true
            poll_health 8003 "Embedder (Vulkan)" 20 || true
        else
            sudo systemctl start llama-coordinator.service
            sudo systemctl start llama-worker.service
            sudo systemctl start llama-embed.service
            poll_health 8001 "Coordinator (Vulkan)" 30 || true
            poll_health 8002 "Worker (Vulkan)" 20 || true
            poll_health 8003 "Embedder (Vulkan)" 20 || true
        fi
        echo ""
        echo "=== Switch to Vulkan Complete! ==="
        ;;

    *)
        echo "Usage: $0 {status|rocm [moe|dual]|vulkan [moe|dual]}"
        exit 1
        ;;
esac

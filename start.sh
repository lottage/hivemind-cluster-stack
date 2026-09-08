#!/usr/bin/env bash
set -e

echo "=== Launching Distributed Hive-Mind AI Stack ==="

if [ -f .env ]; then
    export $(cat .env | grep -v '#' | awk '/=/ {print $1}')
fi

mkdir -p data/thinking_archive data/qdrant_storage data/vault_backup

if command -v docker-compose &> /dev/null; then
    echo "Starting Qdrant & core stack via Docker Compose..."
    docker-compose up -d
else
    echo "Docker compose not found. Starting core bridge locally..."
    python3 core/mcp_server.py &
    python3 ui-stonesage/backend/server.py &
fi

echo "Stack online!"
echo "StoneSage Cockpit: http://localhost:8080"
echo "EasyDash UI:       http://localhost:8085"
echo "MCP Server:        http://localhost:8765/sse"

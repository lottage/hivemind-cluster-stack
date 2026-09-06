@echo off
title StoneSage Homelab Command Center
color 02

echo =====================================================================
echo   StoneSage Homelab Command Center + AI Cognitive Cockpit
echo   Dual-GPU Cluster: 14B Coordinator (:8001) + 3B Worker (:8002)
echo   Proxmox Nodes: pve (192.168.1.229) and bigserv (192.168.1.82)
echo   Home Assistant: http://192.168.1.82:8123
echo =====================================================================
echo.

:: Check if port 8080 is already held by a previous or background instance
for /f "tokens=5" %%a in ('netstat -aon ^| findstr ":8080" ^| findstr "LISTENING"') do (
    echo [i] Port 8080 is currently held by existing process PID %%a.
    echo [i] Terminating previous instance to ensure latest code is running...
    taskkill /f /pid %%a >nul 2>&1
    ping 127.0.0.1 -n 2 >nul
)

cd /d "%~dp0backend"
echo [*] Starting Python backend server...
python -u server.py

if errorlevel 1 (
    echo.
    echo [!] Server exited with an error.
    pause
)

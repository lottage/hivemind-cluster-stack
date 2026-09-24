@echo off
title StoneSage Homelab AI Cockpit & Harness Server (v0.02)
color 0b

echo =====================================================================
echo   StoneSage Homelab Command Center + AI Cognitive Cockpit (v0.02)
echo   Web Cockpit: http://localhost:8080 (or http://192.168.1.132:8080)
echo   Harness PTY WebSocket Daemon: ws://localhost:8088/ws
echo   Coordinator: http://192.168.1.105:8001 ^| Worker: :8002
echo =====================================================================
echo.

:: Free port 8080 if occupied
for /f "tokens=5" %%a in ('netstat -aon ^| findstr ":8080" ^| findstr "LISTENING"') do (
    echo [i] Port 8080 is held by PID %%a. Terminating...
    taskkill /f /pid %%a >nul 2>&1
    ping 127.0.0.1 -n 2 >nul
)

:: Free port 8088 if occupied
for /f "tokens=5" %%a in ('netstat -aon ^| findstr ":8088" ^| findstr "LISTENING"') do (
    echo [i] Port 8088 is held by PID %%a. Terminating...
    taskkill /f /pid %%a >nul 2>&1
    ping 127.0.0.1 -n 2 >nul
)

echo [*] Launching Harness Duplex PTY Daemon on port 8088...
start "Harness PTY Daemon (:8088)" cmd /c "python -u -m harness.server"

echo [*] Starting StoneSage Web Backend on port 8080...
cd /d "%~dp0StoneSage\backend"
python -u server.py

if errorlevel 1 (
    echo.
    echo [!] Server exited with an error.
    pause
)

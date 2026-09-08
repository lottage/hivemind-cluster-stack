@echo off
title EasyDash - Homelab Dashboard & Antigravity Bridge
echo =======================================================
echo  Starting EasyDash on http://localhost:8080 ...
echo  Press Ctrl+C to stop.
echo =======================================================
start http://localhost:8080
python server.py 8080
pause

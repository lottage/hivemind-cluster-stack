@echo off
echo === Launching Distributed Hive-Mind AI Stack ===

if not exist data mkdir data
if not exist data\thinking_archive mkdir data\thinking_archive

echo Starting StoneSage backend...
start /b python ui-stonesage\backend\server.py

echo Starting EasyDash backend...
start /b python ui-easydash\server.py --port 8085

echo Stack online!
echo StoneSage Cockpit: http://localhost:8080
echo EasyDash UI:       http://localhost:8085

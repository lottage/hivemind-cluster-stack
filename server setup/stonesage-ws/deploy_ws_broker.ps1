# Deploy StoneSage WebSocket Broker to LXC 120 (stonesage @ 192.168.1.167 on bigserv)
param(
    [string]$TargetHost = "192.168.1.167",
    [string]$TargetUser = "root"
)

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path

# 1. Create /opt/stonesage-ws on target
ssh -o BatchMode=yes "$TargetUser@$TargetHost" "mkdir -p /opt/stonesage-ws"

# 2. Upload ws_broker.py and service
scp "$ScriptDir\ws_broker.py" "$TargetUser@$TargetHost`:/opt/stonesage-ws/ws_broker.py"
scp "$ScriptDir\stonesage-ws.service" "$TargetUser@$TargetHost`:/etc/systemd/system/stonesage-ws.service"

# 3. Reload systemd & restart service
ssh -o BatchMode=yes "$TargetUser@$TargetHost" "systemctl daemon-reload && systemctl enable stonesage-ws.service && systemctl restart stonesage-ws.service"

Start-Sleep -Seconds 1
ssh -o BatchMode=yes "$TargetUser@$TargetHost" "systemctl status stonesage-ws.service --no-pager -n 5"

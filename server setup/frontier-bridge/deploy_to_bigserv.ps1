# Deploy Frontier Bridge to LXC 120 (stonesage @ 192.168.1.167 on bigserv)
param(
    [string]$TargetHost = "192.168.1.167",
    [string]$TargetUser = "root"
)

Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host "  Deploying Frontier Bridge -> $TargetUser@$TargetHost" -ForegroundColor Cyan
Write-Host "==========================================================" -ForegroundColor Cyan

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path

# 1. Create /opt/frontier-bridge on target
Write-Host "`n[1/4] Ensuring /opt/frontier-bridge exists on $TargetHost..." -ForegroundColor Yellow
ssh -o BatchMode=yes "$TargetUser@$TargetHost" "mkdir -p /opt/frontier-bridge"

# 2. Upload files
Write-Host "`n[2/4] Uploading server.py and config.json..." -ForegroundColor Yellow
scp "$ScriptDir\server.py" "$TargetUser@$TargetHost`:/opt/frontier-bridge/server.py"
scp "$ScriptDir\config.json" "$TargetUser@$TargetHost`:/opt/frontier-bridge/config.json"
scp "$ScriptDir\frontier-bridge.service" "$TargetUser@$TargetHost`:/etc/systemd/system/frontier-bridge.service"

# 3. Reload systemd & restart service
Write-Host "`n[3/4] Enabling and starting frontier-bridge.service..." -ForegroundColor Yellow
ssh -o BatchMode=yes "$TargetUser@$TargetHost" "systemctl daemon-reload && systemctl enable frontier-bridge.service && systemctl restart frontier-bridge.service"

# 4. Probe /health
Write-Host "`n[4/4] Verifying service health on http://$TargetHost`:8085/health..." -ForegroundColor Yellow
Start-Sleep -Seconds 1
$Health = Invoke-RestMethod -Uri "http://$TargetHost`:8085/health" -TimeoutSec 5
$Health | ConvertTo-Json

Write-Host "`n==========================================================" -ForegroundColor Green
Write-Host "  Frontier Bridge deployed and active on port 8085!" -ForegroundColor Green
Write-Host "==========================================================" -ForegroundColor Green

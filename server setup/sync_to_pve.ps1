# Sync updated cluster files from Windows to Ubuntu VM (192.168.1.105) on node 'pve'
param(
    [string]$VmHost = "192.168.1.105",
    [string]$VmUser = "austin"
)

Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host "  PVE Cluster Sync: Windows -> $VmUser@$VmHost" -ForegroundColor Cyan
Write-Host "==========================================================" -ForegroundColor Cyan

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path

# 1. SCP the cluster-bridge and vm-setup directories to /tmp on the VM
Write-Host "`n[1/3] Uploading cluster-bridge to /tmp/cluster-bridge..." -ForegroundColor Yellow
scp -r "$ScriptDir\cluster-bridge" "$VmUser@$VmHost`:/tmp/"

Write-Host "`n[2/3] Uploading vm-setup to /tmp/vm-setup..." -ForegroundColor Yellow
scp -r "$ScriptDir\vm-setup" "$VmUser@$VmHost`:/tmp/"

# 2. Execute atomic move and systemctl reload over SSH
Write-Host "`n[3/3] Deploying to /opt and restarting cluster-mcp.service..." -ForegroundColor Yellow
$RemoteCommand = "sudo cp -r /tmp/cluster-bridge/* /opt/cluster-bridge/ && sudo cp /tmp/vm-setup/systemd/cluster-mcp.service /etc/systemd/system/cluster-mcp.service && sudo systemctl daemon-reload && sudo systemctl restart cluster-mcp.service && sudo systemctl status cluster-mcp.service --no-pager -n 5"

ssh -t "$VmUser@$VmHost" $RemoteCommand

Write-Host "`n==========================================================" -ForegroundColor Green
Write-Host "  Sync Complete! MCP bridge updated and running." -ForegroundColor Green
Write-Host "==========================================================" -ForegroundColor Green

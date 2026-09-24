# Deploy PVE Hardware Watchdog to LXC 120 (stonesage @ 192.168.1.167) on bigserv
param(
    [string]$LxcHost = "192.168.1.167",
    [string]$LxcUser = "root",
    [switch]$DryRun = $false
)

$ErrorActionPreference = "Stop"

Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host "  Deploying PVE Hardware Watchdog to $LxcUser@$LxcHost" -ForegroundColor Cyan
Write-Host "==========================================================" -ForegroundColor Cyan

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$WatchdogPy = Join-Path $ScriptDir "pve_hardware_watchdog.py"
$ServiceFile = Join-Path $ScriptDir "pve-watchdog.service"

# 1. Create target directory on LXC
Write-Host "`n[1/4] Creating remote directory /opt/pve-watchdog..." -ForegroundColor Yellow
ssh -n "$LxcUser@$LxcHost" "mkdir -p /opt/pve-watchdog"

# 2. SCP files
Write-Host "`n[2/4] Uploading watchdog files..." -ForegroundColor Yellow
scp "$WatchdogPy" "$LxcUser@$LxcHost`:/opt/pve-watchdog/pve_hardware_watchdog.py"
scp "$ServiceFile" "$LxcUser@$LxcHost`:/etc/systemd/system/pve-watchdog.service"

# 3. Set permissions
Write-Host "`n[3/4] Configuring execution permissions..." -ForegroundColor Yellow
ssh -n "$LxcUser@$LxcHost" "chmod +x /opt/pve-watchdog/pve_hardware_watchdog.py"

# 4. Run probe verification
Write-Host "`n[4/4] Verifying smart plug and multi-vector cluster probes..." -ForegroundColor Yellow
ssh -n "$LxcUser@$LxcHost" "python3 /opt/pve-watchdog/pve_hardware_watchdog.py --test-plug"
ssh -n "$LxcUser@$LxcHost" "python3 /opt/pve-watchdog/pve_hardware_watchdog.py --test-probes"

Write-Host "`n[5/5] Reloading systemd and enabling service..." -ForegroundColor Yellow
ssh -n "$LxcUser@$LxcHost" "systemctl daemon-reload && systemctl enable pve-watchdog.service && systemctl restart pve-watchdog.service"
ssh -n "$LxcUser@$LxcHost" "systemctl status pve-watchdog.service --no-pager"

Write-Host "`n==========================================================" -ForegroundColor Green
Write-Host "  Deployment Complete! Watchdog is actively monitoring.  " -ForegroundColor Green
Write-Host "==========================================================" -ForegroundColor Green

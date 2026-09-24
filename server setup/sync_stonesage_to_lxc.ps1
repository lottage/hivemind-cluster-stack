# Sync updated StoneSage Frontend and Backend to LXC 120 (stonesage @ 192.168.1.167) on bigserv
param(
    [string]$LxcHost = "192.168.1.167",
    [string]$LxcUser = "root"
)

$ErrorActionPreference = "Stop"

Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host "  Syncing StoneSage Code: Windows -> $LxcUser@$LxcHost" -ForegroundColor Cyan
Write-Host "==========================================================" -ForegroundColor Cyan

$WorkspaceRoot = "C:\Users\johna\OneDrive\Documents\.ai"
$LocalFrontend = "$WorkspaceRoot\StoneSage\frontend"
$LocalBackend = "$WorkspaceRoot\StoneSage\backend"

# 1. Sync Frontend HTML/CSS/JS (excluding .apk files)
Write-Host "`n[1/3] Uploading Frontend assets to LXC 120..." -ForegroundColor Yellow
ssh -n "$LxcUser@$LxcHost" "mkdir -p /opt/stonesage/frontend/js /opt/stonesage/frontend/vendor/xterm"

scp "$LocalFrontend\index.html" "$LxcUser@$LxcHost`:/opt/stonesage/frontend/index.html"
scp "$LocalFrontend\style.css" "$LxcUser@$LxcHost`:/opt/stonesage/frontend/style.css"
scp "$LocalFrontend\app.js" "$LxcUser@$LxcHost`:/opt/stonesage/frontend/app.js"
scp "$LocalFrontend\sw.js" "$LxcUser@$LxcHost`:/opt/stonesage/frontend/sw.js"
scp "$LocalFrontend\manifest.webmanifest" "$LxcUser@$LxcHost`:/opt/stonesage/frontend/manifest.webmanifest"
scp "$LocalFrontend\icon.svg" "$LxcUser@$LxcHost`:/opt/stonesage/frontend/icon.svg"

# Copy modular js directory and vendor assets
scp -r "$LocalFrontend\js" "$LxcUser@$LxcHost`:/opt/stonesage/frontend/"
scp -r "$LocalFrontend\vendor" "$LxcUser@$LxcHost`:/opt/stonesage/frontend/"

# 2. Sync Backend Python modules (preserving config.json)
Write-Host "`n[2/3] Uploading Backend Python modules to LXC 120..." -ForegroundColor Yellow
Get-ChildItem -Path "$LocalBackend" -Filter "*.py" | ForEach-Object {
    scp $_.FullName "$LxcUser@$LxcHost`:/opt/stonesage/backend/$($_.Name)"
}
# Remove any legacy builtin_overrides.json on LXC 120
ssh -n "$LxcUser@$LxcHost" "rm -f /opt/stonesage/backend/builtin_overrides.json"

# 2.5 Sync Harness, Context Fabric, and Valkey A-MEM packages
Write-Host "`n[2.5/3] Uploading Harness & Valkey A-MEM data fabric to LXC 120..." -ForegroundColor Yellow
scp -r "$WorkspaceRoot\harness" "$LxcUser@$LxcHost`:/opt/stonesage/backend/"
ssh -n "$LxcUser@$LxcHost" "mkdir -p /opt/stonesage/backend/data/agent_dna"
if (Test-Path "$WorkspaceRoot\data\agent_dna") {
    scp -r "$WorkspaceRoot\data\agent_dna" "$LxcUser@$LxcHost`:/opt/stonesage/backend/data/"
}

# 3. Restart stonesage services on LXC 120
Write-Host "`n[3/3] Restarting stonesage service on LXC 120..." -ForegroundColor Yellow
ssh -n "$LxcUser@$LxcHost" "systemctl restart stonesage.service"
ssh -n "$LxcUser@$LxcHost" "systemctl status stonesage.service --no-pager -n 5"

Write-Host "`n==========================================================" -ForegroundColor Green
Write-Host "  StoneSage Sync Complete! Fresh GUI is live on :8888.   " -ForegroundColor Green
Write-Host "==========================================================" -ForegroundColor Green

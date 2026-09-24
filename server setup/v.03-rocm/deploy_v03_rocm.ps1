# Deploy v.03-rocm Parallel Build to Ubuntu VM (192.168.1.105) on Proxmox node 'pve'
param(
    [string]$VmHost = "192.168.1.105",
    [string]$VmUser = "austin",
    [switch]$BuildNow = $false
)

$ErrorActionPreference = "Stop"

Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host "  Deploying Parallel Build: v.03-rocm -> $VmUser@$VmHost" -ForegroundColor Cyan
Write-Host "==========================================================" -ForegroundColor Cyan

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
# Clean Windows OpenSSH path according to workspace invariant
$SourcePath = $ScriptDir.TrimEnd('\').TrimEnd('/')

# 1. SCP v.03-rocm to /tmp on VM 102
Write-Host "`n[1/3] Uploading v.03-rocm package to /tmp/v.03-rocm..." -ForegroundColor Yellow
scp -r "$SourcePath" "$VmUser@$VmHost`:/tmp/v.03-rocm"

# 2. Set execute permissions on VM 102
Write-Host "`n[2/3] Setting remote script permissions..." -ForegroundColor Yellow
ssh -n "$VmUser@$VmHost" "chmod +x /tmp/v.03-rocm/*.sh"

Write-Host "`n[3/3] v.03-rocm package successfully staged on $VmHost in /tmp/v.03-rocm!" -ForegroundColor Green

if ($BuildNow) {
    Write-Host "`n=== Launching Automated ROCm Build & Service Registration ===" -ForegroundColor Cyan
    ssh -t "$VmUser@$VmHost" "cd /tmp/v.03-rocm && ./01_install_rocm10.sh && ./02_build_rocm10_llamacpp.sh && ./03_install_rocm_services.sh"
} else {
    Write-Host "`nTo proceed with compilation and testing, SSH into the VM:" -ForegroundColor White
    Write-Host "  ssh $VmUser@$VmHost" -ForegroundColor Yellow
    Write-Host "  cd /tmp/v.03-rocm" -ForegroundColor Yellow
    Write-Host "  ./01_install_rocm10.sh          # Install ROCm 10 packages" -ForegroundColor Gray
    Write-Host "  ./02_build_rocm10_llamacpp.sh   # Build /usr/local/bin/llama-server-rocm" -ForegroundColor Gray
    Write-Host "  ./03_install_rocm_services.sh   # Register systemd unit files" -ForegroundColor Gray
    Write-Host "  ./switch_stack.sh rocm moe      # Safely test ROCm stack (auto-rollback if fails)" -ForegroundColor Gray
    Write-Host "  ./switch_stack.sh vulkan        # Return to Vulkan baseline anytime" -ForegroundColor Gray
}

Write-Host "`n==========================================================" -ForegroundColor Green
Write-Host "  Staging Complete! Production Vulkan Stack Unaltered." -ForegroundColor Green
Write-Host "==========================================================" -ForegroundColor Green

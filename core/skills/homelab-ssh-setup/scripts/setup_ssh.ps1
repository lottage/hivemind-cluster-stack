# Helper script for homelab-ssh-setup skill
param(
    [string]$TargetHost = "127.0.0.1",
    [string]$TargetUser = "clusteradmin"
)

$KeyPath = "$HOME\.ssh\id_ed25519"
$PubPath = "$KYOUR_LONG_LIVED_TOKEN_HERE"

Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host "  Homelab Passwordless SSH Setup Engine" -ForegroundColor Cyan
Write-Host "  Target: $TargetUser@$TargetHost" -ForegroundColor Cyan
Write-Host "==========================================================" -ForegroundColor Cyan

# 1. Generate key if missing
if (-not (Test-Path $PubPath)) {
    Write-Host "`n[1/3] Generating new Ed25519 key pair..." -ForegroundColor Yellow
    if (-not (Test-Path "$HOME\.ssh")) {
        New-Item -ItemType Directory -Path "$HOME\.ssh" -Force | Out-Null
    }
    ssh-keygen -t ed25519 -f $KeyPath -N '""'
    if ($LASTEXITCODE -ne 0) {
        Write-Error "Failed to generate SSH key."
        exit 1
    }
} else {
    Write-Host "`n[1/3] Existing Ed25519 public key found at $PubPath" -ForegroundColor Green
}

# 2. Deploy public key to remote host
Write-Host "`n[2/3] Deploying public key to $TargetUser@$TargetHost..." -ForegroundColor Yellow
Write-Host "Enter the remote user password when prompted below:" -ForegroundColor Gray

$DeployCmd = "mkdir -p ~/.ssh && chmod 700 ~/.ssh && cat >> ~/.ssh/authorized_keys && chmod 600 ~/.ssh/authorized_keys"
Get-Content $PubPath | ssh "$TargetUser@$TargetHost" $DeployCmd

# 3. Test passwordless connection
Write-Host "`n[3/3] Verifying passwordless connection..." -ForegroundColor Yellow
$TestResult = ssh -o BatchMode=yes -o ConnectTimeout=5 "$TargetUser@$TargetHost" "echo 'AUTH_SUCCESS'" 2>&1

if ($TestResult -match "AUTH_SUCCESS") {
    Write-Host "`n==========================================================" -ForegroundColor Green
    Write-Host "  SUCCESS! Passwordless SSH is verified and active!" -ForegroundColor Green
    Write-Host "  You can now connect without password prompts via:" -ForegroundColor Green
    Write-Host "    ssh $TargetUser@$TargetHost" -ForegroundColor White
    Write-Host "==========================================================" -ForegroundColor Green
} else {
    Write-Host "`n[WARNING] BatchMode authentication test returned: $TestResult" -ForegroundColor Red
}

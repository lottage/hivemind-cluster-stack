# Run Obsidian Status Daemon
param(
    [string]$VaultDir = "C:\Users\johna\OneDrive\Documents\obsidian",
    [int]$BaseInterval = 60,
    [switch]$Once
)

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$DaemonPy = Join-Path $ScriptDir "obsidian_status_daemon.py"

Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host "   Obsidian Homelab & AI Stack Status Daemon Launcher     " -ForegroundColor Cyan
Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host "Vault: $VaultDir" -ForegroundColor Yellow
Write-Host "Interval: ${BaseInterval}s" -ForegroundColor Yellow

$Params = @("--vault-dir", "$VaultDir", "--base-interval", "$BaseInterval")
if ($Once) {
    $Params += "--once"
}

python -u "$DaemonPy" @Params

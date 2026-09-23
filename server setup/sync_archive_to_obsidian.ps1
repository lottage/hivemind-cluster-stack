# High-speed Autonomous Thinking Dossier Sync to Obsidian Vault
param(
    [string]$VmHost = "192.168.1.105",
    [string]$VmUser = "austin",
    [string]$RemoteDir = "",
    [string]$ObsidianVaultDir = "C:\Users\johna\OneDrive\Documents\obsidian\Autonomous Thinking"
)

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$pythonScript = Join-Path $scriptDir "sync_archive_to_obsidian.py"

python "$pythonScript"


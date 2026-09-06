# Pull latest Current Status.md from 24/7 StoneSage container (LXC 120) to local Obsidian vault
param(
    [string]$LxcUrl = "http://192.168.1.167:8080/api/status/markdown",
    [string]$TargetFile = "C:\Users\johna\OneDrive\Documents\obsidian\Current Status.md"
)

try {
    $content = (Invoke-WebRequest -Uri $LxcUrl -UseBasicParsing -TimeoutSec 5).Content
    if ($content -and $content.Length -gt 100) {
        [System.IO.File]::WriteAllText($TargetFile, $content, [System.Text.Encoding]::UTF8)
        Write-Host "[OK] Synced Current Status.md from $LxcUrl" -ForegroundColor Green
    } else {
        Write-Host "[!] Received empty or invalid content from $LxcUrl" -ForegroundColor Yellow
    }
} catch {
    Write-Host "[!] Failed to sync from $LxcUrl : $_" -ForegroundColor Red
}

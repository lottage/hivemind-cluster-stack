# Synchronize 24/7 Autonomous Thinking Dossiers from Ubuntu VM (or local) to Obsidian Vault
param(
    [string]$VmHost = "192.168.1.105",
    [string]$VmUser = "austin",
    [string]$RemoteDir = "",
    [string]$ObsidianVaultDir = "C:\Users\johna\OneDrive\Documents\obsidian\Autonomous Thinking"
)

Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host "  Sync Autonomous Thinking Dossiers -> Obsidian Vault     " -ForegroundColor Cyan
Write-Host "==========================================================" -ForegroundColor Cyan

$ExplorationsDir = Join-Path $ObsidianVaultDir "Explorations"
if (-not (Test-Path $ExplorationsDir)) {
    New-Item -ItemType Directory -Path $ExplorationsDir -Force | Out-Null
    Write-Host "Created Obsidian directory: $ExplorationsDir" -ForegroundColor Green
}

$CandidateRemoteDirs = @()
if ($RemoteDir -ne "") {
    $CandidateRemoteDirs += $RemoteDir
}
$CandidateRemoteDirs += "/opt/cluster-bridge/thinking_archive"
$CandidateRemoteDirs += "/home/austin/cluster-bridge/thinking_archive"
$CandidateRemoteDirs = $CandidateRemoteDirs | Select-Object -Unique

$TempDir = Join-Path $env:TEMP "thinking_sync_$(Get-Random)"
New-Item -ItemType Directory -Path $TempDir -Force | Out-Null

try {
    $SyncedFrom = @()
    foreach ($rDir in $CandidateRemoteDirs) {
        Write-Host "`n[1/2] Probing remote archive: $VmUser@$VmHost`:$rDir..." -ForegroundColor Yellow
        $dirCheck = ssh -o BatchMode=yes -o ConnectTimeout=4 "$VmUser@$VmHost" "test -d '$rDir' && ls -1 '$rDir'/*.md 2>/dev/null | wc -l" 2>$null
        if ($LASTEXITCODE -eq 0 -and $dirCheck -and [int]($dirCheck.Trim()) -gt 0) {
            Write-Host "  Found $([int]($dirCheck.Trim())) files in $rDir. Fetching..." -ForegroundColor Green
            # Strip trailing slash from temp dir to prevent OpenSSH path escape issue on Windows
            $cleanTemp = $TempDir.TrimEnd('\').TrimEnd('/')
            scp -o BatchMode=yes "$VmUser@$VmHost`:$rDir/*.md" "$cleanTemp" 2>$null
            $SyncedFrom += $rDir
            break
        } else {
            Write-Host "  Directory empty or not present: $rDir" -ForegroundColor DarkGray
        }
    }

    $Files = Get-ChildItem -Path $TempDir -Filter "*.md"
    if ($Files.Count -eq 0) {
        Write-Host "`nNo markdown dossiers found across candidate remote directories." -ForegroundColor Yellow
        return
    }

    Write-Host "`n[2/2] Ingesting $($Files.Count) files into Obsidian Vault ($ObsidianVaultDir)..." -ForegroundColor Yellow

    foreach ($file in $Files) {
        $destPath = ""
        if ($file.Name -eq "ARCHITECTURE_LIMITS_SYNTHESIS.md") {
            $destPath = Join-Path $ObsidianVaultDir $file.Name
            $content = Get-Content -Path $file.FullName -Raw -Encoding UTF8
            $rewritten = [System.Text.RegularExpressions.Regex]::Replace(
                $content,
                '\[`?(EXP-[A-Za-z0-9\-]+)`?\]\((EXP-[A-Za-z0-9\-]+\.md)\)',
                '[`$1`](Explorations/$2)'
            )
            [System.IO.File]::WriteAllText($destPath, $rewritten, [System.Text.Encoding]::UTF8)
            Write-Host "  Updated master synthesis: $($file.Name)" -ForegroundColor Cyan
        } elseif ($file.Name -like "*HOME*VISION*LOG*.md" -or $file.Name -eq "HOME_AND_VISION_ACTIVITY_LOG.md") {
            $destPath = Join-Path $ObsidianVaultDir "Home & Vision Activity Log.md"
            Copy-Item -Path $file.FullName -Destination $destPath -Force
            Write-Host "  Updated Home & Vision Activity Log: Home & Vision Activity Log.md" -ForegroundColor Green
        } else {
            $destPath = Join-Path $ExplorationsDir $file.Name
            $content = Get-Content -Path $file.FullName -Raw -Encoding UTF8
            if ($content -match "## 5\. Tier-1 Frontier Audit \(Antigravity\)" -and $content -match "### Verdict:\s*([A-Z_]+)") {
                $verdict = $Matches[1]
                $content = [System.Text.RegularExpressions.Regex]::Replace(
                    $content,
                    '- \*\*Frontier Verified\*\*:.*',
                    "- **Frontier Verified**: ``True`` ($verdict)"
                )
            }
            [System.IO.File]::WriteAllText($destPath, $content, [System.Text.Encoding]::UTF8)
            Write-Host "  Synced dossier: $($file.Name)" -ForegroundColor Gray
        }
    }

    Write-Host "`n==========================================================" -ForegroundColor Green
    Write-Host "  Sync Complete! $($Files.Count) files available in Obsidian." -ForegroundColor Green
    Write-Host "  Obsidian Directory: $ObsidianVaultDir" -ForegroundColor Green
    Write-Host "  Sources Synced: $($SyncedFrom -join ', ')" -ForegroundColor Green
    Write-Host "==========================================================" -ForegroundColor Green
} catch {
    Write-Host "Error syncing files: $_" -ForegroundColor Red
} finally {
    if (Test-Path $TempDir) {
        Remove-Item -Path $TempDir -Recurse -Force -ErrorAction SilentlyContinue
    }
}

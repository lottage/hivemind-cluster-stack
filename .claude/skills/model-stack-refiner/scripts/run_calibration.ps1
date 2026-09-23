# Run Model Stack Calibration Loop & Parameter Refiner
param(
    [string]$CoordinatorUrl = "http://127.0.0.1:8001",
    [string]$WorkerUrl = "http://127.0.0.1:8002",
    [double]$TargetCii = 8.5,
    [string]$ObsidianVaultDir = "C:\Users\admin\OneDrive\Documents\obsidian\Autonomous Thinking"
)

Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host "   Model Stack Parameter Refiner & Calibration Loop       " -ForegroundColor Cyan
Write-Host "==========================================================" -ForegroundColor Cyan

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$PyScript = Join-Path $ScriptDir "calibration_loop.py"
$SuitePath = Join-Path (Split-Path -Parent $ScriptDir) "references\benchmark_suite.json"
$OutDir = Join-Path $ScriptDir "reports"

Write-Host "Checking python environment..." -ForegroundColor Yellow
python --version

Write-Host "Launching calibration battery across 5 critical domains..." -ForegroundColor Yellow
python "$PyScript" --coord-url "$CoordinatorUrl" --worker-url "$WorkerUrl" --suite "$SuitePath" --target-cii $TargetCii --out-dir "$OutDir"

$ReportFile = Join-Path $OutDir "calibration_report.json"
if (Test-Path $ReportFile) {
    $CalibDir = Join-Path $ObsidianVaultDir "Calibration"
    if (-not (Test-Path $CalibDir)) {
        New-Item -ItemType Directory -Path $CalibDir -Force | Out-Null
    }
    
    $DestFile = Join-Path $CalibDir "MODEL_CALIBRATION_REPORT.json"
    Copy-Item -Path $ReportFile -Destination $DestFile -Force
    Write-Host "`nSynced calibration report to Obsidian: $DestFile" -ForegroundColor Green
}

# Register Scheduled Task for Database to Obsidian Sync
$ScriptPath = "c:\Users\admin\OneDrive\Documents\.ai\.agents\skills\database-memory-sync\sync_db_to_obsidian.py"
$PythonPath = (Get-Command python.exe).Source

$Action = New-ScheduledTaskAction -Execute $PythonPath -Argument "`"$ScriptPath`""
$Trigger = New-ScheduledTaskTrigger -Daily -At "00:00"
$Trigger.Repetition = (New-ScheduledTaskTrigger -Once -At (Get-Date) -RepetitionInterval (New-TimeSpan -Minutes 30) -RepetitionDuration (New-TimeSpan -Days 365)).Repetition
$Settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable

Register-ScheduledTask -TaskName "HomelabObsidianDbSync" -Action $Action -Trigger $Trigger -Settings $Settings -Description "Syncs Qdrant vector database summary to Obsidian every 30 minutes" -Force
Write-Host "[OK] Registered Windows Scheduled Task: HomelabObsidianDbSync (runs every 30 mins)"

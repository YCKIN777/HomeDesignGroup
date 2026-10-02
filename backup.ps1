# backup.ps1 - HomeDesignGroup AI Platform data backup
# Usage:  .\backup.ps1                 -> backup to backups\<timestamp>\
#         .\backup.ps1 -Out D:\mybackup -> backup to custom dir
# Covers: db/ (per-company databases), company_profiles/, knowledge/,
#         memory/, sedimentation/, config/, CHANGELOG.md
param([string]$Out = "backups")

$root = $PSScriptRoot
$ts = Get-Date -Format "yyyyMMdd-HHmmss"
$dest = Join-Path $root (Join-Path $Out $ts)

$dirs = @("db", "company_profiles", "knowledge", "memory", "sedimentation", "config")
$copied = @()
foreach ($d in $dirs) {
    $src = Join-Path $root $d
    if (Test-Path $src) {
        $dst = Join-Path $dest $d
        New-Item -ItemType Directory -Force $dst | Out-Null
        Copy-Item -Path (Join-Path $src "*") -Destination $dst -Recurse -Force
        $copied += $d
    }
}

foreach ($f in @("CHANGELOG.md")) {
    $src = Join-Path $root $f
    if (Test-Path $src) {
        Copy-Item -Path $src -Destination $dest -Force
        $copied += $f
    }
}

Write-Output ("[backup] done -> " + $dest)
Write-Output ("[backup] backed up: " + ($copied -join ", "))
Write-Output "[backup] note: stop the 8000-port server before backing up the DB"

# scripts/version_bumper.ps1
param (
    [Parameter(Mandatory=$true)] [string]$NewVersion,
    [Parameter(Mandatory=$true)] [string]$CurrentVersion
)

$ErrorActionPreference = "Stop"
$Year = (Get-Date).Year
$DateReleased = Get-Date -Format "yyyy-MM-dd"

$ProjectRoot = Resolve-Path "$PSScriptRoot\.."

Write-Host "--- STARTING FILE UPDATES IN: $ProjectRoot ---" -ForegroundColor Cyan

# Update pyproject.toml
Write-Host "Updating pyproject.toml..."
$PyprojectPath = Join-Path $ProjectRoot "pyproject.toml"
(Get-Content $PyprojectPath) -replace "version = `"$CurrentVersion`"", "version = `"$NewVersion`"" | Set-Content $PyprojectPath

# Update README.md Citation
Write-Host "Updating README.md Citation..."
$ReadmePath = Join-Path $ProjectRoot "README.md"
$CitationPattern = "Grand'Maison, L\.-V\. \(\d{4}\)\. Phytospatial \(.*?\)\. Zenodo"
$NewCitation = "Grand'Maison, L.-V. ($Year). Phytospatial ($NewVersion). Zenodo"
(Get-Content $ReadmePath) -replace $CitationPattern, $NewCitation | Set-Content $ReadmePath

# Update LICENSE-MIT Copyright
Write-Host "Updating LICENSE-MIT Copyright..."
$MITPath = Join-Path $ProjectRoot "LICENSE-MIT"
(Get-Content $MITPath) -replace "Copyright \(c\) 2024-\d{4}", "Copyright (c) 2024-$Year" | Set-Content $MITPath

# Update NOTICE
Write-Host "Updating NOTICE..."
$NoticePath = Join-Path $ProjectRoot "NOTICE"
(Get-Content $NoticePath) -replace "Copyright 2024-\d{4}", "Copyright 2024-$Year" | Set-Content $NoticePath

# Update src/phytospatial/__init__.py
Write-Host "Updating src/phytospatial/__init__.py..."
$InitPath = Join-Path $ProjectRoot "src\phytospatial\__init__.py"
if (Test-Path $InitPath) {
    (Get-Content $InitPath) -replace "# Copyright 2024-\d{4}", "# Copyright 2024-$Year" | Set-Content $InitPath
}

# Update CITATION.cff
Write-Host "Updating CITATION.cff..."
$CffPath = Join-Path $ProjectRoot "CITATION.cff"
$CffContent = Get-Content $CffPath
$CffContent = $CffContent -replace "^version:.*$", "version: $NewVersion"
$CffContent = $CffContent -replace "^date-released:.*$", "date-released: $DateReleased"
$CffContent | Set-Content $CffPath

Write-Host "All files updated successfully." -ForegroundColor Green
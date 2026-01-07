# scripts/publish_trigger.ps1

$ErrorActionPreference = "Stop"
$MainBranch = "main"

Write-Host "--- PRODUCTION RELEASE TRIGGER ---" -ForegroundColor Magenta

# Verification Checks
Write-Host "Checking Git Status..."
if ((git status -s)) { Write-Error "Working directory is dirty. Commit changes first." }

Write-Host "Syncing with Remote..."
git fetch origin
$LocalHash = git rev-parse HEAD
$RemoteHash = git rev-parse "origin/$MainBranch"

if ($LocalHash -ne $RemoteHash) { Write-Error "Local branch is not in sync with remote. Pull or Push first." }

# Run Test Suite
Write-Host "--- RUNNING TEST SUITE ---" -ForegroundColor Cyan
pytest
if ($LASTEXITCODE -ne 0) { Write-Error "Tests failed. Release aborted." }
Write-Host "Tests passed." -ForegroundColor Green

# Version Bump
$CurrentVersion = Select-String -Path "pyproject.toml" -Pattern 'version = "(.*)"' | ForEach-Object { $_.Matches.Groups[1].Value }
Write-Host "Current Version: $CurrentVersion"
$NewVersion = Read-Host "Enter NEW RELEASE version"

if ([string]::IsNullOrWhiteSpace($NewVersion)) { Write-Error "Version required."; exit }

Write-Host "Updating pyproject.toml..."
(Get-Content "pyproject.toml") -replace "version = `"$CurrentVersion`"", "version = `"$NewVersion`"" | Set-Content "pyproject.toml"

# Git Operations
Write-Host "Committing and Tagging..."
git add pyproject.toml
git commit -m "Bump version to $NewVersion"
git tag -a "v$NewVersion" -m "Release v$NewVersion"

Write-Host "Pushing to GitHub..."
git push origin "$MainBranch"
git push origin "v$NewVersion"

# Create GitHub Release (Metadata only)
Write-Host "Creating GitHub Release Draft..."
gh release create "v$NewVersion" --generate-notes --title "v$NewVersion"

Write-Host "SUCCESS! Tag v$NewVersion pushed." -ForegroundColor Green
Write-Host "Monitor the upload progress here: https://github.com/Louis-Gm/phytospatial/actions" -ForegroundColor Gray
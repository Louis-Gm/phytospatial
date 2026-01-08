# scripts/test_release.ps1
$ErrorActionPreference = "Stop"

Write-Host "--- TEST RELEASE ---" -ForegroundColor Yellow

# Ask for Temporary Version
$CurrentVersion = Select-String -Path "pyproject.toml" -Pattern 'version = "(.*)"' | ForEach-Object { $_.Matches.Groups[1].Value }
Write-Host "Current Version: $CurrentVersion"
$NewVersion = Read-Host "Enter temporary test version (e.g., 4.2.0)"

if ([string]::IsNullOrWhiteSpace($NewVersion)) { Write-Error "Version required."; exit }

# Modify pyproject.toml
(Get-Content "pyproject.toml") -replace "version = `"$CurrentVersion`"", "version = `"$NewVersion`"" | Set-Content "pyproject.toml"

try {
    # CLEAN BUILD ARTIFACTS
    Write-Host "--- CLEANING OLD BUILDS ---" -ForegroundColor Cyan
    if (Test-Path "dist") { Remove-Item -Recurse -Force "dist" }
    if (Test-Path "build") { Remove-Item -Recurse -Force "build" }
    Get-ChildItem -Filter "*.egg-info" -Recurse | Remove-Item -Recurse -Force

    # BUILD
    Write-Host "--- BUILDING PACKAGE ---" -ForegroundColor Cyan
    python -m build

    # UPLOAD
    Write-Host "--- UPLOADING TO TESTPYPI ---" -ForegroundColor Cyan
    twine upload --repository testpypi dist/*

    Write-Host "Upload successful. Verification complete." -ForegroundColor Green
}
catch {
    Write-Error "Test release failed: $_"
}
finally {
    # REVERT CHANGES
    Write-Host "--- REVERTING LOCAL CHANGES ---" -ForegroundColor Yellow
    git checkout pyproject.toml
    Write-Host "Reverted pyproject.toml to original state." -ForegroundColor Gray
}
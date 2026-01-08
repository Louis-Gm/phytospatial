# scripts/version_bumper.ps1
param (
    [Parameter(Mandatory=$true)]
    [string]$NewVersion,

    [Parameter(Mandatory=$true)]
    [string]$CurrentVersion
)

$ErrorActionPreference = "Stop"
$Year = (Get-Date).Year
$DateReleased = Get-Date -Format "yyyy-MM-dd"

Write-Host "--- STARTING FILE UPDATES ---" -ForegroundColor Cyan

# Update pyproject.toml
Write-Host "Updating pyproject.toml..."
(Get-Content "pyproject.toml") -replace "version = `"$CurrentVersion`"", "version = `"$NewVersion`"" | Set-Content "pyproject.toml"

# Update README.md Citation
Write-Host "Updating README.md Citation..."
# Matches: "Grand'Maison, L.-V. (####). Phytospatial (ANYTHING). Zenodo"
$CitationPattern = "Grand'Maison, L\.-V\. \(\d{4}\)\. Phytospatial \(.*?\)\. Zenodo"
$NewCitation = "Grand'Maison, L.-V. ($Year). Phytospatial ($NewVersion). Zenodo"
(Get-Content "README.md") -replace $CitationPattern, $NewCitation | Set-Content "README.md"

# Update LICENSE Copyright
Write-Host "Updating LICENSE Copyright..."
$LicenseContent = Get-Content "LICENSE"
$LicensePattern = "Copyright \(c\) (\d{4})(?:-\d{4})?"
$StartYear = [regex]::Match($LicenseContent, $LicensePattern).Groups[1].Value

if ($StartYear -and $StartYear -ne $Year) {
    $NewCopyright = "Copyright (c) $StartYear-$Year"
    $LicenseContent -replace $LicensePattern, $NewCopyright | Set-Content "LICENSE"
}

# Update CITATION.cff (Version and Date)
Write-Host "Updating CITATION.cff..."
$CffContent = Get-Content "CITATION.cff"
# Replace version
$CffContent = $CffContent -replace "^version:.*$", "version: $NewVersion"
# Replace date-released
$CffContent = $CffContent -replace "^date-released:.*$", "date-released: $DateReleased"
$CffContent | Set-Content "CITATION.cff"

Write-Host "All files updated successfully." -ForegroundColor Green
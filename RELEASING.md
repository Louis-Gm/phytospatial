# Phytospatial Release Process

This document outlines the steps required to release a new version of phytospatial. The project utilizes a dual MIT and Apache-2.0 license, and several automated scripts handle the synchronization of version numbers and legal notices across the codebase.

## Prerequisites

1.  **Git Credentials**: You must have push access to the main branch and the ability to create tags.
2.  **GitHub CLI (gh)**: Required by the publish script to generate release notes. Your local github CLI must be authentificated prior to release.
3.  **Development Dependencies**: All tools required for testing and building (pytest, build, and twine) are defined in the pyproject.toml dev group. Install them using:
    ```bash
    pip install -e .[dev]
    ```
4.  **Clean State**: Your working directory must be clean and synchronized with the remote main branch.

## Step 1: Quality Assurance and Testing

Before initiating a release, verify the integrity of the package:

* **Local Testing**: Run the full test suite using pytest to ensure image processing algorithms remain functional.
* **Staging Release**: Execute scripts/test_release.ps1 to verify the package builds correctly and can be uploaded to TestPyPI.
    * This script will prompt for a temporary version number (e.g., 0.2.1-rc1).
    * It automatically cleans old build artifacts and reverts changes to pyproject.toml after the test is complete.
    * Please check that the TestPyPI readme loads correctly.

## Step 2: Executing the Production Release

The production release is managed by scripts/publish_trigger.ps1. This script coordinates the entire workflow:

1.  **Launch the Trigger**: Run .\scripts\publish_trigger.ps1.
2.  **Automated Checks**: The script will verify git status, sync with origin, and run pytest one final time.
3.  **Version Input**: When prompted, enter the new version number.
4.  **Automated Updates**: The script calls version_bumper.ps1 to update the following:
    * pyproject.toml: Updates the version string.
    * README.md: Updates the citation year and version.
    * LICENSE-MIT and NOTICE: Updates the copyright year range to 2024-YYYY.
    * src/phytospatial/__init__.py: Updates the internal copyright header.
    * CITATION.cff: Updates version and release date.

## Step 3: Git Tagging and Remote Sync

The publish script stages the modified files (pyproject.toml, README.md, LICENSE-MIT, LICENSE-APACHE, NOTICE, CITATION.cff, and src/phytospatial/__init__.py). It then commits them with a version-specific message and creates an annotated git tag (e.g., v0.2.1). Finally, it pushes both the branch and the tag to GitHub.

## Step 4: GitHub Release and PyPI Deployment

1.  **Draft Release**: The script uses the GitHub CLI to create a release draft and auto-generate release notes based on the commit history.
2.  **Manual Review**: Navigate to the GitHub Releases page to review the draft.
3.  **Publication**: Once the GitHub release is published manually, the Publish to PyPI GitHub Action is triggered.
4.  **Verification**: Monitor the GitHub Actions tab to ensure the build and upload to PyPI complete successfully.
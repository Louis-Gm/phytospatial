# release.sh

set -e  # Fail immediately if any command errors out

# --- CONFIG ---
PROJECT_NAME="phytospatial"
MAIN_BRANCH="main"
# ---------------

echo "STARTING RELEASE PROCESS FOR $PROJECT_NAME"

# SELECT RELEASE MODE
echo "Select Release Mode:"
echo "  [1] Test (Dry Run - Build & Upload to TestPyPI only)"
echo "  [2] Production (Build, Tag, GitHub Release & Upload to PyPI)"
read -p "Enter choice [1-2]: " mode_choice

if [[ "$mode_choice" != "1" && "$mode_choice" != "2" ]]; then
    echo "Error: Invalid choice. Exiting."
    exit 1
fi

# PRE-UPLOAD CHECKS
if [[ -n $(git status -s) ]]; then
    echo "Error: Working directory is dirty. Please commit changes first."
    exit 1
fi

CURRENT_VERSION=$(grep -m1 'version = "' pyproject.toml | cut -d '"' -f 2)
echo "Current Version: $CURRENT_VERSION"

# ASK FOR NEW VERSION
read -p "Enter the new version number (e.g 4.2.0): " NEW_VERSION

if [[ -z "$NEW_VERSION" ]]; then
    echo "Error: No version entered."
    exit 1
fi

echo "Updating version from $CURRENT_VERSION to $NEW_VERSION..."

# UPDATE FILES
# Update pyproject.toml
sed -i "s/version = \"$CURRENT_VERSION\"/version = \"$NEW_VERSION\"/" pyproject.toml

# Update requirements.txt to match current environment (Freeze)
echo "Syncing requirements.txt with current environment..."
pip freeze > requirements.txt

# CLEAN OLD BUILDS
echo "Cleaning old build artifacts..."
rm -rf dist/ build/ *.egg-info

# BUILD PYTHON PACKAGE
echo "Building Source and Wheel..."
python -m build

# --- EXECUTE MODE ---

if [[ "$mode_choice" == "1" ]]; then
    echo "--------------------------------------------------------"
    echo "TEST MODE SELECTED"
    echo "--------------------------------------------------------"
    
    echo "Uploading to TestPyPI..."
    # This requires a separate account on test.pypi.org
    twine upload --repository testpypi dist/*
    
    echo "Test upload complete."
    echo "Note: Local version bump has NOT been committed."
    exit 0
fi

if [[ "$mode_choice" == "2" ]]; then
    echo "--------------------------------------------------------"
    echo "PRODUCTION MODE SELECTED"
    echo "--------------------------------------------------------"
    
    # COMMIT AND TAG
    echo "Committing and Tagging..."
    git add pyproject.toml requirements.txt
    git commit -m "Bump version to $NEW_VERSION"
    git tag -a "v$NEW_VERSION" -m "Release v$NEW_VERSION"

    echo "Pushing to GitHub..."
    git push origin "$MAIN_BRANCH"
    git push origin "v$NEW_VERSION"

    # CREATE GITHUB RELEASE
    echo "Creating GitHub Release entry..."
    gh release create "v$NEW_VERSION" dist/* --generate-notes --title "v$NEW_VERSION"

    # UPLOAD TO PYPI
    echo "Uploading to PRODUCTION PyPI..."
    twine upload dist/*
fi

echo "SUCCESS. Version v$NEW_VERSION processing complete."

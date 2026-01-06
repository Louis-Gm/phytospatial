# release.sh

set -e  # Fail immediately if any command errors out

# --- CONFIGURATION ---
PROJECT_NAME="phytospatial"
MAIN_BRANCH="main"
SPEC_FILE="main.spec"
# ---------------------

echo "   STARTING RELEASE PROCESS FOR $PROJECT_NAME"

# PRE-FLIGHT CHECKS
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

echo "--> Updating version from $CURRENT_VERSION to $NEW_VERSION..."

# UPDATE FILES
# Update pyproject.toml (works on macOS/Linux/Git Bash)
sed -i "s/version = \"$CURRENT_VERSION\"/version = \"$NEW_VERSION\"/" pyproject.toml

# Update requirements.txt to match current environment (Freeze)
echo "--> Syncing requirements.txt with current environment..."
pip freeze > requirements.txt

# CLEAN OLD BUILDS
echo "--> Cleaning old build artifacts..."
rm -rf dist/ build/ *.egg-info

# BUILD PYTHON PACKAGE
echo "--> Building Source and Wheel..."
python -m build

# BUILD EXECUTABLE
if [[ -f "$SPEC_FILE" ]]; then
    echo "--> Building Standalone Executable (PyInstaller)..."
    pyinstaller "$SPEC_FILE" --clean --noconfirm
else
    echo "Warning: $SPEC_FILE not found. Skipping executable build."
fi

# COMMIT AND TAG
echo "--> Committing version bump..."
git add pyproject.toml requirements.txt
git commit -m "Bump version to $NEW_VERSION"

echo "--> Tagging $NEW_VERSION..."
git tag -a "v$NEW_VERSION" -m "Release v$NEW_VERSION"

# PUSH TO GITHUB
echo "--> Pushing to GitHub..."
git push origin "$MAIN_BRANCH"
git push origin "v$NEW_VERSION"

# CREATE GITHUB RELEASE
# Uploads the Wheel, Source Tarball, and Executable to github
echo "--> Creating GitHub Release..."
gh release create "v$NEW_VERSION" \
    dist/*.whl \
    dist/*.tar.gz \
    dist/*.exe \
    --generate-notes \
    --title "v$NEW_VERSION"

# UPLOAD TO PYPI
read -p "Do you want to upload to PyPI now? [y/N] " response
if [[ "$response" =~ ^[yY]$ ]]; then
    echo "--> Uploading to PyPI..."
    twine upload dist/*.whl dist/*.tar.gz
else
    echo "Skipping PyPI upload."
fi

echo "   RELEASE v$NEW_VERSION COMPLETE"

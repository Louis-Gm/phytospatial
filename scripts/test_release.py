# scripts/test_release.py

import sys
import subprocess
import re
import shutil
from pathlib import Path

# ANSI Colors
YELLOW = '\033[93m'
CYAN = '\033[96m'
GREEN = '\033[92m'
FAIL = '\033[91m'
GRAY = '\033[90m'
RESET = '\033[0m'

def main():
    root = Path(__file__).resolve().parent.parent
    pyproject = root / "pyproject.toml"

    print(f"{YELLOW}TEST RELEASE{RESET}")

    # Ask for Temporary Version
    content = pyproject.read_text("utf-8")
    match = re.search(r'version = "(.*)"', content)
    if not match:
        sys.exit(f"{FAIL}Could not find version in pyproject.toml{RESET}")
        
    current_version = match.group(1)
    print(f"Current Version: {current_version}")
    
    # Check if version was passed as an argument
    if len(sys.argv) > 1:
        new_version = sys.argv[1].strip()
        print(f"Using version from command line argument: {new_version}")
    else:
        # Fallback to interactive mode for local use
        new_version = input("Enter temporary test version (format: 4.2.0): ").strip()

    if not new_version:
        sys.exit(f"{FAIL}Version required.{RESET}")

    # Modify pyproject.toml
    new_content = content.replace(f'version = "{current_version}"', f'version = "{new_version}"')
    pyproject.write_text(new_content, encoding="utf-8")

    try:
        # CLEAN BUILD ARTIFACTS
        print(f"{CYAN}CLEANING OLD BUILDS{RESET}")
        if (root / "dist").exists():
            shutil.rmtree(root / "dist")
        if (root / "build").exists():
            shutil.rmtree(root / "build")
        for path in root.rglob("*.egg-info"):
            shutil.rmtree(path)

        # BUILD
        print(f"{CYAN}BUILDING PACKAGE{RESET}")
        subprocess.run([sys.executable, "-m", "build"], cwd=root, check=True)

        # UPLOAD
        print(f"{CYAN}UPLOADING TO TESTPYPI{RESET}")

        # NOTE: In CI, TWINE_USERNAME/PASSWORD env vars must be set
        subprocess.run("twine upload --repository testpypi dist/*", cwd=root, shell=True, check=True)

        print(f"{GREEN}Upload successful. Verification complete.{RESET}")

    except Exception as e:
        print(f"{FAIL}Test release failed: {e}{RESET}")
        sys.exit(1)

    finally:
        # REVERT CHANGES
        print(f"{YELLOW}REVERTING LOCAL CHANGES{RESET}")

        # We use git checkout to ensure clean revert even if write failed
        subprocess.run(["git", "checkout", "pyproject.toml"], cwd=root, check=True)
        print(f"{GRAY}Reverted pyproject.toml to original state.{RESET}")

if __name__ == "__main__":
    main()
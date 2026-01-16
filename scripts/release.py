# scripts/release.py

import sys
import subprocess
import re
import argparse
from pathlib import Path

MAIN_BRANCH = "main"
FILES_TO_STAGE = [
    "pyproject.toml",
    "README.md",
    "CITATION.cff"
]

# colors for Terminal Output
class Colors:
    HEADER = '\033[95m'
    OKBLUE = '\033[96m'
    OKGREEN = '\033[92m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    WARNING = '\033[93m'

def log(message, color=Colors.OKBLUE):
    print(f"{color}{message}{Colors.ENDC}")

def error_exit(message):
    print(f"{Colors.FAIL}Error: {message}{Colors.ENDC}")
    sys.exit(1)

def run_command(command, cwd=None, capture_output=False):
    """
    Runs a shell command. If capture_output is True, returns the stdout string.
    If the command fails, it exits the script immediately.
    """
    try:
        result = subprocess.run(
            command,
            cwd=cwd,
            check=True,
            shell=True,
            text=True,
            capture_output=capture_output
        )
        return result.stdout.strip() if capture_output else None
    except subprocess.CalledProcessError as e:
        error_exit(f"Command failed: {command}\n{e.stderr if capture_output else ''}")

def main():

    parser = argparse.ArgumentParser(description="Trigger a new release.")
    parser.add_argument(
        "--skip-tests", 
        action="store_true", 
        help="Bypass the pytest suite (Use only for docs/metadata updates)"
    )
    args = parser.parse_args()

    script_path = Path(__file__).resolve()
    project_root = script_path.parent.parent
    
    log("PRODUCTION RELEASE TRIGGER", Colors.HEADER)

    # VERIFICATION CHECKS
    log("Checking Git Status...")
    status = run_command("git status --porcelain", cwd=project_root, capture_output=True)
    if status:
        error_exit("Working directory is dirty. Commit changes first.")

    log("Syncing with Remote...")
    run_command("git fetch origin", cwd=project_root)
    
    local_hash = run_command("git rev-parse HEAD", cwd=project_root, capture_output=True)
    remote_hash = run_command(f"git rev-parse origin/{MAIN_BRANCH}", cwd=project_root, capture_output=True)

    if local_hash != remote_hash:
        error_exit("Local branch is not in sync with remote. Pull or Push first.")

    if args.skip_tests:
        log("WARNING: SKIPPING TEST SUITE AS REQUESTED", Colors.WARNING)
    else:
        log("RUNNING TEST SUITE", Colors.OKBLUE)
        run_command(f"{sys.executable} -m pytest", cwd=project_root)
        log("Tests passed.", Colors.OKGREEN)

    # VERSION INPUT
    pyproject_path = project_root / "pyproject.toml"
    if not pyproject_path.exists():
        error_exit("pyproject.toml not found.")

    content = pyproject_path.read_text(encoding="utf-8")
    match = re.search(r'version = "(.*)"', content)
    if not match:
        error_exit("Could not find current version in pyproject.toml")
    
    current_version = match.group(1)
    log(f"Current Version: {current_version}")
    
    new_version = input(f"{Colors.HEADER}Enter NEW RELEASE version: {Colors.ENDC}").strip()
    if not new_version:
        error_exit("Version required.")

    # CALL FILE UPDATE SCRIPT
    update_script = script_path.parent / "update_docs.py"
    if not update_script.exists():
        error_exit(f"Could not find update_docs.py at {update_script}")

    log(f"Running update_docs.py...")
    run_command(
        f"{sys.executable} {update_script} {new_version} {current_version}", 
        cwd=project_root
    )

    # GIT OPERATIONS
    log("Committing and Tagging...")
    
    # Stage files
    files_str = " ".join(FILES_TO_STAGE)
    run_command(f"git add {files_str}", cwd=project_root)
    
    # Commit
    run_command(f'git commit -m "Bump version to v{new_version}"', cwd=project_root)
    
    # Tag
    run_command(f'git tag -a "v{new_version}" -m "Release v{new_version}"', cwd=project_root)

    log("Pushing to GitHub...")
    run_command(f'git push origin "{MAIN_BRANCH}"', cwd=project_root)
    run_command(f'git push origin "v{new_version}"', cwd=project_root)

    # GITHUB RELEASE
    # NOTE: requires github CLI properly authenticated
    log("Creating GitHub Release Draft...")

    # Generate release notes and create release
    # NOTE: generate notes requires proper formatting of PRs and commits (for instance "fix", "feat" or "docs" keywords)
    run_command(
        f'gh release create "v{new_version}" --generate-notes --title "Phytospatial v{new_version}"',
        cwd=project_root
    )

    log(f"SUCCESS! Tag v{new_version} pushed.", Colors.OKGREEN)
    log("Monitor the upload progress here: https://github.com/Louis-Gm/phytospatial/actions", Colors.ENDC)

if __name__ == "__main__":
    main()
# scripts/update_docs.py
import argparse
import re
from datetime import datetime
from pathlib import Path

def update_content(content: str, pattern: str, replacement: str, flags=0) -> str:
    """
    Helper function to perform regex replacement and log if changes occurred.
    """
    new_content = re.sub(pattern, replacement, content, flags=flags)
    return new_content

def main():
    parser = argparse.ArgumentParser(description="Bump version numbers and dates across the project.")
    parser.add_argument("new_version", help="The new release version (e.g., 0.2.2)")
    parser.add_argument("current_version", help="The current version found in pyproject.toml")
    
    args = parser.parse_args()
    
    new_ver = args.new_version
    curr_ver = args.current_version
    year = str(datetime.now().year)
    date_released = datetime.now().strftime("%Y-%m-%d")

    # Resolve project root relative to this script
    script_path = Path(__file__).resolve()
    project_root = script_path.parent.parent

    print(f"--- STARTING FILE UPDATES IN: {project_root} ---")

    # pyproject.toml (Version)
    file_path = project_root / "pyproject.toml"
    print(f"Updating {file_path.name}...")
    
    if file_path.exists():
        content = file_path.read_text(encoding="utf-8")
        pattern = fr'version = "{re.escape(curr_ver)}"'
        replacement = f'version = "{new_ver}"'
        
        new_content = update_content(content, pattern, replacement)
        if content != new_content:
            file_path.write_text(new_content, encoding="utf-8")
        else:
            print(f"  [!] Warning: Could not find version string matching {curr_ver}")
    else:
        print(f"  [!] Error: {file_path.name} not found.")

    # README.md (Citation)
    file_path = project_root / "README.md"
    print(f"Updating {file_path.name} Citation...")
    
    if file_path.exists():
        content = file_path.read_text(encoding="utf-8")
        pattern = r"Grand'Maison, L\.-V\. \(\d{4}\)\. Phytospatial: a python package dedicated to processing lidar and imagery data in forestry \(.*?\)\ \[software\]\. Zenodo"
        replacement = f"Grand'Maison, L.-V. ({year}). Phytospatial: a python package dedicated to processing lidar and imagery data in forestry ({new_ver}) [software]. Zenodo"
        
        file_path.write_text(update_content(content, pattern, replacement, flags=re.IGNORECASE), encoding="utf-8")

    # CITATION.cff (Release date and version)
    file_path = project_root / "CITATION.cff"
    print(f"Updating {file_path.name}...")

    if file_path.exists():
        content = file_path.read_text(encoding="utf-8")
        
        # Update Version (start of line)
        content = re.sub(r"^version:.*$", f"version: {new_ver}", content, flags=re.MULTILINE)
        
        # Update Date Released (start of line)
        content = re.sub(r"^date-released:.*$", f"date-released: {date_released}", content, flags=re.MULTILINE)
        
        file_path.write_text(content, encoding="utf-8")

    print("\nAll files updated successfully.")

if __name__ == "__main__":
    main()
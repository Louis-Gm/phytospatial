#!/bin/bash

: <<'DOC'
Synchronizes Python modules with MkDocs documentation files and updates the navigation.
Generates markdown files with mkdocstrings directives and injects the updated
navigation structure into the mkdocs.yml file.
DOC

SRC_ROOT="src"
DOCS_DIR="docs/reference"
MKDOCS_FILE="mkdocs.yml"

echo "Starting Documentation Sync..."

find "$SRC_ROOT/phytospatial" -name "*.py" | while read -r py_file; do    
    rel_path="${py_file#$SRC_ROOT/}"
    import_path="${rel_path%.py}"
    import_path="${import_path//\//.}"
    dir_name=$(dirname "$rel_path")
    module_name=$(basename "$rel_path" .py)
    
    if [ "$module_name" == "__init__" ]; then continue; fi

    sub_dirs="${dir_name#phytospatial}"
    target_dir="$DOCS_DIR$sub_dirs"
    mkdir -p "$target_dir"
    target_md="$target_dir/$module_name.md"

    cat <<EOF > "$target_md"
# $module_name

::: $import_path
    options:
      show_root_heading: false
      show_source: true
EOF
done

TMP_YAML="temp_nav.yml"
echo "" > "$TMP_YAML"

last_dir=""

(
    find "$SRC_ROOT/phytospatial" -mindepth 2 -name "*.py" | sort
    find "$SRC_ROOT/phytospatial" -maxdepth 1 -name "*.py" | sort
) | while read -r py_file; do
    
    rel_path="${py_file#$SRC_ROOT/}"
    module_name=$(basename "$rel_path" .py)
    
    if [ "$module_name" == "__init__" ]; then continue; fi

    dir_name=$(dirname "$rel_path")
    clean_dir=$(basename "$dir_name" | sed -r 's/_/ /g' | awk '{for(i=1;i<=NF;i++)sub(/./,toupper(substr($i,1,1)),$i)}1')
    clean_mod=$(echo "$module_name" | sed -r 's/_/ /g' | awk '{for(i=1;i<=NF;i++)sub(/./,toupper(substr($i,1,1)),$i)}1')
    sub_dirs="${rel_path#phytospatial/}"
    md_rel_path="reference/${sub_dirs%.py}.md"

    if [ "$clean_dir" == "Phytospatial" ]; then
        echo "      - \"$clean_mod\": $md_rel_path" >> "$TMP_YAML"
    else
        if [ "$clean_dir" != "$last_dir" ]; then
            echo "      - $clean_dir:" >> "$TMP_YAML"
            last_dir="$clean_dir"
        fi
        echo "          - \"$clean_mod\": $md_rel_path" >> "$TMP_YAML"
    fi
done

sed -i -e "/# REF_START/,/# REF_END/ {
    /# REF_START/ n
    /# REF_END/ !d
    /# REF_END/ i\\
  - API Reference:
    r $TMP_YAML
}" "$MKDOCS_FILE"

rm "$TMP_YAML"
echo "Sync complete."
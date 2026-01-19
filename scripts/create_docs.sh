#!/bin/bash
# scripts/create_docs.sh

SRC_ROOT="src"
DOCS_DIR="docs/reference"
MKDOCS_FILE="mkdocs.yml"

echo "Starting Enhanced Documentation Sync..."

find "$SRC_ROOT/phytospatial" -name "*.py" | while read py_file; do    
    rel_path="${py_file#$SRC_ROOT/}"              # phytospatial/raster/example.py
    import_path="${rel_path%.py}"                 # phytospatial/raster/example
    import_path="${import_path//\//.}"            # phytospatial.raster.example
    dir_name=$(dirname "$rel_path")               # phytospatial/raster
    module_name=$(basename "$rel_path" .py)       # example
    
    # skip init files
    if [ "$module_name" == "__init__" ]; then continue; fi

    sub_dirs="${dir_name#phytospatial}"
    target_dir="$DOCS_DIR$sub_dirs"
    mkdir -p "$target_dir"
    target_md="$target_dir/$module_name.md"

    cat <<EOF > "$target_md"
::: $import_path
    options:
      show_root_heading: true
      show_source: true
EOF

    echo "Generated: $target_md"
done

TMP_YAML="temp_nav.yml"
echo "  - API Reference:" > "$TMP_YAML"

last_dir=""

find "$SRC_ROOT/phytospatial" -name "*.py" | sort | while read py_file; do
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
        last_dir="Phytospatial"
    else
        if [ "$clean_dir" != "$last_dir" ]; then
            echo "      - $clean_dir:" >> "$TMP_YAML"
            last_dir="$clean_dir"
        fi
        echo "          - \"$clean_mod\": $md_rel_path" >> "$TMP_YAML"
    fi
done

# mkdocs injection
sed -i -e "/# REF_START/,/# REF_END/{ 
    /# REF_START/!{ 
        /# REF_END/!d 
    } 
    /# REF_START/r $TMP_YAML
}" "$MKDOCS_FILE"

rm "$TMP_YAML"
echo "Sync complete."
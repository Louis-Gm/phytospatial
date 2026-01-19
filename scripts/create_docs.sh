#!/bin/bash
# scripts/create_docs.sh

SRC_ROOT="src"
DOCS_DIR="docs/reference"
MKDOCS_FILE="mkdocs.yml"

echo "Starting Enhanced Documentation Sync..."

# generate markdown files for each module in src/phytospatial
find "$SRC_ROOT/phytospatial" -name "*.py" | while read py_file; do    
    rel_path="${py_file#$SRC_ROOT/}"              # phytospatial/raster/example_module.py
    import_path="${rel_path%.py}"                 # phytospatial/raster/example_module
    import_path="${import_path//\//.}"            # phytospatial.raster.example_module
    dir_name=$(dirname "$rel_path")               # phytospatial/raster
    module_name=$(basename "$rel_path" .py)       # example_module
    
    # skip init files
    if [ "$module_name" == "__init__" ]; then continue; fi

    # generate title
    clean_dir=$(basename "$dir_name" | sed -r 's/_/ /g' | awk '{for(i=1;i<=NF;i++)sub(/./,toupper(substr($i,1,1)),$i)}1')
    clean_mod=$(echo "$module_name" | sed -r 's/_/ /g' | awk '{for(i=1;i<=NF;i++)sub(/./,toupper(substr($i,1,1)),$i)}1')
    
    if [ "$clean_dir" == "Phytospatial" ]; then
        full_title="$clean_mod"
    else
        full_title="$clean_dir $clean_mod"
    fi

    # extract module description from docstring (first line only)
    # """
    # This works.                          (NumPy style docstring)
    # """
    #
    # """This works too."""             (PEP 257 style docstring)

    description=$(awk '
        /^"""/ { 
            gsub(/"""/, "");              # Remove quotes
            if ($0 ~ /[^[:space:]]/) {    # If text exists on same line
                sub(/^[[:space:]]+/, ""); # Trim leading whitespace
                print $0; 
                exit; 
            }
            flag=1;                       # Else, wait for next line
            next 
        } 
        flag { 
            sub(/^[[:space:]]+/, "");     # Trim leading whitespace
            print $0; 
            exit 
        }' "$py_file")
    
    if [ -z "$description" ]; then
        description="Documentation for the $clean_mod module."
    fi

    sub_dirs="${dir_name#phytospatial}"
    target_dir="$DOCS_DIR$sub_dirs"
    mkdir -p "$target_dir"
    target_md="$target_dir/$module_name.md"
    cat <<EOF > "$target_md"
# $full_title

$description

::: $import_path
    options:
      show_root_heading: true
      show_source: true
EOF

    echo "Generated: $target_md"
done

TMP_YAML="temp_nav.yml"
echo "  - API Reference:" > "$TMP_YAML"

find "$SRC_ROOT/phytospatial" -name "*.py" | sort | while read py_file; do
    rel_path="${py_file#$SRC_ROOT/}"
    module_name=$(basename "$rel_path" .py)
    
    if [ "$module_name" == "__init__" ]; then continue; fi

    dir_name=$(dirname "$rel_path")
    clean_dir=$(basename "$dir_name" | sed -r 's/_/ /g' | awk '{for(i=1;i<=NF;i++)sub(/./,toupper(substr($i,1,1)),$i)}1')
    clean_mod=$(echo "$module_name" | sed -r 's/_/ /g' | awk '{for(i=1;i<=NF;i++)sub(/./,toupper(substr($i,1,1)),$i)}1')
    
    if [ "$clean_dir" == "Phytospatial" ]; then
        title="$clean_mod"
    else
        title="$clean_dir: $clean_mod"
    fi

    sub_dirs="${rel_path#phytospatial/}"
    md_rel_path="reference/${sub_dirs%.py}.md"

    echo "      - \"$title\": $md_rel_path" >> "$TMP_YAML"
done

# mkdocs injection using comment markers
sed -i -e "/# REF_START/,/# REF_END/{ 
    /# REF_START/!{ 
        /# REF_END/!d 
    } 
    /# REF_START/r $TMP_YAML
}" "$MKDOCS_FILE"

rm "$TMP_YAML"
echo "Sync complete."
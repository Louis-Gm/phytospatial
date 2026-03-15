from pathlib import Path
import mkdocs_gen_files

def generate_reference_pages(src_dir: str, pkg_name: str) -> None:
    """
    Traverses the source directory to generate grouped virtual markdown pages and navigation.

    Args:
        src_dir: The relative path to the root of the source code repository.
        pkg_name: The name of the top-level Python package to document.
    """
    nav = mkdocs_gen_files.Nav()
    src_path = Path(src_dir)
    pkg_path = src_path / pkg_name

    subpackages = []
    independent_modules = []

    for path in sorted(pkg_path.rglob("*.py")):
        if path.name == "__init__.py":
            continue

        module_path = path.relative_to(src_path).with_suffix("")
        doc_path = path.relative_to(src_path).with_suffix(".md")
        
        rel_to_pkg = doc_path.relative_to(pkg_name)
        full_doc_path = Path("reference", rel_to_pkg)

        parts = tuple(module_path.parts)
        clean_parts = tuple(part.replace("_", " ").title() for part in parts[1:])

        if len(clean_parts) > 1:
            nav_tuple = ("Subpackages",) + clean_parts
            subpackages.append((nav_tuple, rel_to_pkg.as_posix(), full_doc_path, path, parts, clean_parts))
        else:
            nav_tuple = ("Independent modules",) + clean_parts
            independent_modules.append((nav_tuple, rel_to_pkg.as_posix(), full_doc_path, path, parts, clean_parts))

    for item in subpackages + independent_modules:
        nav_tuple, rel_to_pkg_posix, full_doc_path, path, parts, clean_parts = item
        nav[nav_tuple] = rel_to_pkg_posix

        with mkdocs_gen_files.open(full_doc_path, "w") as fd:
            ident = ".".join(parts)
            fd.write(f"# {clean_parts[-1]}\n\n")
            fd.write(f"::: {ident}\n")
            fd.write("    options:\n")
            fd.write("      show_root_heading: false\n")
            fd.write("      show_source: true\n")

        mkdocs_gen_files.set_edit_path(full_doc_path, path)

    with mkdocs_gen_files.open("reference/SUMMARY.md", "w") as nav_file:
        nav_file.writelines(nav.build_literate_nav())

generate_reference_pages("src", "phytospatial")
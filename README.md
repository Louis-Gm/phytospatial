<br />
<div align="center">
  <a href="https://github.com/Louis-Gm/phytospatial">
    <img src="https://raw.githubusercontent.com/Louis-Gm/phytospatial/main/assets/phytospatial-logo.png" alt="Logo" width="420" height="420">
  </a>
  <h1 align="center"><b>Phytospatial</b></h1>
  <div align="center">
    A python package that processes lidar and imagery data in forestry
  </div>

  [start]: #

  <p align="center">
    <a href="https://phytospatial.readthedocs.io/"><strong>Explore the docs »</strong></a>
  </p>
 
  [end]: #

  <br /><div align="center">
    <a href="https://github.com/Louis-Gm/phytospatial/issues">Report Bug</a>
    ·
    <a href="https://github.com/Louis-Gm/phytospatial/issues">Request Feature</a>
  </div><br /> 

  <div align="center">
    <img src="https://img.shields.io/badge/python-3.10+-orange.svg" alt="Python versions">    
    <img src="https://img.shields.io/badge/Apache%202.0-blue.svg" alt="License">
    <img src="https://img.shields.io/badge/DOI-10.5281%2Fzenodo.18112045-purple" alt="DOI">
    <img src="https://github.com/Louis-Gm/phytospatial/actions/workflows/test_suite.yml/badge.svg" alt="Build Status">    
    <br />
    <img src="https://img.shields.io/badge/Windows-blue.svg?style=flat&logo=data:image/svg%2bxml;base64,PD94bWwgdmVyc2lvbj0iMS4wIiBlbmNvZGluZz0iVVRGLTgiPz4KPHN2ZyB2ZXJzaW9uPSIxLjEiIHhtbG5zPSJodHRwOi8vd3d3LnczLm9yZy8yMDAwL3N2ZyIgd2lkdGg9IjE0IiBoZWlnaHQ9IjE0Ij4KPHBhdGggZD0iTTAgMCBDMCA0LjYyIDAgOS4yNCAwIDE0IEMtNi45MyAxMy41MDUgLTYuOTMgMTMuNTA1IC0xNCAxMyBDLTE0IDkuMDQgLTE0IDUuMDggLTE0IDEgQy05LjE3MDYyNTQgMC4yMTE1MzA2OCAtNC45Njc2Mjk5MyAwIDAgMCBaICIgZmlsbD0iIzREQUU0RiIgdHJhbnNmb3JtPSJ0cmFuc2xhdGUoMTQsMCkiLz4KPHBhdGggZD0iTTAgMCBDMi42NCAwIDUuMjggMCA4IDAgQzggMi4zMSA4IDQuNjIgOCA3IEM1LjY2NzA1MjI1IDcuMDQyNDE3MjMgMy4zMzI5NzQzMyA3LjA0MDkyOTM3IDEgNyBDMCA2IDAgNiAtMC4wNjI1IDIuOTM3NSBDLTAuMDQxODc1IDEuOTY4MTI1IC0wLjAyMTI1IDAuOTk4NzUgMCAwIFogIiBmaWxsPSIjRkNDMDA4IiB0cmFuc2Zvcm09InRyYW5zbGF0ZSg2LDcpIi8+CjxwYXRoIGQ9Ik0wIDAgQzEuOTggMCAzLjk2IDAgNiAwIEM2IDEuOTggNiAzLjk2IDYgNiBDNC4wMiA2IDIuMDQgNiAwIDYgQzAgNC4wMiAwIDIuMDQgMCAwIFogIiBmaWxsPSIjMjE5NUYyIiB0cmFuc2Zvcm09InRyYW5zbGF0ZSgwLDcpIi8+CjxwYXRoIGQ9Ik0wIDAgQzEuOTggMCAzLjk2IDAgNiAwIEM2IDEuOTggNiAzLjk2IDYgNiBDNC4wMiA2IDIuMDQgNiAwIDYgQzAgNC4wMiAwIDIuMDQgMCAwIFogIiBmaWxsPSIjRjM0MjM2IiB0cmFuc2Zvcm09InRyYW5zbGF0ZSgwLDEpIi8+Cjwvc3ZnPgo=" alt="Windows">
    <img src="https://img.shields.io/badge/macOS-000000?style=flat&logo=apple&logoColor=white" alt="MacOS">
    <img src="https://img.shields.io/badge/Linux-FCC624?style=flat&logo=linux&logoColor=black" alt="Linux">
  </div>
</div>

## **About The Project**

**Phytospatial** is a Python toolkit designed to streamline the processing of remote sensing data for forestry and vegetation analysis. It provides tools for handling large hyperspectral rasters, validating vector geometries, and extracting spectral statistics from tree crowns. It also allows for passive-active raster-level fusion via its image processing module.

### **Key Features**

* **Memory-Safe Processing:** Process massive rasters using windowed reading (via `rasterio`) without overloading RAM.
* **Forestry Focused:** Specialized tools for tree crown validation and species labeling.

## **Getting Started**

### **Installation**

To get up and running quickly with `pip`:

```sh
pip install phytospatial
```

> **New to Python?** Check out our detailed [Installation Guide](https://phytospatial.readthedocs.io/en/latest/installation/) for Conda and Virtual Environment setup.

## **Usage**

Here is a simple example of extracting spectral data from tree crowns using the *extract_to_dataframe* API, which automatically handles memory management and tiling strategies.

```python
from phytospatial import extract, loaders

# Load tree crowns (returns a standardized Vector object)
crowns = loaders.load_crowns("data/crowns.shp")

# Extract features directly into a pandas DataFrame
# The 'auto' mode automatically selects the best processing strategy
df = extract.extract_to_dataframe(
    raster_input="data/image.tif",
    vector_input=crowns,
    tile_mode="auto"
)

print(df.head())
```

For a complete workflow, see the [Spectral Extraction Tutorial](https://phytospatial.readthedocs.io/en/latest/examples/extraction_pipeline/).

## **Contribute**

As an open-source project, we encourage and welcome contributions of students, researchers, or professional developers.

**Want to help?** Please read our [CONTRIBUTING](https://phytospatial.readthedocs.io/en/latest/contributing/contributing/) section for a detailed explanation of how to submit pull requests. Please also make sure to read the project's [CODE OF CONDUCT](https://phytospatial.readthedocs.io/en/latest/contributing/code_of_conduct/).

Not sure how to implement your idea, but want to contribute?
<br />
Feel free to leave a feature request <a href="https://github.com/Louis-Gm/phytospatial/issues">here</a>.

## **Citation**

If you use this project in your research, please cite it as:

Grand'Maison, L.-V. (2026). Phytospatial: a python package that processes lidar and imagery data in forestry (0.5.0) [software]. Zenodo. https://doi.org/10.5281/zenodo.18112045

## **Contact**

The project is currently being maintained by **Louis-Vincent Grand'Maison**.

Feel free to contact me by email or linkedin:
<br />
Email - [lvgra@ulaval.ca](mailto:lvgra@ulaval.ca)
<br />
Linkedin - [grandmaison-lv](https://www.linkedin.com/in/grandmaison-lv/)

## **Acknowledgments & Funding**

This software is developed by Louis-Vincent Grand'Maison as part of a PhD project. The maintenance and development of this project is supported by several research scholarships:

* Fonds de recherche du Québec – Nature et technologies (FRQNT) (Scholarship 2024-2025)
* Natural Sciences and Engineering Research Council of Canada (NSERC) (Scholarship 2025-present)
* Université Laval (Scholarship 2024-present)

## **License**

`Phytospatial` is distributed under the Apache License, Version 2.0.
<br />
See the LICENSE file for the full text. This license includes a permanent, world-wide, non-exclusive, no-charge, royalty-free, irrevocable patent license for all users.

See [LICENSE](https://phytospatial.readthedocs.io/en/latest/license/) for more information on licensing and copyright.

[start]: #

([Back to Top](#table-of-contents))

[end]: #

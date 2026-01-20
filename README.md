<br />
<div align="center">
  <a href="https://github.com/Louis-Gm/phytospatial">
    <img src="https://raw.githubusercontent.com/Louis-Gm/phytospatial/main/assets/phytospatial-logo.png" alt="Logo" width="420" height="420">
  </a>
  <h1 align="center"><b>phytospatial</b></h1>
  <p align="center">
    A python package that processes lidar and imagery data in forestry
  </p>

  [start]: #

  <p align="center">
    <a href="https://phytospatial.readthedocs.io/"><strong>Explore the docs »</strong></a>
  </p>
 
  [end]: #

  <p>
    <a href="https://github.com/Louis-Gm/phytospatial/issues">Report Bug</a>
    ·
    <a href="https://github.com/Louis-Gm/phytospatial/issues">Request Feature</a>
  </p>
  <p align="center">
    <img src="https://img.shields.io/badge/python-3.10+-orange.svg" alt="Python versions">    
    <img src="https://img.shields.io/badge/Apache%202.0-blue.svg" alt="License">
    <img src="https://img.shields.io/badge/DOI-10.5281%2Fzenodo.18112045-purple" alt="DOI">
    <img src="https://github.com/Louis-Gm/phytospatial/actions/workflows/test_suite.yml/badge.svg" alt="Build Status">    
    <br />
    <img src="https://img.shields.io/badge/Windows-0078D6?style=flat&logo=windows&logoColor=white" alt="Windows">
    <img src="https://img.shields.io/badge/macOS-000000?style=flat&logo=apple&logoColor=white" alt="MacOS">
    <img src="https://img.shields.io/badge/Linux-FCC624?style=flat&logo=linux&logoColor=black" alt="Linux">
  </p>
</div>

## About The Project

**Phytospatial** is a Python toolkit designed to streamline the processing of remote sensing data for forestry and vegetation analysis. It provides tools for handling large hyperspectral rasters, validating vector geometries, and extracting spectral statistics from tree crowns. It also allows for passive-active raster-level fusion via its image processing module.

### Key Features

* **Memory-Safe Processing:** Process massive rasters using windowed reading (via `rasterio`) without overloading RAM.
* **Forestry Focused:** Specialized tools for tree crown validation and species labeling.
* **Dual-Licensed:** Available under both MIT and Apache 2.0 licenses for maximum flexibility.

## Getting Started

### Installation

To get up and running quickly with `pip`:

```sh
git clone https://github.com/Louis-Gm/phytospatial.git
cd phytospatial
pip install -e .
```

> **New to Python?** Check out our detailed [Installation Guide](https://phytospatial.readthedocs.io/en/latest/installation/) for Conda and Virtual Environment setup.

## Usage

Here is a simple example of extracting spectral data from tree crowns:

```python
from phytospatial import extract, loaders

# Load tree crowns
crowns = loaders.load_crowns("data/crowns.shp")

# Initialize extractor
extractor = extract.BlockExtractor("data/image.tif")

# Process
results = []
for stats in extractor.process_crowns(crowns):
    results.append(stats)
```

For a complete workflow, see the [Introduction Pipeline Tutorial](https://phytospatial.readthedocs.io/en/latest/examples/intro_pipeline/).

## Contribute

As an open-source project, we encourage and welcome contributions of students, researchers, or professional developers.

**Want to help?** Please read our [CONTRIBUTING](https://phytospatial.readthedocs.io/en/latest/contributing/contributing/) section for a detailed explanation of how to submit pull requests. Please also make sure to read the project's [CODE OF CONDUCT](https://phytospatial.readthedocs.io/en/latest/contributing/code_of_conduct/).

Not sure how to implement your idea, but want to contribute?
<br />
Feel free to leave a feature request <a href="https://github.com/Louis-Gm/phytospatial/issues">here</a>.

## Citation

If you use this project in your research, please cite it as:

Grand'Maison, L.-V. (2026). Phytospatial: a python package that processes lidar and imagery data in forestry (0.4.0) [software]. Zenodo. https://doi.org/10.5281/zenodo.18112045

## Contact

The project is currently being maintained by **Louis-Vincent Grand'Maison**.

Feel free to contact me by email or linkedin:
<br />
Email - [lvgra@ulaval.ca](mailto:lvgra@ulaval.ca)
<br />
Linkedin - [grandmaison-lv](https://www.linkedin.com/in/grandmaison-lv/)

## Acknowledgments & Funding

This software is developed by Louis-Vincent Grand'Maison as part of a PhD project. The maintenance and development of this project is supported by several research scholarships:

* Fonds de recherche du Québec – Nature et technologies (FRQNT) (Scholarship 2024-2025)
* Natural Sciences and Engineering Research Council of Canada (NSERC) (Scholarship 2025-present)
* Université Laval (Scholarship 2024-present)

## License

`phytospatial` is distributed under the Apache License, Version 2.0.
<br />
See the LICENSE file for the full text. This license includes a permanent, world-wide, non-exclusive, no-charge, royalty-free, irrevocable patent license for all users.

See [LICENSE](https://phytospatial.readthedocs.io/en/latest/license/) for more information on licensing and copyright.

[start]: #

([Back to Top](#table-of-contents))

[end]: #

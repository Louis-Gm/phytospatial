<br />
<div align="center">
  <a href="https://github.com/Louis-Gm/phytospatial">
    <img src="https://raw.githubusercontent.com/Louis-Gm/phytospatial/main/assets/phytospatial.png" alt="Logo" width="420" height="420">
  </a>

  <h3 align="center">phytospatial</h3>

  <p align="center">
    A python package to process remote sensing data in forestry applications
    <br />
    <a href="https://phytospatial.readthedocs.io/"><strong>Explore the docs »</strong></a>
    <br />
    <br />
    <a href="https://github.com/Louis-Gm/phytospatial/issues">Report Bug</a>
    ·
    <a href="https://github.com/Louis-Gm/phytospatial/issues">Request Feature</a>
  </p>
  
  <p align="center">
    <img src="https://github.com/Louis-Gm/phytospatial/actions/workflows/test_suite.yml/badge.svg" alt="Build Status">
    <img src="https://img.shields.io/badge/python-3.10-orange.svg" alt="Python 3.10">    
    <img src="https://img.shields.io/badge/License-MIT%20or%20Apache%202.0-blue.svg" alt="License">
    <img src="https://img.shields.io/badge/DOI-10.5281%2Fzenodo.18112045-purple" alt="DOI">
  </p>
</div>

## Table of Contents
| **Getting Started** | **Documentation** | **Community** |
|:--:|:--:|:--:|
| [About the Project](#about-the-project) | [Project Organization](CONTRIBUTING.md#project-structure) | [Contribute](#contribute) |
| [Installation](#getting-started) | [Citation](#citation) | [Contact](#contact) |
| [Usage](#usage) | [License](#license) | [Acknowledgments](#acknowledgments--funding) |

## About The Project

**Phytospatial** is a Python toolkit designed to streamline the processing of remote sensing data for forestry and vegetation analysis. It provides tools for handling large hyperspectral rasters, validating vector geometries, and extracting spectral statistics from tree crowns. It also allows for passive-active raster-level fusion via its image processing module.

### Key Features

* **Memory-Safe Processing:** Process massive rasters using windowed reading (via `rasterio`) without overloading RAM.
* **Forestry Focused:** Specialized tools for tree crown validation and species labeling.
* **Dual-Licensed:** Available under both MIT and Apache 2.0 licenses for maximum flexibility.

([Back to Top](#table-of-contents))

## Getting Started

### Installation

To get up and running quickly with `pip`:

```sh
git clone https://github.com/Louis-Gm/phytospatial.git
cd phytospatial
pip install -e .
```

> **New to Python?** Check out our detailed [Installation Guide](docs/installation.md) for Conda and Virtual Environment setup.

([Back to Top](#table-of-contents))

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

For a complete workflow, see the [Introduction Pipeline Tutorial](examples/intro_pipeline.ipynb).

([Back to Top](#table-of-contents))

## Contribute

As an open-source project, we encourage and welcome contributions of students, researchers, or professional developers.

**Want to help?** Please read our [CONTRIBUTING](CONTRIBUTING.md) section for a detailed explanation of how to submit pull requests. Please make sure to read the [CODE OF CONDUCT](CODE_OF_CONDUCT.md) section before making contributions.

Not sure how to implement your idea, but want to contribute?
<br />
Feel free to leave a feature request <a href="https://github.com/Louis-Gm/phytospatial/issues">here</a>.

([Back to Top](#table-of-contents))

## Citation

If you use this project in your research, please cite it as:

Grand'Maison, L.-V. (2026). Phytospatial (0.2.1-alpha). Zenodo. https://doi.org/10.5281/zenodo.18112045

([Back to Top](#table-of-contents))

## Contact

The project is currently being maintained by **Louis-Vincent Grand'Maison**.

Feel free to contact me by email or linkedin:
<br />
Email - [lvgra@ulaval.ca](mailto:lvgra@ulaval.ca)
<br />
Linkedin - [grandmaison-lv](https://www.linkedin.com/in/grandmaison-lv/)

([Back to Top](#table-of-contents))

## Acknowledgments & Funding

This software is developed by Louis-Vincent Grand'Maison as part of a PhD project. The maintenance and development of this project is supported by several research scholarships:

* Fonds de recherche du Québec – Nature et technologies (FRQNT) (Scholarship 2024-2025)
* Natural Sciences and Engineering Research Council of Canada (NSERC) (Scholarship 2025-present)
* Université Laval (Scholarship 2024-present)

([Back to Top](#table-of-contents))

## License

`phytospatial` is distributed under the Apache License, Version 2.0 or the MIT License, at your option.

Unless you explicitly state otherwise, any contribution you intentionally submit for inclusion in this repository (as defined by Apache-2.0) shall be dual-licensed as above, without any additional terms or conditions.

See [LICENSE-MIT](LICENSE-MIT), [LICENSE-APACHE](LICENSE-APACHE) and [NOTICE](NOTICE) for more information on licensing and copyright.

([Back to Top](#table-of-contents))
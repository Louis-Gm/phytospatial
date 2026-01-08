<!-- HEADER AND LOGO -->
<br />
<div align="center">
  <a href="https://github.com/Louis-Gm/phytospatial">
    <img src="https://raw.githubusercontent.com/Louis-Gm/phytospatial/main/assets/phytospatial.png" alt="Logo" width="420" height="420">
  </a>

  <h3 align="center">phytospatial</h3>

  <p align="center">
    A python package to process remote sensing data in forestry applications
    <br />
    <a href="https://github.com/Louis-Gm/phytospatial/issues">Report Bug</a>
    ·
    <a href="https://github.com/Louis-Gm/phytospatial/issues">Request Feature</a>
  </p>
  
  <p align="center">
    <img src="https://img.shields.io/badge/python-3.10-orange.svg" alt="Python 3.10">    
    <img src="https://img.shields.io/badge/License-MIT%20or%20Apache%202.0-blue.svg" alt="MIT License">
    <img src="https://img.shields.io/badge/DOI-10.5281%2Fzenodo.18112045-purple" alt="DOI">
  </p>
</div>

<!-- TABLE OF CONTENTS -->
## Table of Contents
| **Getting Started** | **Documentation** | **Community** |
|:--:|:--:|:--:|
| [About the Project](#about-the-project) | [Project Organization](#project-organization) | [Contribute](#contribute) |
| [Installation](#getting-started) | [Citation](#citation) | [Contact](#contact) |
| [Usage](#usage) | [License](#license) | [Acknowledgments](#acknowledgments--funding) |

<!-- ABOUT -->
## About The Project

**Phytospatial** is a Python toolkit designed to streamline the processing of remote sensing data for forestry and vegetation analysis. It provides tools for handling large hyperspectral rasters, validating vector geometries, and extracting spectral statistics from tree crowns. It also allows for passive-active raster-level fusion via its image processing module.

### Key Features

* **Memory-Safe Processing:** Process massive rasters using windowed reading (via `rasterio`) without overloading RAM.
* **Forestry Focused:** Specialized tools for tree crown validation and species labeling.
* **Dual-Licensed:** Available under both MIT and Apache 2.0 licenses for maximum flexibility.

([Back to Top](#table-of-contents))

<!-- GETTING STARTED -->
## Getting Started

To get a local copy up and running follow these simple example steps.

### Installation

1. First, clone the repository to your local machine:
   ```sh
   git clone https://github.com/Louis-Gm/phytospatial.git
   ```
2. Enter the project directory:
   ```sh
   cd phytospatial
   ```
3. Enjoy!

### Environment

It is highly recommended to use a virtual environment. Choose the method that fits your workflow.

_Using pip or conda, setting up the environment is simple_

**Using conda (recommended):**
We provide a configured `environment.yml` that handles Python versioning and automatically installs the package in editable mode.

1. Create the environment from the file:
   ```sh
   conda env create -f environment.yml
   ```
2. Activate the new environment:
   ```sh
   conda activate phytospatial-env
   ```

**Using standard pip (venv):**
If you prefer standard Python tools:

1. Ensure Python 3.10+ is installed
2. Create a virtual environment

   **On windows:**
      ```sh
      python -m venv venv
      ```

   **on Linux/mac:**
      ```sh
      python3 -m venv venv
      ```


3. Install the package in editable mode
   ```sh
   pip install -e .[analysis]
   ```

### Verification
To ensure everything is dandy, run:
   ```sh
   python -c "import phytospatial; print('Phytospatial installed successfully!')"
   ```

You are now ready to run the package, Celebrate! 🥂¨

([Back to Top](#table-of-contents))

<!-- USAGE -->
## Usage

Will come later!

([Back to Top](#table-of-contents))

<!-- PROJECT ORGANIZATION -->
## Project Organization

- `.github/workflows`: Contains GitHub Actions used for building, testing, and publishing.
- `src/phytospatial`: Place new source code here.
- `tests`: Contains Python-based test cases to validate source code.
- `scripts`: Place new scripts to facilitate project maintenance here.
- `assets`: Contains images used in the project.
- `paper`: Contains the paper associated with this package.
- `pyproject.toml`: Contains metadata about the project and configurations for additional tools used to format, lint, type-check, and analyze Python code.

([Back to Top](#table-of-contents))

<!-- CONTRIBUTE -->
## Contribute

As an open-source project, we encourage and welcome contributions of students, researchers, or professional developers.

**Want to help?** Please read our [CONTRIBUTING](https://github.com/Louis-Gm/phytospatial/blob/main/CONTRIBUTING.md) section for a detailed explanation of how to submit pull requests. Please make sure to read the [CODE OF CONDUCT](https://github.com/Louis-Gm/phytospatial/blob/main/CODE_OF_CONDUCT.md) section before making contributions.

Not sure how to implement your idea, but want to contribute?
<br />
Feel free to leave a feature request <a href="https://github.com/Louis-Gm/phytospatial/issues">here</a>.

([Back to Top](#table-of-contents))

<!-- CITATION -->
## Citation

If you use this project in your research, please cite it as:

Grand'Maison, L.-V. (2026). Phytospatial (0.2.1-alpha). Zenodo. https://doi.org/10.5281/zenodo.18112045

([Back to Top](#table-of-contents))

<!-- CONTACT -->
## Contact

The project is currently being maintained by **Louis-Vincent Grand'Maison**.

Feel free to contact me by email or linkedin:
<br />
Email - [lvgra@ulaval.ca](mailto:lvgra@ulaval.ca)
<br />
Linkedin - [grandmaison-lv](https://www.linkedin.com/in/grandmaison-lv/)

([Back to Top](#table-of-contents))

<!-- FUNDING -->
## Acknowledgments & Funding

This software is developed by Louis-Vincent Grand'Maison as part of a PhD project. The maintenance and development of this project is supported by several research scholarships:

* Fonds de recherche du Québec – Nature et technologies (FRQNT) (Scholarship 2024-2025)
* Natural Sciences and Engineering Research Council of Canada (NSERC) (Scholarship 2025-present)
* Université Laval (Scholarship 2024-present)

([Back to Top](#table-of-contents))

<!-- LICENSE -->
## License

`phytospatial` is distributed under the Apache License, Version 2.0 or the MIT License, at your option.

Unless you explicitly state otherwise, any contribution you intentionally submit for inclusion in this repository (as defined by Apache-2.0) shall be dual-licensed as above, without any additional terms or conditions.

See [LICENSE-MIT](https://github.com/Louis-Gm/phytospatial/blob/main/LICENSE-MIT), [LICENSE-APACHE](https://raw.githubusercontent.com/Louis-Gm/phytospatial/LICENSE-APACHE) and [NOTICE](https://github.com/Louis-Gm/phytospatial/blob/main/NOTICE) for more information on licensing and copyright.

([Back to Top](#table-of-contents))
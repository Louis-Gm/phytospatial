<!-- HEADER AND LOGO -->
<br />
<div align="center">
  <a href="https://github.com/Louis-Gm/phytospatial">
    <img src="https://raw.githubusercontent.com/Louis-Gm/phytospatial/main/images/phytospatial.png" alt="Logo" width="420" height="420">
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
    <img src="https://img.shields.io/badge/python-3.10-blue.svg" alt="Python 3.10">
    <img src="https://img.shields.io/badge/license-MIT-green.svg" alt="MIT License">
    <img src="https://zenodo.org/badge/DOI/10.5281/zenodo.18112046.svg" alt="DOI">
  </p>
</div>

<!-- TABLE OF CONTENTS -->
## Table of Contents
| &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp; **Getting Started** &nbsp;&nbsp;&nbsp;&nbsp; | &nbsp;&nbsp;&nbsp;&nbsp; **Documentation** &nbsp;&nbsp;&nbsp;&nbsp; | &nbsp;&nbsp;&nbsp;&nbsp; **Community** &nbsp;&nbsp;&nbsp;&nbsp; |
|:--:|:--:|:--:|
| [About the Project](#about-the-project) | [Organization](#project-organization) | [Contribute](#contribute) |
| [Installation](#getting-started) | [Citation](#citation) | [Contact](#contact) |
| [Usage](#usage) | [License](#license) | [Acknowledgments](#acknowledgments--funding) |

<!-- ABOUT -->
## About The Project

**phytospatial** is a Python toolkit designed to streamline the processing of remote sensing data for forestry and vegetation analysis.

*Key features:*
* Will come later!

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
- `images`: Contains images used in the project.
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

Grand'Maison, L.V. (2025). Phytospatial: A python package for hyperspectral image processing in forestry [Computer software]. https://doi.org/10.5281/zenodo.18112045

([Back to Top](#table-of-contents))

<!-- CONTACT -->
## Contact

The project is being maintained by **Louis-Vincent Grand'Maison**.

Feel free to contact me by email or linkedin:
<br />
Email - [lvgra@ulaval.ca](mailto:lvgra@ulaval.ca)
<br />
Linkedin - [grandmaison-lv](https://www.linkedin.com/in/grandmaison-lv/)

([Back to Top](#table-of-contents))

<!-- FUNDING -->
## Acknowledgments & Funding

This software is developed by Louis-Vincent Grand'Maison as part of a PhD project at the Département des sciences géomatiques, Université Laval. The maintenance and development of this project is supported by several research scholarships:

* Fonds de recherche du Québec – Nature et technologies (FRQNT) (Scholarship 2024-2025)
* Natural Sciences and Engineering Research Council of Canada (NSERC) (Scholarship 2025-present)
* Université Laval (Scholarship 2024-present)

([Back to Top](#table-of-contents))

<!-- LICENSE -->
## License

Distributed under the MIT License. See [LICENSE](https://github.com/Louis-Gm/phytospatial/blob/main/LICENSE) for more information.

([Back to Top](#table-of-contents))



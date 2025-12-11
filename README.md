
<!-- HEADER AND LOGO -->
<a name="readme-top"></a>
<br />
<div align="center">
  <a href="https://github.com/Louis-Gm/phytospatial">
    <img src="images/phytospatial.png" alt="Logo" width="420" height="420">
  </a>

  <h3 align="center">phytospatial</h3>

  <p align="center">
    A python package to process remote sensing data for vegetation analysis!
    <br />
    <a href="https://github.com/Louis-Gm/phytospatial/issues">Report Bug</a>
    ·
    <a href="https://github.com/Louis-Gm/phytospatial/issues">Request Feature</a>
  </p>
  
  <p align="center">
    <img src="https://img.shields.io/badge/python-3.10-blue.svg" alt="Python 3.10">
    <img src="https://img.shields.io/badge/license-MIT-green.svg" alt="MIT License">
  </p>
</div>

<!-- TABLE OF CONTENTS -->

<details>
  <summary>Table of Contents</summary>
  <ol>
    <li><a href="#about-the-project">About The Project</a></li>
    <li><a href="#getting-started">Getting Started</a></li>
    <li><a href="#usage">Usage</a></li>
    <li><a href="#contribute">Contribute</a></li>
    <li><a href="#citation">Citation</a></li>
    <li><a href="#contact">Contact</a></li>
    <li><a href="#funding">Funding</a></li>
  </ol>
</details>

<!-- ABOUT -->
## About The Project

**phytospatial** is a Python toolkit designed to streamline the processing of remote sensing data for forestry and vegetation analysis.

*Key features:*
* Will come later!

<p align="right">(<a href="#readme-top">back to top</a>)</p>

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

You are now ready to run the package, Celebrate! 🥂

### Usage

Will come later!

<!-- CONTRIBUTING -->
## Contribute

The project is being maintained by **Louis-Vincent Grand'Maison** (Université Laval).

As an open-source project, we encourage and welcome your contributions, whether you are a student, researcher, or developer.

**Want to help?** Please read our [CONTRIBUTING.md](./CONTRIBUTING.md) for details on our code of conduct and the process for submitting pull requests.

<p align="right">(<a href="#readme-top">back to top</a>)</p>

## Citation

If you use this project in your research, please cite it as:

Grand'Maison, L.V. (2025). Phytospatial: A python package for vegetation analysis. Université Laval.

<!-- CONTACT -->
### Contact

Email - [lvgra@ulaval.ca](mailto:lvgra@ulaval.ca)

Linkedin - [grandmaison-lv](https://www.linkedin.com/in/grandmaison-lv/)

<!-- FUNDING -->
### Funding

This project was initially funded through a scholarship from the **Fonds de Recherche du Québec - Secteur Nature et Technologies (2024-2025)**.

It is currently funded through scholarships from **Université Laval (2024-present)** and the **Natural Sciences and Engineering Research Council of Canada (2025-present)**.

<!-- LICENSE -->
## License

Distributed under the MIT License. See [LICENSE](./LICENSE) for more information.

<p align="right">(<a href="#readme-top">back to top</a>)</p>




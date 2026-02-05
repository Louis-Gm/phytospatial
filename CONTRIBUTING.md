# Contributing to phytospatial

First off, thank you for considering contributing to **phytospatial**! 

The project is currently maintained by **Louis-Vincent Grand'Maison**. 

As an academic open-source project, we encourage and welcome collaborations from other researchers.

## Legal & Licensing

By contributing to this repository (via Pull Requests, Issues, or otherwise), you agree to the following terms:

1.  **License Agreement:** You agree that your contributions will be distributed under the project's  **Apache-2.0 license**. See [LICENSE](https://phytospatial.readthedocs.io/en/latest/license/) for more information on licensing and copyright.
2.  **Academic Integrity:** As this project is part of active research, please ensure any citations or algorithms added are properly referenced.
3.  **Code of conduct:** As an open-sourced project, it is important to understand our code of conduct prior to contributing. See [CODE_OF_CONDUCT](https://phytospatial.readthedocs.io/en/latest/contributing/code_of_conduct/) prior to contributing.

## Project Structure

* `src/phytospatial`: Core source code files.
* `tests`: Pytest suite for the source code. Unit tests are for single modules whereas integration tests aim to capture interactions between modules.
* `.github`: CI/CD workflows (Tests, Release). Also contains issue templates for bug reports or feature requests.
* `scripts`: Maintenance scripts for the project.
* `docs`: Documentation files for the project. Contains three subdirectories
  * `examples`: Tutorial jupyter notebooks 
  * `reference`: Reference files for source code documentation.
  * `contributing`: Specific documentation for contributors

## How to Contribute

If you have an idea for a new feature or have found a bug, please follow these steps to submit your changes.

### 1. Fork the Project
Click the "Fork" button at the top right of the repository page. This creates a copy of the code under your own GitHub account.

### 2. Create your own Branch
Open your terminal/command prompt. Create a new branch for your specific task. 
Ideally, please use the following naming convention:
* Use lowercase and hyphens (*kebab-case*)
* Prefix with `feat/` for features, `fix/` for bugs or `docs/` for documentation.

**Examples**
* `feat/raster-calculator`
* `fix/installation-error`
* `docs/update-readme`

```sh
git checkout -b feat/your-feature-name
```

### 3. Commit your changes

Make your changes in the code. Once you are done, commit them with a clear message explaining what you did.

```sh
git commit -m "Add function to calculate canopy height"
```

### 4. Push to the branch

Upload your branch to your forked repository on GitHub.

```sh
git push origin feat/your-feature-name
```

### 5. Create a pull request

1. Go to the original phytospatial repository on GitHub.

2. Locate the prompt to **"Compare & pull request"**.

3. Click it, write a description of your changes, and submit!

## Note on dependencies

If your new feature requires installing a new Python library, please **mention it in your Pull Request description** so we can update `environment.yml`.

## Release Protocol

We follow a strict, automated protocol for releasing new versions to ensure consistency across PyPI, GitHub, and our [readthedocs](https://phytospatial.readthedocs.io/en/latest/) website. Manual version bumps are strongly discouraged.

If you are a contributor looking to publish a new version, please strictly follow the steps outlined in [RELEASING](https://phytospatial.readthedocs.io/en/latest/contributing/releasing/).

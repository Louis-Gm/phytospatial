# Contributing to phytospatial

First off, thank you for considering contributing to **phytospatial**! 

The project is currently maintained by **Louis-Vincent Grand'Maison**. 

As an academic open-source project, we encourage and welcome collaborations from other researchers.

## Legal & Licensing

By contributing to this repository (via Pull Request, Issue, or otherwise), you agree to the following terms:

1.  **License Agreement:** You agree that your contributions will be distributed under the project's **MIT License**. See [LICENSE](https://raw.githubusercontent.com/Louis-Gm/phytospatial/LICENSE) for more information on licensing and copyright.
2.  **Academic Integrity:** As this project is part of active research, please ensure any citations or algorithms added are properly referenced.

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

If your new feature requires installing a new Python library, please **mention it in your Pull Request description** so we can update environment.yml and requirements.txt.

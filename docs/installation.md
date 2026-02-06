# Installation Guide

Welcome to **Phytospatial**! This guide will help you download the code, set up a secure Python environment, and install the package using your preferred package manager.

## Prerequisites

Before starting, ensure you have the following installed:
* **Python 3.10+**: [Download Python here](https://www.python.org/downloads/)
* **Conda**: We highly recommend using [Anaconda](https://www.anaconda.com/products/distribution) (or miniconda) for managing environments.

---

## 1. Set Up Your Environment

To avoid conflicts with other software, we recommend creating a dedicated virtual environment for this project. Choose **one** of the methods below.

### Option A: Using Conda (Recommended)
This is ideal if you want a self-contained environment that manages both Python and non-Python dependencies.
NOTE: You can also download our environment.yml file and create the environment from there.

1. Create and name your environment:

   ```sh
   conda create -n phytospatial_env python=3.10
   ```

2. Activate the new environment:

   ```sh
   conda activate phytospatial_env
   ```

3. Install Phytospatial from PyPI:

   ```sh
   pip install phytospatial
   ```

### Option B: Using Standard Python (pip)
Use this if you prefer a lightweight, native Python setup.

1. **Create the virtual environment:**
   * **Windows:**

     ```sh
     python -m venv venv
     ```

   * **Mac/Linux:**

     ```sh
     python3 -m venv venv
     ```

2. **Activate the environment:**
   * **Windows:**

     ```sh
     .\venv\Scripts\activate
     ```
   * **Mac/Linux:**

     ```sh
     source venv/bin/activate
     ```

3. **Install dependencies manually:**

     ```sh
     pip install --upgrade pip pip install phytospatial
     ```

---

## 2. Install optional dependencies
If you intend to perform advanced spatial analysis, you can install the extra feature set:

```sh
pip install "phytospatial[analysis]"
```

---

## 3. Verify Installation
Check that the package is correctly recognized by your system:

```sh
python -c "import phytospatial; print('Phytospatial version ' + phytospatial.version + ' installed successfully!')"
```
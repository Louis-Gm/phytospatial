# Installation Guide

Welcome to **Phytospatial**! This guide will help you download the code, set up a secure Python environment, and install the package on your machine.

## Prerequisites

Before starting, ensure you have the following installed:
* **Git**: [Download Git here](https://git-scm.com/downloads)
* **Python Distribution**: We highly recommend [Miniconda](https://docs.conda.io/en/latest/miniconda.html) or [Anaconda](https://www.anaconda.com/products/distribution) for managing environments.

---

## 1. Get the Code (Cloning)

First, you need to download the repository to your local computer using Git.

1. Open your terminal (Command Prompt, PowerShell, or Terminal).
2. Navigate to the folder where you want to store the project:
   ```sh
   cd path/to/your/projects/folder
   ```
3. Clone the repository:
   ```sh
   git clone https://github.com/Louis-Gm/phytospatial.git
   ```
4. Enter the project directory:
   ```sh
   cd phytospatial
   ```

---

## 2. Set Up Your Environment

To avoid conflicts with other software, you should create a dedicated "virtual environment" for this project. Choose **one** of the methods below.

### Option A: Using Conda (Recommended)
This is the easiest method. We provide a pre-configured file (`environment.yml`) that installs Python and necessary libraries automatically.

1. Create the environment from the file:
   ```sh
   conda env create -f environment.yml
   ```
2. Activate the new environment:
   ```sh
   conda activate phytospatial_env
   ```

### Option B: Using Standard Python (pip)
If you prefer not to use Conda, you can use Python's built-in tools.

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
   pip install --upgrade pip
   pip install -e .[analysis]
   ```

---

## 3. Verify Installation

Once your environment is active and the package is installed, verify that everything is working correctly:

```sh
python -c "import phytospatial; print('Phytospatial installed successfully!')"
```
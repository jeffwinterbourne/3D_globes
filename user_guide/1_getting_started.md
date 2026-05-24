# 1. Getting Started

Welcome! Setting up a scientific Python environment can sometimes feel daunting, especially with libraries that process geospatial data. This page guides you through installing the environment step-by-step so you can start creating globes with ease.

---

## 🛠️ Prerequisites: Install Conda (Recommended)

`globe3d` relies on heavy-duty scientific libraries like `numpy` (for math), `scipy` (for interpolation), and `trimesh` (for 3D mesh modeling). Some of these packages—particularly `netCDF4` (which reads scientific grids) and `rasterio` (for GeoTIFF images)—rely on underlying C libraries that can be tricky to compile manually.

To save you from compilation errors, we recommend using **Conda** (a package manager that downloads pre-compiled versions of these scientific libraries).

1. Download the installer suited for your operating system:
   - [Miniconda Installer (Recommended - lightweight, fast)](https://docs.conda.io/en/latest/miniconda.html)
   - [Anaconda Installer (Full suite, includes a desktop dashboard)](https://www.anaconda.com/products/individual)
2. Run the installer and follow the instructions. If you are on Windows, we recommend checking the option to "Add Conda to my PATH" or using the **Anaconda Prompt** terminal that the installer installs.

---

## 🚀 Step 1: Clone the Project Code

Open your terminal (Linux/macOS) or your **Anaconda Prompt / PowerShell** (Windows) and download the repository:

```bash
git clone https://github.com/jeffwinterbourne/3D_globes.git
cd 3D_globes
```

---

## 📦 Step 2: Set Up Your Python Environment

We will create an isolated environment called `pygmt` where all our project dependencies will live safely without conflicting with other Python code on your computer.

Run the following commands in your terminal:

1. **Create and Activate the Environment**:
   This installs Python 3.12 inside our clean space.
   ```bash
   conda create -n pygmt python=3.12 -y
   conda activate pygmt
   ```
2. **Install netCDF4 (Pre-compiled)**:
   We fetch this from `conda-forge` to ensure the underlying C-libraries link perfectly:
   ```bash
   conda install -c conda-forge netcdf4 -y
   ```
3. **Install rasterio (Optional, for TIFF maps)**:
   If you plan to load height maps or elevation models from `.tif` or `.tiff` files:
   ```bash
   conda install -c conda-forge rasterio -y
   ```

---

## 💻 Step 3: Install the `globe3d` Package

We will now install the `globe3d` package in **editable mode** (using `-e .`). This tells Python to register the library in your environment while pointing directly to the code in your folder. Any edits made in the code will take effect immediately without having to re-install.

```bash
pip install -e .
```

*This will automatically pull in all other necessary libraries (such as NumPy, SciPy, Matplotlib, Trimesh, Tqdm, and Cmocean).*

---

## 🔍 Step 4: Verify Your Installation

Let's make sure everything is installed and functioning correctly by running our automated test suite:

```bash
pytest
```

If everything is correct, you should see green text indicating that all tests (e.g., `34 passed`) succeeded!

### 📓 Launching the Example Notebooks

To run the interactive tutorials:

1. Install Jupyter Lab inside your conda environment:
   ```bash
   conda install -c conda-forge jupyterlab -y
   ```
2. Launch Jupyter Lab from the project root directory:
   ```bash
   jupyter lab
   ```
3. The browser window will open. Click on the `examples` folder to open any tutorial notebook and run it cell-by-cell!

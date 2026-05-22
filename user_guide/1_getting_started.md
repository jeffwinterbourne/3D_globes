# 1. Getting Started

This page explains how to set up your environment, clone the `globe3d` repository, install the library, and verify your installation.

---

## Prerequisites: Install Conda

`globe3d` relies on several scientific Python libraries (like `numpy`, `scipy`, and `trimesh`). Some packages—particularly spatial libraries like `netCDF4`—can be difficult to compile manually. We recommend using **Miniconda** or **Anaconda** to manage your python packages safely.

1. Download the installer for your operating system:
   - [Miniconda Installer (Recommended, lightweight)](https://docs.conda.io/en/latest/miniconda.html)
   - [Anaconda Installer (Full desktop application)](https://www.anaconda.com/products/individual)
2. Follow the installation instructions for your system, making sure to add Conda to your shell/terminal path when prompted.

---

## Step 1: Clone the Git Repository

Open your terminal (Linux/macOS) or Command Prompt/PowerShell (Windows) and clone the repository:

```bash
git clone https://github.com/jeffwinterbourne/3D_globes.git
cd 3D_globes
```

---

## Step 2: Set Up the Conda Environment

We use a Conda environment called `pygmt` to ensure all spatial dependencies are resolved properly.

### Windows, macOS, and Linux Setup

1. **Create and Activate the Environment**:
   ```bash
   conda create -n pygmt python=3.12 -y
   conda activate pygmt
   ```
2. **Install netCDF4 (from conda-forge)**:
   It is best to install `netCDF4` via Conda first to ensure the underlying C libraries are linked correctly:
   ```bash
   conda install -c conda-forge netcdf4 -y
   ```
3. **Install rasterio (optional, for GeoTIFF support)**:
   If you plan to use GeoTIFF grids, install `rasterio`:
   ```bash
   conda install -c conda-forge rasterio -y
   ```

---

## Step 3: Install the `globe3d` Package

Install `globe3d` in **editable mode**. This installs the package while allowing any changes you make to the code inside the `src/` directory to take effect immediately without re-installing:

```bash
pip install -e .
```

This will automatically pull in all other necessary dependencies (like `numpy`, `scipy`, `matplotlib`, `trimesh`, `tqdm`, and `cmocean`).

---

## Step 4: Verify the Installation

To ensure everything is installed and working correctly, run the `pytest` test suite:

```bash
pytest
```

If the installation was successful, all tests should pass with green checkmarks (e.g. `34 passed`).

### Starting Jupyter Notebooks

To run the interactive example notebooks accompanying this guide:

1. Install Jupyter Lab or Notebook:
   ```bash
   conda install -c conda-forge jupyterlab -y
   ```
2. Launch Jupyter Lab from the project root directory:
   ```bash
   jupyter lab
   ```
3. Open any notebook in the `examples/` directory to run it step-by-step.

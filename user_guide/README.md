# 🌐 globe3d: User & Educator Guide

Welcome to the user guide for `globe3d`! This library was created to fully automate the process of turning global scientific datasets into stunning, tactile, 3D-printable globes. 

Whether you are an **Earth scientist** wanting to feel seismic tomography anomalies, an **educator** looking to teach plate tectonics and planetary structures through touch, or a **novice maker** eager to print a custom planet, this guide is designed for you. You don't need to be an expert programmer to create beautiful models; we will walk you through every step.

---

## 📖 Guide Index

This guide is structured as a step-by-step path to taking a raw dataset and turning it into a physical object in your hands:

1. [**Getting Started**](1_getting_started.md)
   Set up your Python environment on Windows, macOS, or Linux, install the library, and verify your installation.
2. [**Data Formats & Requirements**](2_data_formats.md)
   Learn about the inputs (NetCDF grids, topography images, color maps) and outputs (STL/OBJ files) and how they relate to what your 3D printer needs.
3. [**Key Concepts**](3_key_concepts.md)
   Understand *why* we design globes the way we do—the physics and geometry of Fibonacci lattices, hollowing to save plastic, splitting to avoid support material, and using magnetic joints.
4. [**Example 1: Basic Globe**](4_example_basic.md)
   Create a single solid sphere and displace its surface with scaled topography—perfect for a first test print.
5. [**Example 2: Intermediate Globe**](5_example_intermediate.md)
   Combine multiple datasets (like seismic tomography with surface topography), apply a coastal boundary step, and split the globe into hemispheres.
6. [**Example 3: Adding Magnets**](6_example_magnets.md)
   Design magnet cavities inside the flat mating surfaces so your hemispheres snap together perfectly.
7. [**Example 4: Coloured Globe**](7_example_coloured.md)
   The ultimate pipeline: topography, coastal steps, split hemispheres, independent coloring for internal and external surfaces, and exporting for multi-color printing.
8. [**Where to Get Data**](8_where_to_get_data.md)
   A curated library of free, open-source repositories where you can download global grids of Earth topography (ETOPO), lunar and planetary elevations, seismic tomography, geoid heights, and crustal thickness.

---

## 🧪 Interactive Jupyter Notebooks

If you prefer to learn by doing, every tutorial page corresponds to a fully documented, cell-by-cell Jupyter Notebook in the [examples/](../examples) directory:

- [**example_1_basic_globe.ipynb**](../examples/example_1_basic_globe.ipynb)
- [**example_2_intermediate_globe.ipynb**](../examples/example_2_intermediate_globe.ipynb)
- [**example_3_magnets_globe.ipynb**](../examples/example_3_magnets_globe.ipynb)
- [**example_4_coloured_globe.ipynb**](../examples/example_4_coloured_globe.ipynb)

These notebooks are configured with live 3D visualization helpers so you can preview and verify your model's details interactively before writing the final files for 3D printing.

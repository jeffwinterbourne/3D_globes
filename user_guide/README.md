# globe3d User Guide

Welcome to the comprehensive user guide for `globe3d`! This guide is designed to help users—even those with limited Python experience—learn how to use the `globe3d` library to generate beautiful, 3D-printable globe models with exaggerated topography, custom textures, hollowed shells, and magnetic split-hemisphere joints.

---

## Guide Index

This guide is structured into logical steps:

1. [**Getting Started**](1_getting_started.md)
   Learn how to set up your python environment on Windows, macOS, or Linux, clone the git repository, install `globe3d`, and run the test suite to verify your setup.
2. [**Data Formats & Requirements**](2_data_formats.md)
   Understand the supported input grid formats (NetCDF, GMT), image formats for surface coloring, and output 3D file formats (STL, OBJ). Learn how color maps are represented.
3. [**Key Concepts**](3_key_concepts.md)
   Explore the core geometric representations (vertices, faces, color arrays), the Fibonacci lattice, how mesh hollowing (inner vs. outer surfaces) works, how hemispheres are split, and how to import and slice your models in slicers like Bambu Studio or OrcaSlicer.
4. [**Example 1: Basic Globe**](4_example_basic.md)
   A walkthrough for generating a single solid sphere and displacing its surface with topography, with no color.
5. [**Example 2: Intermediate Globe**](5_example_intermediate.md)
   A walkthrough for combining multiple grid displacements (tomography + topography), applying a coastal step, and splitting the model into hemispheres.
6. [**Example 3: Adding Magnets**](6_example_magnets.md)
   Learn how to add magnet voids to the mating surface of split hemispheres using both the "bosses" and "inside shell" methods, generate test pieces, and tune tolerances.
7. [**Example 4: Coloured Globe**](7_example_coloured.md)
   A complete step-by-step walkthrough of the entire pipeline, incorporating topography, coastal steps, split hemispheres, independent coloring for inner and outer surfaces, and OBJ output.

---

## Example Notebooks

Each tutorial section is accompanied by a fully functional, self-contained Jupyter Notebook in the [examples/](../examples) directory:

- [**example_1_basic_globe.ipynb**](../examples/example_1_basic_globe.ipynb)
- [**example_2_intermediate_globe.ipynb**](../examples/example_2_intermediate_globe.ipynb)
- [**example_3_magnets_globe.ipynb**](../examples/example_3_magnets_globe.ipynb)
- [**example_4_coloured_globe.ipynb**](../examples/example_4_coloured_globe.ipynb)

These notebooks are organized cell-by-cell with visualization helpers so you can verify each stage of the model generation pipeline interactively.

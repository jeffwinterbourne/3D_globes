# 3. Key Concepts

This page explains the core concepts, data structures, and mechanics behind the `globe3d` library, plus guidance on 3D slicers.

---

## 🏗️ Core Data Structures

A 3D mesh in `globe3d` is represented by two primary NumPy arrays:

1. **Vertices (`(N, 3)` Float Array)**:
   A list of Cartesian coordinates $(x, y, z)$ in model space (typically in millimeters).
2. **Faces (`(F, 3)` Integer Array)**:
   A list of triangles. Each row consists of three indices corresponding to the vertices that make up that triangle.

Optional coloring is represented by:
3. **Colors (`(N, 3)` Float Array)**:
   RGB color values in the range $[0.0, 1.0]$ for each of the $N$ vertices.

---

## 🌐 Sphere Generation Strategies

To represent a sphere, we distribute points as evenly as possible. `globe3d` provides two algorithms:

### 1. Fibonacci Sphere Lattice (`generate_sphere_points_fibonacci`)
Distributes points uniformly using a spherical Fibonacci spiral.
- **Winding**: Connects points using a Delaunay triangulation on the sphere.
- **Advantage**: You can specify the exact number of vertices (e.g. 10,000 or 1,000,000). Highly recommended for high-resolution print models.

### 2. Subdivided Icosahedron (`generate_sphere_points_icosahedron`)
Starts with a regular 12-vertex icosahedron and repeatedly subdivides each triangular face.
- **Advantage**: Perfect uniformity of triangle shapes.
- **Disadvantage**: Vertex count grows exponentially: $10 \times 4^s + 2$ (where $s$ is the number of subdivisions).

---

## 🕳️ Hollow Globes: Inner vs. Outer Surface

Solid globes are heavy, use a lot of plastic, and are prone to warping during printing. Hollowing out the inside of the globe solves this.

```
                  _..._             <- Displaced Outer Shell
                .'     '.
               /   ___   \
              |   /   \   |         <- Hollow Cavity (Inner Shell)
              |  |  x  |  |
              |   \___/   |
               \         /
                '.     .'
                  `"""`
```

### Why Splitting Before Hollowing is Critical
When creating a split globe (e.g. top and bottom hemispheres), the order of operations matters:

1. **Incorrect Approach**: If you hollow the globe first, and then slice it with a plane cut, modern slicers and boolean engines will cap the entire flat circular face of the cut. This seals the hollow cavity shut, treating it as solid.
2. **Correct Approach** (`create_hollow_hemispheres`):
   - First, slice the displaced **outer shell** into two capped hemispheres.
   - Second, boolean-subtract the **inner shell** from each half.
   - This creates an **annular cap** (a flat ring face on the mating surface) with the hollow cavity completely open.

---

## 🧲 Annular Caps & Magnet Voids

The mating flat surfaces (the annular caps) of the top and bottom hemispheres are ideal locations for aligning and securing the halves together:
- **Bosses**: Extra cylindrical plastic towers enclosing the magnet holes. Needed if the shell wall is thinner than the magnet depth.
- **No-Bosses (Shell-Placement)**: Places the magnet voids directly inside the natural thickness of the shell (if the topography is thick enough), avoiding protruding plastic bosses.

---

## 🖨️ Slicing in Bambu Studio / OrcaSlicer

To print your OBJ models with vertex colors:

1. **Import the OBJ**:
   - Drag and drop your `.obj` files into **Bambu Studio** or **OrcaSlicer**.
   - If the slicer asks if you want to load it as a single multi-part object, select **Yes**.
2. **Assign Filaments to Colors**:
   - In the slicer, use the "Paint bucket" tool or right-click the parts to assign different filaments (e.g. Filament 1 for the land, Filament 2 for oceans).
   - The slicer automatically maps the vertex color values in the OBJ to the closest filament slot.
3. **Print Orientation**:
   - Orient the hemispheres flat-side down on the build plate. This ensures a clean, smooth mating surface and requires no support material on the interior cavity.
4. **Supports**:
   - Enable supports for the outer overhangs near the poles (usually tree supports work best).
5. **Infill & Walls**:
   - Use $2-3$ walls and $10-15\%$ infill.

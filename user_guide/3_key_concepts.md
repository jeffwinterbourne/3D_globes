# 3. Key Concepts

This page breaks down the core concepts behind the `globe3d` library, explaining how virtual mathematical meshes in Python become physical, sliceable models in your slicer (like Bambu Studio, OrcaSlicer, or PrusaSlicer).

---

## 🏗️ How a 3D Mesh is Represented

In Python, a 3D mesh is represented using two coordinate arrays of numbers (using the fast **NumPy** library):

1. **Vertices (a list of points, shape `(N, 3)`)**:
   Coordinates $(x, y, z)$ in millimeters defining where each corner of the model sits.
2. **Faces (a list of triangles, shape `(F, 3)`)**:
   Indices pointing to the vertices. Each row is a group of three vertices that are connected to form a flat triangle.
3. **Colors (Optional, shape `(N, 3)`)**:
   Red, Green, and Blue values between `0.0` and `1.0` assigned to each vertex, allowing multi-color printing.

---

## 🌐 Creating a Spherical Grid

To represent a sphere, we need to distribute points on its surface as evenly as possible. If we used standard latitude/longitude lines (a UV sphere), the points would cluster heavily at the poles, making the mesh inefficient and causing slicing errors. `globe3d` offers two algorithms:

### 1. Fibonacci Lattice (`generate_sphere_points_fibonacci`) — *Recommended*
Distributes points in a uniform, spiral pattern on the sphere (based on the golden ratio).
- **Advantages**: Points are extremely evenly distributed. You can specify the exact number of vertices you want (e.g. 5,000 for quick testing, 150,000 for high-detail printing).
- **Use Case**: This is our go-to grid for high-resolution planetary models.

### 2. Subdivided Icosahedron (`generate_sphere_points_icosahedron`)
Starts with a 20-sided regular shape (like a 20-sided gaming die) and repeatedly splits every triangle into four smaller triangles.
- **Advantages**: Triangles are perfectly uniform in shape.
- **Disadvantages**: You cannot pick the exact number of vertices; they grow exponentially ($10 \times 4^s + 2$ where $s$ is the number of subdivisions).

---

## 🕳️ Hollowing the Globe: Saving Plastic & Time

Printing a solid sphere uses a massive amount of plastic, takes days to print, and is prone to warping as the hot plastic cools. To prevent this, we hollow out the inside of the globe.

```
                  _..._             <- Displaced Outer Shell (Planetary Topography)
                .'     '.
               /   ___   \
              |   /   \   |         <- Hollow Cavity (Inner Shell, constant radius)
              |  |  x  |  |
              |   \___/   |
               \         /
                '.     .'
                  `"""`
```

### ⚠️ The Secret to Splitting & Hollowing
When creating a split globe (e.g. a top and bottom hemisphere held together by magnets), the order of operations in Python is critical:

1. **The Incorrect Way**: If you hollowed the sphere first, and then sliced it in half, your 3D slicing software would see the flat cut and cap it with a solid layer. This would seal the hollow cavity shut, wasting plastic.
2. **The Correct Way (Used by `globe3d`)**:
   - First, slice the outer shell into two hemispheres.
   - Second, cap the cut flat surface to create a flat "mating face."
   - Third, subtract the inner hollow sphere from the hemisphere mesh.
   - This results in an **annular cap** (a flat ring surface on the joint) with the hollow interior completely open to the air, ready for printing.

---

## 🧲 Annular Caps & Magnet Voids

The flat mating surface (the annular cap) of each hemisphere is the perfect place to put joint hardware:
- **Inside Shell (No Bosses)**: If your globe wall is thick enough, you can sink magnet holes directly into the shell wall without changing its shape.
- **Bosses**: If the globe wall is thin (e.g. 2-3 mm) and you need to fit a 2 mm deep magnet, we add small cylindrical "towers" of plastic (bosses) on the inside wall of the cavity to anchor the magnets safely.

---

## 🖨️ 3D Slicing & Printing Tips

Here is how to set up your files in **Bambu Studio** or **OrcaSlicer** for a successful print:

1. **Import the OBJ**:
   Drag your `.obj` file onto the build plate. If the slicer asks if you want to import it as a single multi-part object, click **Yes**.
2. **Map Colors to Filaments**:
   Use the Paint bucket tool or right-click the parts to assign filaments (e.g., Filament 1 for oceans, Filament 2 for land). The slicer will auto-map your OBJ's vertex colors to the closest filament color.
3. **Orient Flat Side Down**:
   Place the split hemispheres flat-side down on the build plate. This ensures strong adhesion to the build plate and means the interior cavity prints cleanly with **zero supports**.
4. **Supports for the Exterior**:
   Enable supports (we recommend "Tree supports") only for the steep overhangs on the outer surface near the pole (the top of the dome).
5. **Infill & Walls**:
   Since the globe is hollowed, use $2-3$ walls and $10-15\%$ infill for the solid shell sections. This keeps the model strong but lightweight.

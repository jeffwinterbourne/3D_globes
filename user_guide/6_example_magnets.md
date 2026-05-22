# 6. Example 3: Adding Magnets

This tutorial explains how to add magnet voids and bosses to the equatorial mating surface of your split hemispheres, and how to print a calibration test piece to fine-tune tolerances.

The complete notebook is located at [examples/example_3_magnets_globe.ipynb](../examples/example_3_magnets_globe.ipynb).

---

## The Hollowing & Magnet Insertion Pipeline

When printing split globes, it is best to:
1. Split the outer displaced mesh into top and bottom capped hemispheres.
2. Hollow each hemisphere by subtracting a smaller concentric sphere (the inner mesh).
3. Insert magnet voids (and optional reinforcing bosses) along the flat mating ring.

`globe3d` automates this entire pipeline inside the `create_hollow_hemispheres` function.

---

## Tolerances: Getting the Perfect Fit

Because 3D printers squeeze plastic slightly outward as they print, a $5.0\text{ mm}$ hole will usually be too tight for a $5.0\text{ mm}$ magnet. To account for this, we add small tolerances:
- **Radial/Horizontal Tolerance (`h_tol`)**: Typically $0.1\text{ to } 0.2\text{ mm}$. Added to the radius of the magnet.
- **Vertical Tolerance (`v_tol`)**: Typically $0.05\text{ to } 0.15\text{ mm}$. Added to the height/depth of the magnet void.
- **Vertical Offset (`v_offset`)**: The thickness of the plastic ceiling above the magnet (so it doesn't break through the flat mating surface). Typically $0.2\text{ mm}$ (exactly one or two print layers).

---

## Code Walkthrough

### 1. Import Libraries
```python
import os
import trimesh
from globe3d import (
    generate_sphere_points_fibonacci,
    create_hollow_hemispheres,
    generate_magnet_test_piece
)
```

### 2. Prepare Outer and Inner Spheres
We generate a high-detail outer sphere (which we would displace) and a coarser, slightly smaller inner sphere defining the cavity:
```python
model_radius_mm = 40.0

# Coarse outer sphere for demo
outer_vertices, outer_faces = generate_sphere_points_fibonacci(n_points=6000, radius=model_radius_mm)

# Inner sphere (75% of radius -> 10 mm thick default wall)
inner_vertices, inner_faces = generate_sphere_points_fibonacci(n_points=1000, radius=model_radius_mm * 0.75)
```

### 3. Alternative A: Magnet Placement WITH Bosses (`add_bosses=True`)
Use this when you want magnets placed at exact angular positions, and need plastic reinforcement "bosses" to shield the magnets because the shell wall is thin.
```python
magnet_params_bosses = {
    'magnet_diameter': 5.0,        # 5mm diameter
    'magnet_height': 2.0,          # 2mm height
    'h_tol': 0.15,                 # 0.15mm radial tolerance
    'v_tol': 0.10,                 # 0.10mm vertical tolerance
    'v_offset': 0.20,              # 0.20mm floor thickness
    'min_thick': 1.5,              # 1.5mm wall surrounding the void
    'n_magnets': 3,                # 3 magnets per side
    'start_lon': 0.0,              # Space them evenly starting at 0 degrees
    'add_bosses': True             # Reinforce with cylindrical towers
}

top_bosses, bottom_bosses = create_hollow_hemispheres(
    outer_vertices=outer_vertices,
    outer_faces=outer_faces,
    inner_vertices=inner_vertices,
    inner_faces=inner_faces,
    engine='manifold',
    magnet_params=magnet_params_bosses
)
print("Generated hollow hemispheres with bosses.")
```

### 4. Alternative B: Magnet Placement WITHOUT Bosses (Inside Shell)
Use this to keep the interior cavity clean and avoid extra printed material. The algorithm steps around the shell at `step_degrees` increments and checks where a magnet void fits safely inside the natural wall thickness, selecting the positions that maximize angular spacing uniformity:
```python
magnet_params_no_bosses = {
    'magnet_diameter': 5.0,
    'magnet_height': 2.0,
    'h_tol': 0.15,
    'v_tol': 0.10,
    'v_offset': 0.20,
    'min_thick': 1.5,
    'n_magnets': 3,
    'min_magnets': 2,             # Raise error if fewer than 2 fit
    'min_angular_spacing': 60.0,  # Keep them at least 60 degrees apart
    'step_degrees': 2.0,          # Step search resolution
    'add_bosses': False           # Do not build bosses; fit inside the shell
}

top_noboss, bottom_noboss = create_hollow_hemispheres(
    outer_vertices=outer_vertices,
    outer_faces=outer_faces,
    inner_vertices=inner_vertices,
    inner_faces=inner_faces,
    engine='manifold',
    magnet_params=magnet_params_no_bosses
)
print("Generated hollow hemispheres without bosses.")
```

---

## 🔬 Calibrating with a Test Piece

Instead of printing a whole globe to test if your magnets fit, you should print a quick, 10-minute test cylinder containing a single magnet void.

Use the `generate_magnet_test_piece` function:
```python
output_dir = "../outputs"
os.makedirs(output_dir, exist_ok=True)
test_piece_path = os.path.join(output_dir, "magnet_test_piece.stl")

# Generates a cylinder that fits one magnet
generate_magnet_test_piece(
    diameter=5.0,
    height=2.0,
    horizontal_tolerance=0.15,
    vertical_tolerance=0.10,
    vertical_offset=0.20,
    min_thickness=1.5,
    output_path=test_piece_path
)
print(f"Generated calibration test piece at {test_piece_path}")
```

### Tuning Process:
1. Print the test piece.
2. Push your magnet into the void.
3. **If it is too loose** (falls out): Decrease `h_tol` or `v_tol`.
4. **If it is too tight** (won't push in): Increase `h_tol` or `v_tol`.
5. Once tuned, use those exact tolerance values in your main globe `magnet_params`.

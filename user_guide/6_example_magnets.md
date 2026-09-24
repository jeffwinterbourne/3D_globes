# 6. Example 3: Adding Magnets

This tutorial explains how to add magnet cavities and structural reinforcement "bosses" to the equatorial mating surface of split hemispheres, allowing the halves to snap together perfectly. We will also generate a calibration test piece to fine-tune your printer's tolerances.

The complete interactive notebook is located at [examples/example_3_magnets_globe.ipynb](../examples/example_3_magnets_globe.ipynb).

---

## 🧲 Why Add Magnets?
To turn a split globe into an interactive model—like the nested "Seismic Matryoshka" or the "Earth Interior" model—you need a way to hold the hemispheres together that is clean and repeatable. Embedded neodymium magnets are perfect. They align the hemispheres automatically and hold them securely, yet let users easily separate the halves to inspect the interior.

### 🔍 Understanding Tolerances
Because 3D printers extrude hot plastic that swells slightly as it cools, printing a $5.0\text{ mm}$ hole will result in a hole that is too small for a $5.0\text{ mm}$ magnet. To account for this, we add small adjustments:
- **Horizontal/Radial Tolerance (`horizontal_tolerance`)**: Typically $0.1\text{ to } 0.2\text{ mm}$. This widens the hole so the magnet slides in smoothly.
- **Vertical Tolerance (`vertical_tolerance`)**: Typically $0.05\text{ to } 0.15\text{ mm}$. This adds extra depth to the pocket so the magnet doesn't sit proud of the flat surface.
- **Ceiling Thickness (`vertical_offset`)**: The thickness of the plastic layer between the magnet pocket and the flat mating surface. A thickness of $0.2\text{ mm}$ (usually one or two print layers) keeps the magnet invisible and close enough to retain high magnetic pull.

---

## 💻 Code Walkthrough

### 1. Import Libraries
We import the core model constructor and the test piece helper:
```python
import os
from globe3d import GlobeModel, generate_magnet_test_piece
```

### 2. Prepare the Hollow Model
We initialize our model with `hollow=True` and define an `inner_ratio` of `0.5` (which makes the hollow cavity $50\%$ of the outer radius, leaving a thick wall perfect for magnet pockets):
```python
model_radius_mm = 40.0

# Initialize a hollow model
model = GlobeModel(
    n_points=6000,
    radius=model_radius_mm,
    hollow=True,
    inner_ratio=0.5,  # Thick shell for housing magnets
)
print(f"Outer shell: {model.outer.vertices.shape[0]} vertices")
print(f"Inner shell: {model.inner.vertices.shape[0]} vertices")
```

### 3. Alternative A: Allowing Bosses with Automatic Minimization (`allow_bosses=True`)
By default, `allow_bosses=True` allows the software to build structural cylindrical "towers" (bosses) around magnet voids on the inside of the cavity where the shell is too thin. Crucially, the algorithm **minimizes the number of bosses needed and minimizes the material added**:
- If the shell is thick enough at candidate locations, **zero bosses are created**, leaving those regions completely smooth.
- If some bosses are required to meet your requested magnet count and spacing, it selects positions that minimize the total boss count and pushes the voids outward to minimize how far the bosses protrude into the cavity.
```python
# Configure magnets allowing bosses when necessary (auto-minimizing boss count & material)
model.configure_magnets(
    diameter=5.0,                  # 5 mm disc magnet
    height=2.0,                    # 2 mm height
    n_magnets=3,                   # 3 magnets
    position=0.0,                  # Start angle or search base
    horizontal_tolerance=0.15,     # 0.15 mm radial tolerance
    vertical_tolerance=0.10,       # 0.10 mm depth tolerance
    vertical_offset=0.20,          # 0.20 mm plastic ceiling
    min_thickness=1.5,             # 1.5 mm minimum plastic walls around magnet
    allow_bosses=True,             # Allow bosses if needed (minimizes boss count & protrusion)
)

# Generate the meshes (hollowing and magnet voids are calculated automatically)
top_boss, bottom_boss = model.generate_hemispheres(engine='manifold')
print(f"Top hemisphere is watertight: {top_boss.is_watertight}")
```

### 4. Alternative B: Strict No-Boss Placement (`allow_bosses=False`)
If you want to guarantee that the inner hollow cavity remains completely smooth with zero protruding bosses, set `allow_bosses=False`. The algorithm searches the equatorial plane to find optimal spots where the magnet pocket fits entirely inside the natural thickness of the displaced shell wall, raising an error if not enough zero-boss locations exist.
```python
# Reconfigure magnets to sit strictly inside the natural wall thickness with zero bosses
model.configure_magnets(
    diameter=5.0,
    height=2.0,
    n_magnets=3,
    min_magnets=2,                 # Raise error if fewer than 2 spots fit
    min_angular_spacing=60.0,      # Keep magnets at least 60 degrees apart
    step_degrees=2.0,              # Search angular step resolution
    horizontal_tolerance=0.15,
    vertical_tolerance=0.10,
    vertical_offset=0.20,
    min_thickness=1.5,
    allow_bosses=False,            # Strictly no support bosses
)

top_noboss, bottom_noboss = model.generate_hemispheres(engine='manifold')
```

---

## 🔬 Calibration: Print a Test Piece First!

Do not print a full 8-hour globe to test if your magnet settings are correct. Instead, generate and print a small **10-minute calibration test piece** containing a single magnet pocket.

```python
os.makedirs('../outputs', exist_ok=True)
test_piece_path = "../outputs/magnet_test_piece.stl"

generate_magnet_test_piece(
    diameter=5.0,
    height=2.0,
    horizontal_tolerance=0.15,
    vertical_tolerance=0.10,
    vertical_offset=0.20,
    min_thickness=1.5,
    output_path=test_piece_path,
)
print(f"Saved calibration test piece to: {test_piece_path}")
```

### 📈 How to Tune Your Settings:
1. **Print the test cylinder** using the same layer height and settings you plan to use for your globe.
2. **Press fit a magnet** into the pocket.
3. **Analyze the fit**:
   - *Too loose* (magnet drops out when shaken): Decrease the `horizontal_tolerance` or `vertical_tolerance`.
   - *Too tight* (cannot press magnet in, or it warps the plastic): Increase the `horizontal_tolerance`.
4. **Lock in the values**: Once the magnet pushes in snugly and stays in place, use those exact tolerances in your `configure_magnets()` call.

> [!TIP]
> When assembling the printed hemispheres, double-check the polarities of your magnets before gluing them in! It is extremely frustrating to glue a magnet in backward, preventing the hemispheres from closing.

import numpy as np
import pytest
from globe3d.mesh import (
    generate_sphere_points_fibonacci,
    generate_sphere_points_icosahedron,
    resize_globe,
    hollow_mesh,
    create_inner_mesh,
    compute_scale_factor,
    project_vertices_to_sphere,
    split_mesh_hemispheres,
    create_hollow_hemispheres
)
import trimesh

def test_generate_sphere_points_fibonacci():
    n_points = 100
    radius = 2.0
    vertices, faces = generate_sphere_points_fibonacci(n_points, radius)
    
    assert vertices.shape == (n_points, 3)
    assert faces.shape[1] == 3
    
    # Check if points are on the sphere
    radii = np.linalg.norm(vertices, axis=1)
    assert np.allclose(radii, radius)

def test_generate_sphere_points_icosahedron():
    subdivisions = 1
    radius = 1.0
    vertices, faces = generate_sphere_points_icosahedron(subdivisions, radius)
    
    # Icosahedron has 12 vertices, subdivision adds more
    assert vertices.shape[0] > 12
    assert faces.shape[1] == 3
    
    # Check if points are on the sphere
    radii = np.linalg.norm(vertices, axis=1)
    assert np.allclose(radii, radius)

def test_resize_globe():
    vertices = np.array([[1.0, 0.0, 0.0], [0.0, 1.0, 0.0]])
    scale = 2.0
    resized = resize_globe(vertices, scale)
    
    expected = np.array([[2.0, 0.0, 0.0], [0.0, 2.0, 0.0]])
    assert np.allclose(resized, expected)

def test_compute_scale_factor():
    vertices = np.array([[10.0, 0.0, 0.0], [0.0, 5.0, 0.0]])
    desired_cube_size = 10.0
    # Max val is 10.0. We want scaled max to be 5.0. So scale factor should be 0.5.
    scale_factor = compute_scale_factor(vertices, desired_cube_size)
    assert scale_factor == 0.5

def test_project_vertices_to_sphere():
    vertices = np.array([[2.0, 0.0, 0.0], [0.0, 0.5, 0.0]])
    radius = 1.0
    projected = project_vertices_to_sphere(vertices, radius)
    
    radii = np.linalg.norm(projected, axis=1)
    assert np.allclose(radii, radius)

def test_create_inner_mesh():
    # Create a simple mesh (tetrahedron)
    vertices = np.array([
        [0, 0, 0],
        [1, 0, 0],
        [0, 1, 0],
        [0, 0, 1]
    ], dtype=float)
    faces = np.array([
        [0, 2, 1],
        [0, 1, 3],
        [0, 3, 2],
        [1, 2, 3]
    ])
    
    thickness = 0.1
    inner_mesh = create_inner_mesh(vertices, faces, thickness)
    
    # Inner mesh should be smaller
    assert inner_mesh.vertices.shape == vertices.shape
    assert inner_mesh.faces.shape == faces.shape
    
    # Check bounding box is smaller
    assert np.all(inner_mesh.bounds[1] - inner_mesh.bounds[0] < 1.0)

def test_split_mesh_hemispheres():
    # Create a simple sphere
    mesh = trimesh.creation.icosphere(radius=1.0)
    
    # Split it
    top, bottom = split_mesh_hemispheres(mesh)
    
    assert top is not None
    assert bottom is not None
    
    # Check if they are watertight (capped)
    assert top.is_watertight
    assert bottom.is_watertight
    
    # Check bounds roughly
    # Top should have z >= 0 (approx)
    assert top.bounds[0][2] >= -0.01
    # Bottom should have z <= 0 (approx)
    assert bottom.bounds[1][2] <= 0.01


def test_fibonacci_normals_outward():
    """Verify ConvexHull faces are fixed to have outward-facing normals."""
    n_points = 500
    radius = 10.0
    vertices, faces = generate_sphere_points_fibonacci(n_points, radius)

    mesh = trimesh.Trimesh(vertices=vertices, faces=faces)
    # Volume must be positive (outward normals).
    assert mesh.volume > 0
    # Volume should be close to 4/3 * pi * r^3.
    expected_volume = (4 / 3) * np.pi * radius ** 3
    assert abs(mesh.volume - expected_volume) / expected_volume < 0.05


def test_icosahedron_normals_outward():
    """Verify icosahedron faces have outward-facing normals."""
    subdivisions = 2
    radius = 5.0
    vertices, faces = generate_sphere_points_icosahedron(subdivisions, radius)

    mesh = trimesh.Trimesh(vertices=vertices, faces=faces)
    assert mesh.volume > 0
    expected_volume = (4 / 3) * np.pi * radius ** 3
    assert abs(mesh.volume - expected_volume) / expected_volume < 0.05


def test_create_hollow_hemispheres():
    """End-to-end test: split-then-boolean-subtract produces correct hollow hemispheres."""
    outer_radius = 40.0
    inner_radius = 32.0
    ov, of = generate_sphere_points_fibonacci(5000, outer_radius)
    iv, if_ = generate_sphere_points_fibonacci(1000, inner_radius)

    top, bottom = create_hollow_hemispheres(
        ov, of, iv, if_, engine='manifold'
    )

    assert top is not None, "Top hemisphere is None"
    assert bottom is not None, "Bottom hemisphere is None"

    # Both halves must be watertight.
    assert top.is_watertight, "Top hemisphere is not watertight"
    assert bottom.is_watertight, "Bottom hemisphere is not watertight"

    # Both halves must have positive volume.
    assert top.volume > 0, f"Top volume is {top.volume}"
    assert bottom.volume > 0, f"Bottom volume is {bottom.volume}"

    # Volume should be close to 2/3 * pi * (R^3 - r^3).
    expected_vol = (2 / 3) * np.pi * (outer_radius ** 3 - inner_radius ** 3)
    assert abs(top.volume - expected_vol) / expected_vol < 0.10
    assert abs(bottom.volume - expected_vol) / expected_vol < 0.10

    # Z-bounds: top should be above equator, bottom below.
    assert top.bounds[0][2] >= -0.01
    assert bottom.bounds[1][2] <= 0.01

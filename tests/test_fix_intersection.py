import numpy as np
import pytest
from globe3d.mesh import GlobeModel

def test_fix_intersection_value_error_not_hollow():
    """Verify that fix_intersection raises ValueError if model is not hollow."""
    model = GlobeModel(hollow=False)
    with pytest.raises(ValueError, match="model is not hollow"):
        model.fix_intersection(min_thickness=1.2)

def test_fix_intersection_value_error_invalid_mode():
    """Verify that fix_intersection raises ValueError for an invalid mode."""
    model = GlobeModel(hollow=True)
    with pytest.raises(ValueError, match="mode must be one of"):
        model.fix_intersection(min_thickness=1.2, mode="invalid")

def test_fix_intersection_inner_mode():
    """Verify that mode='inner' displaces inner vertices inward only."""
    # Create a simple 10-point hollow globe model
    model = GlobeModel(method="fibonacci", n_points=10, radius=10.0, hollow=True, inner_ratio=0.8, inner_n_points=10)
    
    # Intentionally violate the thickness constraint by pushing an inner vertex outward
    # Let's verify coords are center-based. center is (0,0,0) by default.
    r_outer_start = np.linalg.norm(model.outer_vertices, axis=1)
    r_inner_start = np.linalg.norm(model.inner_vertices, axis=1)
    
    # Outer radius is 10.0, inner is 8.0. Normal thickness is 2.0 mm.
    # Let's push one inner vertex to radius 9.5. This leaves a thickness of 0.5 mm.
    # If min_thickness is 1.2, this is a violation of 0.7 mm.
    model.inner_vertices[0] = model.inner_vertices[0] * (9.5 / r_inner_start[0])
    
    model.fix_intersection(min_thickness=1.2, mode="inner")
    
    r_outer_after = np.linalg.norm(model.outer_vertices, axis=1)
    r_inner_after = np.linalg.norm(model.inner_vertices, axis=1)
    
    # Outer vertices should not be modified
    assert np.allclose(r_outer_start, r_outer_after)
    # The violated inner vertex should be pushed inward to radius 10.0 - 1.2 = 8.8 mm
    assert np.isclose(r_inner_after[0], 8.8)
    # The rest of inner vertices should remain around 8.0
    assert np.all(r_inner_after[1:] >= 8.0 - 1e-7)
    
    # Check recipe is recorded
    assert any(s["type"] == "fix_intersection" and s["mode"] == "inner" for s in model.recipe)
    assert any(s["type"] == "fix_intersection" and s["mode"] == "inner" for s in model._inner_recipe)

def test_fix_intersection_outer_mode():
    """Verify that mode='outer' displaces outer vertices outward only."""
    model = GlobeModel(method="fibonacci", n_points=10, radius=10.0, hollow=True, inner_ratio=0.8, inner_n_points=10)
    
    r_outer_start = np.linalg.norm(model.outer_vertices, axis=1)
    r_inner_start = np.linalg.norm(model.inner_vertices, axis=1)
    
    # Violate thickness constraint: pull an outer vertex inward to radius 8.5 (thickness 0.5 mm)
    model.outer_vertices[0] = model.outer_vertices[0] * (8.5 / r_outer_start[0])
    
    model.fix_intersection(min_thickness=1.2, mode="outer")
    
    r_outer_after = np.linalg.norm(model.outer_vertices, axis=1)
    r_inner_after = np.linalg.norm(model.inner_vertices, axis=1)
    
    # Inner vertices should not be modified
    assert np.allclose(r_inner_start, r_inner_after)
    # The violated outer vertex should be pushed outward to radius 8.0 + 1.2 = 9.2 mm
    assert np.isclose(r_outer_after[0], 9.2)
    
    # Check recipe
    assert any(s["type"] == "fix_intersection" and s["mode"] == "outer" for s in model.recipe)

def test_fix_intersection_both_mode():
    """Verify that mode='both' displaces both outer and inner vertices symmetrically."""
    model = GlobeModel(method="fibonacci", n_points=10, radius=10.0, hollow=True, inner_ratio=0.8, inner_n_points=10)
    
    r_outer_start = np.linalg.norm(model.outer_vertices, axis=1)
    r_inner_start = np.linalg.norm(model.inner_vertices, axis=1)
    
    # Violate thickness constraint: push inner vertex to 9.5 (thickness 0.5 mm)
    # Total violation = 1.2 - 0.5 = 0.7 mm.
    # In both mode, inner should go inward by 0.35 mm (to 9.15 mm), and outer outward by 0.35 mm (to 10.35 mm)
    model.inner_vertices[0] = model.inner_vertices[0] * (9.5 / r_inner_start[0])
    
    model.fix_intersection(min_thickness=1.2, mode="both")
    
    r_outer_after = np.linalg.norm(model.outer_vertices, axis=1)
    r_inner_after = np.linalg.norm(model.inner_vertices, axis=1)
    
    assert np.isclose(r_inner_after[0], 9.15)
    assert np.isclose(r_outer_after[0], 10.35)
    assert np.isclose(r_outer_after[0] - r_inner_after[0], 1.2)

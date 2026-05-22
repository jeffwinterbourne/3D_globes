import numpy as np
from scipy.spatial import ConvexHull
import trimesh


def fix_face_chirality(vertices, faces, center=(0.0, 0.0, 0.0)):
    """Ensures that each triangular face of the mesh points outward from a given center.

    Compares the computed face normal (via cross product) with the vector from
    the center to the face centroid. If the face normal points inward (dot product
    is negative), the winding order of the face is corrected by swapping the second
    and third vertex indices.

    Args:
        vertices (numpy.ndarray): Array of shape (n_points, 3) representing vertex coordinates.
        faces (numpy.ndarray): Array of shape (n_faces, 3) containing indices of vertices.
        center (array-like, optional): Center point of the mesh. Defaults to (0.0, 0.0, 0.0).

    Returns:
        numpy.ndarray: Array of shape (n_faces, 3) containing faces with corrected winding order.
    """
    vertices = np.asarray(vertices, dtype=np.float64)
    faces = np.asarray(faces, dtype=np.int32)
    center = np.asarray(center, dtype=np.float64)

    v0 = vertices[faces[:, 0]]
    v1 = vertices[faces[:, 1]]
    v2 = vertices[faces[:, 2]]

    normals = np.cross(v1 - v0, v2 - v0)
    centroids = (v0 + v1 + v2) / 3.0
    vecs = centroids - center

    dots = np.sum(normals * vecs, axis=1)

    corrected_faces = faces.copy()
    flip_mask = dots < 0.0
    corrected_faces[flip_mask, 1] = faces[flip_mask, 2]
    corrected_faces[flip_mask, 2] = faces[flip_mask, 1]

    return corrected_faces


def generate_sphere_points_fibonacci(n_points, radius=1.0, center=(0.0, 0.0, 0.0)):
    """Generates sphere vertices and faces using a Fibonacci lattice.

    Yields a highly uniform density of points over the sphere surface. Face connectivity
    is computed via a ConvexHull triangulation, and winding orders are corrected to
    point outward.

    Args:
        n_points (int): The number of points to generate.
        radius (float, optional): The radius of the sphere. Defaults to 1.0.
        center (array-like, optional): The center coordinates of the sphere. Defaults to (0.0, 0.0, 0.0).

    Returns:
        tuple: A tuple containing:
            - vertices (numpy.ndarray): Array of shape (n_points, 3) representing coordinates.
            - faces (numpy.ndarray): Array of shape (n_faces, 3) representing face indices.
    """
    center = np.array(center, dtype=np.float64)
    indices = np.arange(0, n_points, dtype=np.float64) + 0.5
    phi = np.arccos(1 - 2 * indices / n_points)
    golden_angle = np.pi * (3 - np.sqrt(5))
    theta = golden_angle * indices

    x = np.cos(theta) * np.sin(phi)
    y = np.sin(theta) * np.sin(phi)
    z = np.cos(phi)
    vertices = np.vstack((x, y, z)).T * radius + center

    hull = ConvexHull(vertices)
    faces = hull.simplices

    faces = fix_face_chirality(vertices, faces, center)

    return vertices, faces


def create_icosahedron(radius=1.0, center=(0.0, 0.0, 0.0)):
    """Creates the vertices and faces of an icosahedron inscribed in a sphere.

    Args:
        radius (float, optional): The radius of the enclosing sphere. Defaults to 1.0.
        center (array-like, optional): The center coordinates of the icosahedron. Defaults to (0.0, 0.0, 0.0).

    Returns:
        tuple: A tuple containing:
            - vertices (numpy.ndarray): Array of shape (12, 3) representing coordinates.
            - faces (numpy.ndarray): Array of shape (20, 3) representing face indices.
    """
    center = np.array(center, dtype=np.float64)
    phi_ratio = (1 + np.sqrt(5)) / 2

    vertices = [
        (-1,  phi_ratio, 0), (1,  phi_ratio, 0),
        (-1, -phi_ratio, 0), (1, -phi_ratio, 0),
        (0, -1,  phi_ratio), (0,  1,  phi_ratio),
        (0, -1, -phi_ratio), (0,  1, -phi_ratio),
        (phi_ratio, 0, -1), (phi_ratio, 0,  1),
        (-phi_ratio, 0, -1), (-phi_ratio, 0,  1)
    ]
    vertices = np.array(vertices, dtype=np.float64)
    vertices = vertices / np.linalg.norm(vertices, axis=1, keepdims=True) * radius
    vertices += center

    faces = np.array([
        [0, 11, 5],
        [0, 5, 1],
        [0, 1, 7],
        [0, 7, 10],
        [0, 10, 11],
        [1, 5, 9],
        [5, 11, 4],
        [11, 10, 2],
        [10, 7, 6],
        [7, 1, 8],
        [3, 9, 4],
        [3, 4, 2],
        [3, 2, 6],
        [3, 6, 8],
        [3, 8, 9],
        [4, 9, 5],
        [2, 4, 11],
        [6, 2, 10],
        [8, 6, 7],
        [9, 8, 1]
    ], dtype=np.int32)
    return vertices, faces


def midpoint(v1, v2):
    """Computes the midpoint between two vertices.

    Args:
        v1 (numpy.ndarray): Coordinates of the first vertex.
        v2 (numpy.ndarray): Coordinates of the second vertex.

    Returns:
        numpy.ndarray: The midpoint coordinates.
    """
    return (v1 + v2) / 2.0


def subdivide_icosahedron(vertices, faces, radius=1.0, center=(0.0, 0.0, 0.0)):
    """Subdivides each triangular face of a mesh into four smaller triangles.

    Projects the newly created midpoints back onto the sphere of the specified radius.
    Uses vectorized operations for efficiency.

    Args:
        vertices (numpy.ndarray): Array of shape (V, 3) representing coordinates.
        faces (numpy.ndarray): Array of shape (F, 3) representing face indices.
        radius (float, optional): Sphere radius to project points onto. Defaults to 1.0.
        center (array-like, optional): Center coordinates of the sphere. Defaults to (0.0, 0.0, 0.0).

    Returns:
        tuple: A tuple containing:
            - new_vertices (numpy.ndarray): Array of shape (V_new, 3) with subdivided coordinates.
            - new_faces (numpy.ndarray): Array of shape (F_new, 3) with subdivided face indices.
    """
    center = np.asarray(center, dtype=np.float64)
    V = vertices.shape[0]
    F = faces.shape[0]

    edges = np.vstack([
        faces[:, [0, 1]],
        faces[:, [1, 2]],
        faces[:, [2, 0]]
    ])

    edges_sorted = np.sort(edges, axis=1)
    unique_edges, inverse_indices = np.unique(edges_sorted, axis=0, return_inverse=True)

    midpoints = (vertices[unique_edges[:, 0]] + vertices[unique_edges[:, 1]]) / 2.0
    centered = midpoints - center
    norms = np.linalg.norm(centered, axis=1, keepdims=True)
    norms[norms == 0.0] = 1.0
    midpoints_projected = (centered / norms) * radius + center

    new_vertices = np.vstack([vertices, midpoints_projected])

    a = V + inverse_indices[0:F]
    b = V + inverse_indices[F:2*F]
    c = V + inverse_indices[2*F:3*F]

    f1 = np.column_stack([faces[:, 0], a, c])
    f2 = np.column_stack([faces[:, 1], b, a])
    f3 = np.column_stack([faces[:, 2], c, b])
    f4 = np.column_stack([a, b, c])

    new_faces = np.vstack([f1, f2, f3, f4]).astype(np.int32)
    return new_vertices, new_faces


def generate_sphere_points_icosahedron(subdivisions, radius=1.0, center=(0.0, 0.0, 0.0)):
    """Generates a sphere mesh by recursively subdividing an icosahedron.

    Args:
        subdivisions (int): Number of subdivision steps.
        radius (float, optional): Sphere radius. Defaults to 1.0.
        center (array-like, optional): Center of the sphere. Defaults to (0.0, 0.0, 0.0).

    Returns:
        tuple: A tuple containing:
            - vertices (numpy.ndarray): Array of shape (V, 3) representing coordinates.
            - faces (numpy.ndarray): Array of shape (F, 3) representing face indices.
    """
    vertices, faces = create_icosahedron(radius, center)
    for _ in range(subdivisions):
        vertices, faces = subdivide_icosahedron(vertices, faces, radius, center)

    faces = fix_face_chirality(vertices, faces, center)
    return vertices, faces


def project_vertices_to_sphere(vertices, radius=1.0, center=(0.0, 0.0, 0.0)):
    """Projects a set of vertices radially onto the surface of an ideal sphere.

    Args:
        vertices (numpy.ndarray): Array of shape (n_points, 3) representing coordinates.
        radius (float, optional): Target radius of the sphere. Defaults to 1.0.
        center (array-like, optional): Coordinates of the sphere center. Defaults to (0.0, 0.0, 0.0).

    Returns:
        numpy.ndarray: Projected vertex coordinates.
    """
    center = np.array(center, dtype=np.float64)
    centered = vertices - center
    norms = np.linalg.norm(centered, axis=1, keepdims=True)
    norms[norms == 0] = 1.0
    projected_vertices = (centered / norms) * radius + center
    return projected_vertices


def resize_globe(vertices, scale, origin=(0.0, 0.0, 0.0)):
    """Scales vertices relative to a specified origin.

    Args:
        vertices (numpy.ndarray): Array of shape (n_points, 3) representing coordinates.
        scale (float): Scale multiplier.
        origin (array-like, optional): Origin point for scaling. Defaults to (0.0, 0.0, 0.0).

    Returns:
        numpy.ndarray: Scaled vertex coordinates.
    """
    origin = np.array(origin, dtype=np.float64)
    return (vertices - origin) * scale + origin


def invert_chirality(faces):
    """Reverses the winding order of all triangular faces.

    Args:
        faces (numpy.ndarray): Array of shape (n_faces, 3) representing face indices.

    Returns:
        numpy.ndarray: Reassigned face indices with reversed winding.
    """
    return faces[:, [0, 2, 1]]


def combine_subtractive_globes(outer_vertices, outer_faces, inner_vertices, inner_faces,
                               outer_colors=None, inner_colors=None):
    """Combines two concentric globe meshes for a hollow/subtractive model.

    Inverts winding order (chirality) of the inner mesh so it acts subtractively.
    Optionally combines vertex color arrays if both are provided.

    Args:
        outer_vertices (numpy.ndarray): Outer mesh vertices.
        outer_faces (numpy.ndarray): Outer mesh faces.
        inner_vertices (numpy.ndarray): Inner mesh vertices.
        inner_faces (numpy.ndarray): Inner mesh faces.
        outer_colors (numpy.ndarray, optional): Outer mesh colors. Defaults to None.
        inner_colors (numpy.ndarray, optional): Inner mesh colors. Defaults to None.

    Returns:
        tuple: Combined vertices and faces (and colors if provided).
    """
    inner_faces_inverted = invert_chirality(inner_faces)
    offset = outer_vertices.shape[0]
    inner_faces_inverted = inner_faces_inverted + offset

    combined_vertices = np.vstack([outer_vertices, inner_vertices])
    combined_faces = np.vstack([outer_faces, inner_faces_inverted])

    if (outer_colors is not None) and (inner_colors is not None):
        combined_colors = np.vstack([outer_colors, inner_colors])
        return combined_vertices, combined_faces, combined_colors
    else:
        return combined_vertices, combined_faces


def compute_scale_factor(vertices, desired_cube_size):
    """Computes scale factor to fit vertices within a bounding cube centered at origin.

    Args:
        vertices (numpy.ndarray): Array of shape (N, 3) representing coordinates.
        desired_cube_size (float): The desired side length of the bounding cube.

    Returns:
        float: Scale factor.
    """
    max_val = np.max(np.abs(vertices))
    if max_val == 0:
        return 1.0
    return (desired_cube_size / 2.0) / max_val


def hollow_mesh(outer_vertices, outer_faces, inner_vertices=None, inner_faces=None,
                output_path=None, thickness=1.0, **kwargs):
    """Hollows a 3D mesh by performing a boolean difference with an inner mesh.

    Args:
        outer_vertices (numpy.ndarray): Outer mesh vertices.
        outer_faces (numpy.ndarray): Outer mesh faces.
        inner_vertices (numpy.ndarray, optional): Inner mesh vertices. If None, generated automatically.
        inner_faces (numpy.ndarray, optional): Inner mesh faces. If None, generated automatically.
        output_path (str, optional): File path to export the resulting hollowed STL. Defaults to None.
        thickness (float, optional): Shell thickness (used if inner mesh not provided). Defaults to 1.0.
        **kwargs: Extra keyword arguments passed to `trimesh.boolean.difference`.

    Returns:
        trimesh.Trimesh or None: The hollowed mesh, or None if boolean operation fails.
    """
    outer_mesh = trimesh.Trimesh(vertices=outer_vertices, faces=outer_faces)

    if inner_vertices is None or inner_faces is None:
        inner_mesh = create_inner_mesh(outer_vertices, outer_faces, thickness=thickness)
    else:
        inner_mesh = trimesh.Trimesh(vertices=inner_vertices, faces=inner_faces)

    if not outer_mesh.is_watertight:
        print("Warning: Outer mesh is not watertight. This may cause issues with boolean operations.")
    if not inner_mesh.is_watertight:
        print("Warning: Inner mesh is not watertight. This may cause issues with boolean operations.")

    try:
        hollowed_mesh = trimesh.boolean.difference(outer_mesh, inner_mesh, **kwargs)
    except Exception as e:
        if "object is not iterable" in str(e):
            print("Error: Boolean operation failed (Trimesh object is not iterable). Check the mesh geometry.")
            return None
        else:
            print(f"Error performing boolean difference: {e}")
            return None

    if hollowed_mesh is None:
        print("Error: Boolean difference returned None.")
        return None

    if not hollowed_mesh.is_watertight:
        print("Warning: Resulting mesh is not watertight. Attempting to repair...")
        hollowed_mesh = trimesh.repair.fix_fill(hollowed_mesh)
        if not hollowed_mesh.is_watertight:
            print("Error: Mesh repair failed. The mesh is still not watertight.")

    if output_path:
        try:
            hollowed_mesh.export(output_path)
            print(f"Hollowed mesh saved to {output_path}")
        except Exception as e:
            print(f"Error saving hollowed mesh: {e}")
            return None
    return hollowed_mesh


def create_inner_mesh(outer_vertices, outer_faces, thickness):
    """Generates an inner mesh by scaling down the outer mesh relative to its bounds center.

    Args:
        outer_vertices (numpy.ndarray): Outer mesh vertices.
        outer_faces (numpy.ndarray): Outer mesh faces.
        thickness (float): Target shell thickness.

    Returns:
        trimesh.Trimesh: The generated inner mesh.
    """
    outer_mesh = trimesh.Trimesh(vertices=outer_vertices, faces=outer_faces)
    bounds = outer_mesh.bounds
    center = (bounds[0] + bounds[1]) / 2.0

    scale_factor = 1 - thickness / outer_mesh.bounding_box.extents.max()
    if scale_factor <= 0:
        raise ValueError(f"Thickness {thickness} is too large for this mesh. Please use a smaller value.")

    inner_mesh = outer_mesh.copy()
    inner_mesh.apply_scale(scale_factor)
    inner_mesh.apply_translation((center - inner_mesh.centroid))
    return inner_mesh


def split_mesh_hemispheres(mesh, normal=(0, 0, 1), origin=(0, 0, 0)):
    """Splits a mesh into two halves along a plane.

    Args:
        mesh (trimesh.Trimesh): The mesh to split.
        normal (array-like, optional): Normal vector of the cutting plane. Defaults to (0, 0, 1).
        origin (array-like, optional): Point on the cutting plane. Defaults to (0, 0, 0).

    Returns:
        tuple: (top_mesh, bottom_mesh) halves as trimesh.Trimesh, or (None, None) if slice fails.
    """
    try:
        top_half = mesh.slice_plane(plane_origin=origin, plane_normal=normal, cap=True)
        bottom_half = mesh.slice_plane(plane_origin=origin, plane_normal=[-n for n in normal], cap=True)
        return top_half, bottom_half
    except Exception as e:
        print(f"Error splitting mesh: {e}")
        return None, None


def create_hollow_hemispheres(
    outer_vertices, outer_faces,
    inner_vertices, inner_faces,
    plane_normal=(0, 0, 1),
    plane_origin=(0, 0, 0),
    engine=None,
    magnet_params=None,
):
    """Creates two hollow hemispheres for 3D printing, optionally with magnet voids.

    Splits the outer mesh along the specified cutting plane, subtracts the inner mesh
    from each half, and optionally places magnet voids and bosses.

    Args:
        outer_vertices (numpy.ndarray): Outer shell vertices.
        outer_faces (numpy.ndarray): Outer shell faces.
        inner_vertices (numpy.ndarray): Inner shell vertices (normally smooth).
        inner_faces (numpy.ndarray): Inner shell faces.
        plane_normal (array-like, optional): Cutting plane normal. Defaults to (0, 0, 1).
        plane_origin (array-like, optional): Cutting plane origin. Defaults to (0, 0, 0).
        engine (str, optional): Boolean engine for trimesh ('manifold' or 'blender').
        magnet_params (dict, optional): Magnet insertion parameters. Defaults to None.

    Returns:
        tuple: (top_half, bottom_half) as trimesh.Trimesh objects, or (None, None) if failing.
    """
    normal = np.array(plane_normal, dtype=np.float64)
    origin = np.array(plane_origin, dtype=np.float64)

    outer_mesh = trimesh.Trimesh(vertices=outer_vertices, faces=outer_faces)
    outer_mesh.fix_normals()
    inner_mesh = trimesh.Trimesh(vertices=inner_vertices, faces=inner_faces)
    inner_mesh.fix_normals()

    try:
        top_outer = outer_mesh.slice_plane(
            plane_origin=origin, plane_normal=normal, cap=True
        )
        bottom_outer = outer_mesh.slice_plane(
            plane_origin=origin, plane_normal=-normal, cap=True
        )
    except Exception as e:
        print(f"Error splitting outer mesh: {e}")
        return None, None

    if top_outer is None or bottom_outer is None:
        print("Error: slice_plane returned None.")
        return None, None

    bool_kwargs = {}
    if engine is not None:
        bool_kwargs['engine'] = engine

    try:
        top_hollow = trimesh.boolean.difference(
            [top_outer, inner_mesh], **bool_kwargs
        )
    except Exception as e:
        print(f"Error performing boolean subtraction on top hemisphere: {e}")
        return None, None

    try:
        bottom_hollow = trimesh.boolean.difference(
            [bottom_outer, inner_mesh], **bool_kwargs
        )
    except Exception as e:
        print(f"Error performing boolean subtraction on bottom hemisphere: {e}")
        return None, None

    if magnet_params is not None:
        diameter = magnet_params.get('magnet_diameter', magnet_params.get('diameter', 5.0))
        height = magnet_params.get('magnet_height', magnet_params.get('height', 2.0))
        h_tol = magnet_params.get('h_tol', magnet_params.get('horizontal_tolerance', 0.15))
        v_tol = magnet_params.get('v_tol', magnet_params.get('vertical_tolerance', 0.10))
        v_offset = magnet_params.get('v_offset', magnet_params.get('vertical_offset', 0.20))
        min_thick = magnet_params.get('min_thick', magnet_params.get('min_thickness', 1.5))
        n_magnets = magnet_params.get('n_magnets', 3)
        start_lon = magnet_params.get('start_lon', magnet_params.get('position', 0.0))

        add_bosses = magnet_params.get('add_bosses', magnet_params.get('add_material', True))
        min_magnets = magnet_params.get('min_magnets', 2)
        min_angular_spacing = magnet_params.get('min_angular_spacing', 60.0)
        step_degrees = magnet_params.get('step_degrees', 2)

        from globe3d.magnets import insert_magnets_into_hemispheres
        try:
            top_hollow, bottom_hollow = insert_magnets_into_hemispheres(
                top_mesh=top_hollow,
                bottom_mesh=bottom_hollow,
                outer_vertices=outer_mesh,
                outer_faces=None,
                diameter=diameter,
                height=height,
                n_magnets=n_magnets,
                position=start_lon,
                horizontal_tolerance=h_tol,
                vertical_tolerance=v_tol,
                vertical_offset=v_offset,
                min_thickness=min_thick,
                engine=engine,
                add_bosses=add_bosses,
                min_magnets=min_magnets,
                min_angular_spacing=min_angular_spacing,
                step_degrees=step_degrees,
                inner_vertices=inner_mesh,
                inner_faces=None,
            )
        except Exception as e:
            print(f"Error inserting magnets: {e}")
            return None, None

    return top_hollow, bottom_hollow

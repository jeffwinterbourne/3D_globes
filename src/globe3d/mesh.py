import numpy as np
from scipy.spatial import ConvexHull
import trimesh

def generate_sphere_points_fibonacci(n_points, radius=1.0, center=(0.0, 0.0, 0.0)):
    """
    Generates a set of vertices on a sphere using the Fibonacci lattice, 
    yielding a reasonable uniform density even for large numbers (e.g. 1e6).

    Parameters:
      n_points (int): Number of points to generate.
      radius (float): Sphere radius.
      center (tuple): Center coordinates (default (0,0,0)).

    Returns:
      vertices: (n_points x 3) numpy array of Cartesian coordinates.
      faces: Triangular faces computed via a convex hull (n_faces x 3 indices).
    """
    center = np.array(center, dtype=np.float64)
    # Using a common Fibonacci sphere formulation:
    indices = np.arange(0, n_points, dtype=np.float64) + 0.5
    phi = np.arccos(1 - 2 * indices / n_points)  # polar angle
    golden_angle = np.pi * (3 - np.sqrt(5))
    theta = golden_angle * indices               # azimuthal angle

    x = np.cos(theta) * np.sin(phi)
    y = np.sin(theta) * np.sin(phi)
    z = np.cos(phi)
    vertices = np.vstack((x, y, z)).T * radius + center

    # Triangulate via the convex hull so we get faces for STL export.
    hull = ConvexHull(vertices)
    faces = hull.simplices
    return vertices, faces


def create_icosahedron(radius=1.0, center=(0.0, 0.0, 0.0)):
    """
    Creates the vertices and faces of an icosahedron inscribed in a sphere.

    Returns:
      vertices: (12 x 3) numpy array.
      faces: (20 x 3) numpy array (indices into vertices).
    """
    center = np.array(center, dtype=np.float64)
    phi_ratio = (1 + np.sqrt(5)) / 2  # golden ratio

    vertices = [
        (-1,  phi_ratio, 0), (1,  phi_ratio, 0),
        (-1, -phi_ratio, 0), (1, -phi_ratio, 0),
        (0, -1,  phi_ratio), (0,  1,  phi_ratio),
        (0, -1, -phi_ratio), (0,  1, -phi_ratio),
        (phi_ratio, 0, -1), (phi_ratio, 0,  1),
        (-phi_ratio, 0, -1), (-phi_ratio, 0,  1)
    ]
    vertices = np.array(vertices, dtype=np.float64)
    # Normalize and scale vertices to lie on the sphere
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
    """
    Computes the midpoint between two vertices.
    """
    return (v1 + v2) / 2.0


def subdivide_icosahedron(vertices, faces, radius=1.0, center=(0.0, 0.0, 0.0)):
    """
    Subdivides each triangular face into four smaller triangles, projecting new vertices
    back onto the sphere. Uses caching to avoid duplicating midpoint vertices.

    Parameters:
      vertices: current list (numpy array) of vertices.
      faces: current list (numpy array) of faces (indices).
      radius: sphere radius.
      center: sphere center.

    Returns:
      new_vertices: numpy array of vertices after subdivision.
      new_faces: numpy array of faces (indices).
    """
    center = np.array(center, dtype=np.float64)
    midpoint_cache = {}

    def get_midpoint(i, j):
        # Return the index of the midpoint vertex between vertices[i] and vertices[j]
        if (i, j) in midpoint_cache:
            return midpoint_cache[(i, j)]
        if (j, i) in midpoint_cache:
            return midpoint_cache[(j, i)]
        v_mid = midpoint(vertices[i], vertices[j])
        # Project onto sphere surface
        v_mid = v_mid - center
        v_mid = v_mid / np.linalg.norm(v_mid) * radius + center
        nonlocal vertices_list
        index = len(vertices_list)
        vertices_list.append(v_mid)
        midpoint_cache[(i, j)] = index
        return index

    vertices_list = list(vertices)
    new_faces = []
    for tri in faces:
        i0, i1, i2 = tri
        a = get_midpoint(i0, i1)
        b = get_midpoint(i1, i2)
        c = get_midpoint(i2, i0)
        new_faces.append([i0, a, c])
        new_faces.append([i1, b, a])
        new_faces.append([i2, c, b])
        new_faces.append([a, b, c])
    new_vertices = np.array(vertices_list, dtype=np.float64)
    new_faces = np.array(new_faces, dtype=np.int32)
    return new_vertices, new_faces
    
    
def generate_sphere_points_icosahedron(subdivisions, radius=1.0, center=(0.0, 0.0, 0.0)):
    """
    Generates a sphere mesh by subdividing an icosahedron.

    Parameters:
      subdivisions (int): Number of recursive subdivisions.
      radius (float): Sphere radius.
      center (tuple): Center of the sphere.

    Returns:
      vertices: (n_points x 3) numpy array.
      faces: (n_faces x 3) numpy array.
    """
    vertices, faces = create_icosahedron(radius, center)
    for _ in range(subdivisions):
        vertices, faces = subdivide_icosahedron(vertices, faces, radius, center)
    return vertices, faces


def project_vertices_to_sphere(vertices, radius=1.0, center=(0.0, 0.0, 0.0)):
    """
    Projects a set of vertices onto the surface of an ideal sphere.
    For each vertex, computes the vector from the center, normalizes it, and scales it to the desired radius.
    
    Parameters:
      vertices: (n_points x 3) numpy array of vertex coordinates.
      radius (float): The target radius of the sphere.
      center (tuple or array-like): Coordinates of the sphere's center.
      
    Returns:
      projected_vertices: numpy array of the same shape as vertices with each point lying exactly on the sphere.
    """
    center = np.array(center, dtype=np.float64)
    # Shift vertices to be relative to the center
    centered = vertices - center
    # Compute norms and avoid division by zero
    norms = np.linalg.norm(centered, axis=1, keepdims=True)
    norms[norms == 0] = 1.0
    # Normalize and scale to the desired radius, then shift back by the center
    projected_vertices = (centered / norms) * radius + center
    return projected_vertices


def resize_globe(vertices, scale, origin=(0.0, 0.0, 0.0)):
    """
    Resizes (scales) the globe by the provided scalar relative to the given origin.
    
    Parameters:
      vertices (numpy.ndarray): Array of shape (n_points, 3) representing the mesh vertices.
      scale (float): The scalar factor by which to resize the mesh.
      origin (tuple or array-like): The point about which scaling is performed. Default is (0,0,0).
    
    Returns:
      numpy.ndarray: New vertex array with each vertex scaled relative to the origin.
    """
    origin = np.array(origin, dtype=np.float64)
    return (vertices - origin) * scale + origin


def invert_chirality(faces):
    """
    Reverses the winding order for every triangle in the mesh.
    
    Parameters:
      faces (numpy.ndarray): Array of shape (n_faces, 3) of triangle indices.
    
    Returns:
      numpy.ndarray: A new array with the winding order of each triangle reversed.
    """
    return faces[:, [0, 2, 1]]


def combine_subtractive_globes(outer_vertices, outer_faces, inner_vertices, inner_faces,
                               outer_colors=None, inner_colors=None):
    """
    Combines two globe meshes such that the inner (subtracted) globe's faces have inverted
    chirality (making it 'subtractive' for creating hollow globes) and merges the vertices
    and triangles. Optionally, it also combines the vertex colors from both meshes.

    Parameters:
      outer_vertices (numpy.ndarray): Array of shape (n_points_outer, 3) for the outer globe.
      outer_faces (numpy.ndarray): Array of shape (n_faces_outer, 3) for the outer globe.
      inner_vertices (numpy.ndarray): Array of shape (n_points_inner, 3) for the inner globe.
      inner_faces (numpy.ndarray): Array of shape (n_faces_inner, 3) for the inner globe.
      outer_colors (numpy.ndarray, optional): Array of shape (n_points_outer, 3) containing colors 
                                              for the outer globe's vertices.
      inner_colors (numpy.ndarray, optional): Array of shape (n_points_inner, 3) containing colors 
                                              for the inner globe's vertices.
    
    Returns:
      If vertex colors are provided: a tuple (combined_vertices, combined_faces, combined_colors)
      Otherwise: a tuple (combined_vertices, combined_faces)
    
    Notes:
      - The inner globe's face winding order is inverted.
      - The indices in the inner_faces are offset by the number of outer vertices.
    """
    # Invert the triangle chirality for the inner globe.
    inner_faces_inverted = invert_chirality(inner_faces)
    
    # Offset indices in inner_faces_inverted by the number of outer vertices.
    offset = outer_vertices.shape[0]
    inner_faces_inverted = inner_faces_inverted + offset
    
    # Concatenate the vertices and faces.
    combined_vertices = np.vstack([outer_vertices, inner_vertices])
    combined_faces = np.vstack([outer_faces, inner_faces_inverted])
    
    if (outer_colors is not None) and (inner_colors is not None):
        # Concatenate the colors likewise.
        combined_colors = np.vstack([outer_colors, inner_colors])
        return combined_vertices, combined_faces, combined_colors
    else:
        return combined_vertices, combined_faces


def compute_scale_factor(vertices, desired_cube_size):
    """
    Computes a scale factor to fit the vertices inside a bounding cube centered at the origin.
    
    The idea is to scale the vertices so that the maximum absolute coordinate over x, y, or z 
    becomes desired_cube_size/2.
    
    Parameters:
      vertices (numpy.ndarray): Array of shape (n, 3) with the vertex coordinates.
      desired_cube_size (float): The target side length of the bounding cube.
    
    Returns:
      float: The scale factor. When multiplied with vertices, the result
             will have max(|x|, |y|, |z|) <= desired_cube_size/2.
    """
    # Find the maximum absolute value from all coordinates.
    max_val = np.max(np.abs(vertices))
    
    # Protect against degenerate case.
    if max_val == 0:
        return 1.0
    
    # The scale factor is set so that:
    #    scaled_max = max_val * scale_factor = desired_cube_size/2.
    scale_factor = (desired_cube_size / 2.0) / max_val
    return scale_factor


def hollow_mesh(outer_vertices, outer_faces, inner_vertices=None, inner_faces=None, output_path=None, thickness=1.0, **kwargs):
    """
    Hollows a 3D mesh by performing a boolean difference with a scaled-down version of itself.

    Args:
        outer_vertices (numpy.ndarray): (n_points x 3) array of outer mesh vertices.
        outer_faces (numpy.ndarray): (n_faces x 3) array of outer mesh face indices.
        inner_vertices (numpy.ndarray, optional): (n_points x 3) array of inner mesh vertices.
            If None, an inner mesh is created by scaling the outer mesh.
        inner_faces (numpy.ndarray, optional): (n_faces x 3) array of inner mesh face indices.
            If None, an inner mesh is created by scaling the outer mesh.
        output_path (str, optional): Path to save the hollowed STL file. If None, the mesh is not saved.
        thickness (float, optional): Thickness of the shell.  Ignored if inner_vertices and inner_faces are provided.
        **kwargs:  Additional keyword arguments passed to trimesh.boolean.difference.
    """
    # Create the outer mesh from vertices and faces
    outer_mesh = trimesh.Trimesh(vertices=outer_vertices, faces=outer_faces)

    if inner_vertices is None or inner_faces is None:
        # Create inner mesh by scaling
        inner_mesh = create_inner_mesh(outer_vertices, outer_faces, thickness=thickness)
    else:
        # Use the provided inner mesh data.
        inner_mesh = trimesh.Trimesh(vertices=inner_vertices, faces=inner_faces)

    # Check if the meshes are valid
    if not outer_mesh.is_watertight:
        print("Warning: Outer mesh is not watertight.  This may cause issues with boolean operations.")
    if not inner_mesh.is_watertight:
        print("Warning: Inner mesh is not watertight.  This may cause issues with boolean operations.")

    try:
        # Perform the boolean operation to create the hollowed mesh
        hollowed_mesh = trimesh.boolean.difference(outer_mesh, inner_mesh, **kwargs)
    except Exception as e:
        if "object is not iterable" in str(e):
            print("Error: 'Trimesh' object is not iterable.  This often means the boolean operation failed.")
            print("  Try checking the mesh for self-intersections or other errors.")
            print("  Returning None.")
            return None
        else:
            print(f"Error performing boolean difference: {e}")
            return

    if hollowed_mesh is None:
        print("Error: Boolean difference returned None.  Check your input meshes.")
        return

    # Check the result
    if not hollowed_mesh.is_watertight:
        print("Warning: Resulting mesh is not watertight.  This could cause problems.")

    # Attempt to fix the mesh
    if not hollowed_mesh.is_watertight:
        print("Attempting to repair mesh...")
        hollowed_mesh = trimesh.repair.fix_fill(hollowed_mesh)
        if not hollowed_mesh.is_watertight:
            print("Error: Mesh repair failed.  The mesh is still not watertight.")

    if output_path:
        try:
            # Save the hollowed mesh to a new STL file
            hollowed_mesh.export(output_path)
            print(f"Hollowed mesh saved to {output_path}")
        except Exception as e:
            print(f"Error saving hollowed mesh: {e}")
            return
    return hollowed_mesh # Return the trimesh object

def create_inner_mesh(outer_vertices, outer_faces, thickness):
    """
    Generates an inner mesh by scaling down the outer mesh.

    Args:
        outer_vertices (numpy.ndarray): (n_points x 3) array of outer mesh vertices.
        outer_faces (numpy.ndarray): (n_faces x 3) array of outer mesh face indices.
        thickness (float): Thickness of the shell.

    Returns:
        trimesh.Trimesh: The generated inner mesh.
    """
    outer_mesh = trimesh.Trimesh(vertices=outer_vertices, faces=outer_faces)

    # Get the bounding box of the mesh.
    bounds = outer_mesh.bounds
    # Calculate the center of the bounding box.
    center = (bounds[0] + bounds[1]) / 2.0

    # Scale the mesh down, relative to the center.
    scale_factor = 1 - thickness / outer_mesh.bounding_box.extents.max()
    if scale_factor <= 0:
        raise ValueError(f"Thickness {thickness} is too large for this mesh.  Please use a smaller value.")

    inner_mesh = outer_mesh.copy()
    inner_mesh.apply_scale(scale_factor)
    inner_mesh.apply_translation((center - inner_mesh.centroid))  # keep the inner mesh centered
    return inner_mesh


def split_mesh_hemispheres(mesh, normal=(0, 0, 1), origin=(0, 0, 0)):
    """
    Splits a mesh into two halves using a plane.

    Args:
        mesh (trimesh.Trimesh): The mesh to split.
        normal (tuple): Normal vector of the splitting plane (default: Z-axis).
        origin (tuple): Point on the splitting plane (default: origin).

    Returns:
        tuple: (top_mesh, bottom_mesh) where top_mesh is on the positive side of the normal.
               Returns (None, None) if splitting fails.
    """
    try:
        # slice_plane returns a new mesh that is capped by default in recent trimesh versions
        # We need to slice twice to get both halves
        
        # Top half (keep positive side)
        top_half = mesh.slice_plane(plane_origin=origin, plane_normal=normal, cap=True)
        
        # Bottom half (keep negative side -> normal is inverted)
        bottom_half = mesh.slice_plane(plane_origin=origin, plane_normal=[-n for n in normal], cap=True)
        
        return top_half, bottom_half
    except Exception as e:
        print(f"Error splitting mesh: {e}")
        return None, None

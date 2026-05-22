"""Mesh generation and manipulation module for the globe3d package.

This module provides the GlobeModel class representing the 3D globe geometry
and its creation recipe, along with helper functions for sphere generation,
chirality fixing, hollowing, and hemisphere splitting.
"""

import numpy as np
from scipy.spatial import ConvexHull
import trimesh
from globe3d.displacement import Displacer, Colourer, select_inward_facing, select_outward_facing, SELECTION_REGISTRY
from globe3d.magnets import MagnetSettings


class GlobeModel:
    """Contains the 3D geometry and recipe for building a 3D printable globe.

    Attributes:
        outer_vertices (numpy.ndarray): (N, 3) array of outer shell vertices in mm.
        outer_faces (numpy.ndarray): (F, 3) array of outer shell face indices.
        outer_colors (numpy.ndarray): (N, 3) array of RGB colors in range [0, 1].
        inner_vertices (numpy.ndarray): (N_inner, 3) array of inner shell vertices.
        inner_faces (numpy.ndarray): (F_inner, 3) array of inner shell face indices.
        inner_colors (numpy.ndarray): (N_inner, 3) array of inner RGB colors.
        magnet_settings (MagnetSettings): Configuration for magnet void insertion.
        recipe (list): List of dicts representing applied displacement and colouring steps.
    """

    def __init__(self, vertices: np.ndarray = None, faces: np.ndarray = None):
        """Initializes a GlobeModel.

        Args:
            vertices (numpy.ndarray, optional): Outer shell vertices. Defaults to None.
            faces (numpy.ndarray, optional): Outer shell face indices. Defaults to None.
        """
        self.outer_vertices = np.asarray(vertices, dtype=np.float64) if vertices is not None else None
        self.outer_faces = np.asarray(faces, dtype=np.int32) if faces is not None else None
        self.outer_colors = None

        self.inner_vertices = None
        self.inner_faces = None
        self.inner_colors = None

        self.magnet_settings = None
        self.recipe = []

    @classmethod
    def from_fibonacci(cls, n_points: int, radius: float = 1.0, center=(0.0, 0.0, 0.0)) -> "GlobeModel":
        """Generates a sphere GlobeModel using a Fibonacci lattice.

        Args:
            n_points (int): The number of points to generate.
            radius (float, optional): The radius of the sphere in mm. Defaults to 1.0.
            center (array-like, optional): Center of the sphere. Defaults to (0.0, 0.0, 0.0).

        Returns:
            GlobeModel: A GlobeModel instance with a Fibonacci sphere geometry.
        """
        v, f = generate_sphere_points_fibonacci(n_points, radius, center)
        return cls(v, f)

    @classmethod
    def from_icosahedron(cls, subdivisions: int, radius: float = 1.0, center=(0.0, 0.0, 0.0)) -> "GlobeModel":
        """Generates a sphere GlobeModel by recursively subdividing an icosahedron.

        Args:
            subdivisions (int): Number of subdivision steps.
            radius (float, optional): Sphere radius in mm. Defaults to 1.0.
            center (array-like, optional): Center of the sphere. Defaults to (0.0, 0.0, 0.0).

        Returns:
            GlobeModel: A GlobeModel instance with an icosahedron-derived sphere.
        """
        v, f = generate_sphere_points_icosahedron(subdivisions, radius, center)
        return cls(v, f)

    def displace(self, displacer: Displacer, scale: float = 1.0):
        """Displaces the model's outer vertices and records the step in its recipe.

        Args:
            displacer (Displacer): The displacement object to apply.
            scale (float, optional): Scaling multiplier for the displacement. Defaults to 1.0.

        Raises:
            ValueError: If outer geometry is not initialized.
        """
        if self.outer_vertices is None:
            raise ValueError("Cannot displace: outer geometry is not initialized.")
        self.outer_vertices = displacer(self.outer_vertices, scale=scale)
        self.recipe.append({
            "type": "displacement",
            "displacer": displacer,
            "scale": scale
        })

    def colour(self, colouring: Colourer, target: str = "outer", selection=None, selection_kwargs=None):
        """Assigns colors to a subset of the model's vertices and records the step in the recipe.

        Args:
            colouring (Colourer): The coloring object to apply.
            target (str, optional): Target to color ('outer' or 'inner'). Defaults to 'outer'.
            selection (str, callable, or array-like, optional): Vertex subset selection.
                Can be 'inward_facing', 'outward_facing', a custom callable, or a list of indices.
            selection_kwargs (dict, optional): Keyword arguments for the selection function.

        Raises:
            ValueError: If target is invalid or the target geometry is not initialized.
        """
        if target not in ("outer", "inner"):
            raise ValueError("target must be either 'outer' or 'inner'.")

        vertices = getattr(self, f"{target}_vertices")
        faces = getattr(self, f"{target}_faces")

        if vertices is None:
            raise ValueError(f"Cannot color: {target} geometry is not initialized.")

        if selection is None:
            selected_indices = np.arange(len(vertices))
        elif isinstance(selection, str):
            if selection not in SELECTION_REGISTRY:
                raise ValueError(
                    f"Selection function '{selection}' not found in registry. "
                    f"Available functions: {list(SELECTION_REGISTRY.keys())}"
                )
            select_func = SELECTION_REGISTRY[selection]
            selected_indices = select_func(vertices, faces, **(selection_kwargs or {}))
        elif callable(selection):
            selected_indices = selection(vertices, faces, **(selection_kwargs or {}))
        else:
            selected_indices = np.asarray(selection, dtype=np.int32)

        if len(selected_indices) > 0:
            current_colors = getattr(self, f"{target}_colors")
            if current_colors is None:
                current_colors = np.ones((len(vertices), 3), dtype=np.float64)

            new_colors = colouring(vertices[selected_indices])
            current_colors[selected_indices] = new_colors
            setattr(self, f"{target}_colors", current_colors)

        self.recipe.append({
            "type": "colouring",
            "colouring": colouring,
            "target": target,
            "selection": selection,
            "selection_kwargs": selection_kwargs
        })

    def create_inner_mesh(self, thickness: float):
        """Generates the inner mesh by scaling down the outer mesh relative to its bounds center.

        Args:
            thickness (float): Target shell thickness in mm.
        """
        if self.outer_vertices is None or self.outer_faces is None:
            raise ValueError("Outer mesh must be defined before generating the inner mesh.")
        inner_mesh = create_inner_mesh(self.outer_vertices, self.outer_faces, thickness=thickness)
        self.inner_vertices = inner_mesh.vertices
        self.inner_faces = inner_mesh.faces
        if self.outer_colors is not None:
            self.inner_colors = np.ones((len(self.inner_vertices), 3), dtype=np.float64)

    def to_trimesh(self, part: str = "outer") -> trimesh.Trimesh:
        """Generates a trimesh.Trimesh representation of the specified part.

        Args:
            part (str, optional): Part to generate ('outer', 'inner', or 'combined'). Defaults to 'outer'.

        Returns:
            trimesh.Trimesh: The requested mesh representation.
        """
        if part == "outer":
            if self.outer_vertices is None or self.outer_faces is None:
                raise ValueError("Outer geometry is not defined.")
            colors = self.outer_colors
            if colors is not None:
                vertex_colors = (colors * 255.0).astype(np.uint8)
                return trimesh.Trimesh(vertices=self.outer_vertices, faces=self.outer_faces, vertex_colors=vertex_colors)
            return trimesh.Trimesh(vertices=self.outer_vertices, faces=self.outer_faces)

        elif part == "inner":
            if self.inner_vertices is None or self.inner_faces is None:
                raise ValueError("Inner geometry is not defined.")
            colors = self.inner_colors
            if colors is not None:
                vertex_colors = (colors * 255.0).astype(np.uint8)
                return trimesh.Trimesh(vertices=self.inner_vertices, faces=self.inner_faces, vertex_colors=vertex_colors)
            return trimesh.Trimesh(vertices=self.inner_vertices, faces=self.inner_faces)

        elif part == "combined":
            if self.outer_vertices is None or self.inner_vertices is None:
                raise ValueError("Both outer and inner geometries must be defined for combined part.")
            res = combine_subtractive_globes(
                self.outer_vertices, self.outer_faces,
                self.inner_vertices, self.inner_faces,
                self.outer_colors, self.inner_colors
            )
            if len(res) == 3:
                combined_vertices, combined_faces, combined_colors = res
                vertex_colors = (combined_colors * 255.0).astype(np.uint8)
                return trimesh.Trimesh(vertices=combined_vertices, faces=combined_faces, vertex_colors=vertex_colors)
            else:
                combined_vertices, combined_faces = res
                return trimesh.Trimesh(vertices=combined_vertices, faces=combined_faces)

        else:
            raise ValueError("part must be 'outer', 'inner', or 'combined'.")

    def _apply_recipe_colors_to_mesh(self, mesh: trimesh.Trimesh):
        """Re-applies the colouring steps from the recipe to a post-processed mesh's vertices."""
        if not self.recipe:
            return

        # Initialize to solid white
        colors = np.ones((len(mesh.vertices), 3), dtype=np.float64)
        has_colored = False

        for step in self.recipe:
            if step["type"] == "colouring":
                has_colored = True
                colouring = step["colouring"]
                selection = step["selection"]
                selection_kwargs = step["selection_kwargs"] or {}

                if selection is None:
                    selected_indices = np.arange(len(mesh.vertices))
                elif isinstance(selection, str):
                    if selection not in SELECTION_REGISTRY:
                        continue
                    select_func = SELECTION_REGISTRY[selection]
                    selected_indices = select_func(mesh.vertices, mesh.faces, **selection_kwargs)
                elif callable(selection):
                    selected_indices = selection(mesh.vertices, mesh.faces, **selection_kwargs)
                else:
                    # Map indices roughly, but list of indices on original mesh might not align with new mesh.
                    # As a fallback, try to apply.
                    selected_indices = np.asarray(selection, dtype=np.int32)
                    selected_indices = selected_indices[selected_indices < len(mesh.vertices)]

                if len(selected_indices) > 0:
                    new_colors = colouring(mesh.vertices[selected_indices])
                    colors[selected_indices] = new_colors

        if has_colored:
            mesh.visual.vertex_colors = (colors * 255.0).astype(np.uint8)

    def generate_hemispheres(
        self,
        plane_normal=(0, 0, 1),
        plane_origin=(0, 0, 0),
        hollow: bool = True,
        thickness: float = 1.5,
        engine: str = None,
    ) -> tuple:
        """Cuts the globe model into top and bottom capped hemispheres, optionally hollowed with magnets.

        Args:
            plane_normal (array-like, optional): Cutting plane normal. Defaults to (0, 0, 1).
            plane_origin (array-like, optional): Cutting plane origin. Defaults to (0, 0, 0).
            hollow (bool, optional): If True, hollow the hemispheres. Defaults to True.
            thickness (float, optional): Shell thickness in mm. Defaults to 1.5.
            engine (str, optional): Boolean engine for trimesh. Defaults to None.

        Returns:
            tuple: (top_half, bottom_half) as trimesh.Trimesh objects.
        """
        if self.outer_vertices is None or self.outer_faces is None:
            raise ValueError("Outer geometry is not defined.")

        if hollow:
            if self.inner_vertices is None or self.inner_faces is None:
                self.create_inner_mesh(thickness)

            top_half, bottom_half = create_hollow_hemispheres(
                self.outer_vertices, self.outer_faces,
                self.inner_vertices, self.inner_faces,
                plane_normal=plane_normal,
                plane_origin=plane_origin,
                engine=engine,
                magnet_params=self.magnet_settings
            )
        else:
            outer_mesh = trimesh.Trimesh(vertices=self.outer_vertices, faces=self.outer_faces)
            outer_mesh.fix_normals()
            top_half, bottom_half = split_mesh_hemispheres(outer_mesh, normal=plane_normal, origin=plane_origin)

        # Apply coloring recipe to both halves
        if top_half is not None:
            self._apply_recipe_colors_to_mesh(top_half)
        if bottom_half is not None:
            self._apply_recipe_colors_to_mesh(bottom_half)

        return top_half, bottom_half

    def write_stl(self, filename: str, part: str = "outer"):
        """Exports the model geometry to a binary STL file.

        Args:
            filename (str): Path to export the STL.
            part (str, optional): Part to export ("outer", "inner", or "combined"). Defaults to "outer".
        """
        mesh = self.to_trimesh(part=part)
        from globe3d.io import write_stl_binary
        write_stl_binary(filename, mesh.vertices, mesh.faces)

    def write_obj(self, filename: str, part: str = "outer", center=(0.0, 0.0, 0.0), fix_normals=False):
        """Exports the model geometry with vertex colors to an OBJ file.

        Args:
            filename (str): Path to export the OBJ.
            part (str, optional): Part to export ("outer", "inner", or "combined"). Defaults to "outer".
            center (array-like, optional): Center point to offset the mesh. Defaults to (0.0, 0.0, 0.0).
            fix_normals (bool, optional): If True, corrects face normals winding order. Defaults to False.
        """
        mesh = self.to_trimesh(part=part)
        from globe3d.io import write_obj_with_vertex_colors

        if hasattr(mesh.visual, "vertex_colors") and mesh.visual.vertex_colors is not None:
            # trimesh colors are uint8 of shape (V, 4) or (V, 3)
            colors = mesh.visual.vertex_colors[:, :3].astype(np.float64) / 255.0
        else:
            colors = np.ones((len(mesh.vertices), 3), dtype=np.float64)

        write_obj_with_vertex_colors(filename, mesh.vertices, mesh.faces, colors, center=center, fix_normals=fix_normals)


def fix_face_chirality(vertices, faces, center=(0.0, 0.0, 0.0)):
    """Ensures that each triangular face of the mesh points outward from a given center.

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

    Args:
        n_points (int): The number of points to generate.
        radius (float, optional): The radius of the sphere. Defaults to 1.0.
        center (array-like, optional): The center coordinates of the sphere. Defaults to (0.0, 0.0, 0.0).

    Returns:
        tuple: (vertices, faces)
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
    """Creates the vertices and faces of an icosahedron inscribed in a sphere."""
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
    """Computes the midpoint between two vertices."""
    return (v1 + v2) / 2.0


def subdivide_icosahedron(vertices, faces, radius=1.0, center=(0.0, 0.0, 0.0)):
    """Subdivides each triangular face of a mesh into four smaller triangles."""
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
    """Generates a sphere mesh by recursively subdividing an icosahedron."""
    vertices, faces = create_icosahedron(radius, center)
    for _ in range(subdivisions):
        vertices, faces = subdivide_icosahedron(vertices, faces, radius, center)

    faces = fix_face_chirality(vertices, faces, center)
    return vertices, faces


def project_vertices_to_sphere(vertices, radius=1.0, center=(0.0, 0.0, 0.0)):
    """Projects a set of vertices radially onto the surface of an ideal sphere."""
    center = np.array(center, dtype=np.float64)
    centered = vertices - center
    norms = np.linalg.norm(centered, axis=1, keepdims=True)
    norms[norms == 0] = 1.0
    projected_vertices = (centered / norms) * radius + center
    return projected_vertices


def resize_globe(vertices, scale, origin=(0.0, 0.0, 0.0)):
    """Scales vertices relative to a specified origin."""
    origin = np.array(origin, dtype=np.float64)
    return (vertices - origin) * scale + origin


def invert_chirality(faces):
    """Reverses the winding order of all triangular faces."""
    return faces[:, [0, 2, 1]]


def combine_subtractive_globes(outer_vertices, outer_faces, inner_vertices, inner_faces,
                               outer_colors=None, inner_colors=None):
    """Combines two concentric globe meshes for a hollow/subtractive model."""
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
    """Computes scale factor to fit vertices within a bounding cube centered at origin."""
    max_val = np.max(np.abs(vertices))
    if max_val == 0:
        return 1.0
    return (desired_cube_size / 2.0) / max_val


def hollow_mesh(outer_vertices, outer_faces, inner_vertices=None, inner_faces=None,
                output_path=None, thickness=1.0, **kwargs):
    """Hollows a 3D mesh by performing a boolean difference with an inner mesh."""
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
    """Generates an inner mesh by scaling down the outer mesh relative to its bounds center."""
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
    """Splits a mesh into two halves along a plane."""
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
    """Creates two hollow hemispheres for 3D printing, optionally with magnet voids."""
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
        from globe3d.magnets import insert_magnets_into_hemispheres
        try:
            top_hollow, bottom_hollow = insert_magnets_into_hemispheres(
                top_mesh=top_hollow,
                bottom_mesh=bottom_hollow,
                outer_vertices=outer_mesh,
                outer_faces=None,
                engine=engine,
                inner_vertices=inner_mesh,
                inner_faces=None,
                settings=magnet_params,
            )
        except Exception as e:
            print(f"Error inserting magnets: {e}")
            return None, None

    return top_hollow, bottom_hollow

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


class _MeshProxy:
    """Lightweight proxy giving ``model.outer`` / ``model.inner`` a clean API.

    Users interact with ``model.outer.displace(...)`` and
    ``model.inner.displace(...)`` instead of directly mutating arrays.

    Attributes:
        _model (GlobeModel): Back-reference to the owning model.
        _target (str): ``'outer'`` or ``'inner'``.
    """

    def __init__(self, model: "GlobeModel", target: str):
        """Initializes a _MeshProxy.

        Args:
            model (GlobeModel): The owning model.
            target (str): ``'outer'`` or ``'inner'``.
        """
        object.__setattr__(self, '_model', model)
        object.__setattr__(self, '_target', target)

    # ----- read-only properties -------------------------------------------

    @property
    def vertices(self) -> np.ndarray:
        """(N, 3) vertex array (read-only view)."""
        return getattr(self._model, f"{self._target}_vertices")

    @property
    def faces(self) -> np.ndarray:
        """(F, 3) face-index array (read-only view)."""
        return getattr(self._model, f"{self._target}_faces")

    @property
    def colors(self) -> np.ndarray:
        """(N, 3) RGB color array (read-only view), or None."""
        return getattr(self._model, f"{self._target}_colors")

    # ----- mutating helpers -----------------------------------------------

    def displace(self, displacer: Displacer, scale: float = 1.0):
        """Displaces this mesh's vertices and records the step in the recipe.

        Args:
            displacer (Displacer): The displacement object to apply.
            scale (float, optional): Scaling multiplier. Defaults to 1.0.

        Raises:
            ValueError: If the geometry is not initialized.
        """
        verts = getattr(self._model, f"{self._target}_vertices")
        if verts is None:
            raise ValueError(f"Cannot displace: {self._target} geometry is not initialized.")
        new_verts = displacer(verts, scale=scale)
        setattr(self._model, f"{self._target}_vertices", new_verts)
        recipe = self._model.recipe if self._target == "outer" else self._model._inner_recipe
        recipe.append({
            "type": "displacement",
            "displacer": displacer,
            "scale": scale,
        })

    def displace_constant(self, amount: float, scale: float = 1.0):
        """Displaces this mesh's vertices by a constant radial amount.

        Args:
            amount (float): The constant displacement in mm.
            scale (float, optional): Scaling multiplier. Defaults to 1.0.

        Raises:
            ValueError: If the geometry is not initialized.
        """
        from globe3d.displacement import ConstantDisplacer
        displacer = ConstantDisplacer(amount)
        self.displace(displacer, scale=scale)

    def colour(self, colouring: Colourer, selection=None, selection_kwargs=None):
        """Assigns colors to a subset of this mesh's vertices and records the step.

        Args:
            colouring (Colourer): The coloring object to apply.
            selection (str, callable, or array-like, optional): Vertex subset.
                Can be ``'inward_facing'``, ``'outward_facing'``, a custom callable,
                or a list of indices.
            selection_kwargs (dict, optional): Keyword arguments for the selection function.

        Raises:
            ValueError: If the geometry is not initialized.
        """
        self._model.colour(colouring, target=self._target,
                           selection=selection, selection_kwargs=selection_kwargs)


class GlobeModel:
    """Central object representing a 3D printable globe.

    A ``GlobeModel`` encapsulates the outer and (optionally) inner shell
    geometry, vertex colors, displacement/colouring recipes, and magnet
    settings.  It exposes high-level methods so that the user never needs
    to manipulate internal arrays directly.

    Attributes:
        outer_vertices (numpy.ndarray): (N, 3) array of outer shell vertices in mm.
        outer_faces (numpy.ndarray): (F, 3) array of outer shell face indices.
        outer_colors (numpy.ndarray): (N, 3) array of RGB colors in range [0, 1].
        inner_vertices (numpy.ndarray): (N_inner, 3) array of inner shell vertices.
        inner_faces (numpy.ndarray): (F_inner, 3) array of inner shell face indices.
        inner_colors (numpy.ndarray): (N_inner, 3) array of inner RGB colors.
        magnet_settings (MagnetSettings): Configuration for magnet void insertion.
        recipe (list): Outer-shell displacement and colouring steps.
    """

    # ------------------------------------------------------------------
    # Construction
    # ------------------------------------------------------------------

    def __init__(
        self,
        method: str = 'fibonacci',
        n_points: int = 100000,
        radius: float = 40.0,
        center: tuple = (0.0, 0.0, 0.0),
        subdivisions: int = None,
        hollow: bool = False,
        inner_ratio: float = 0.8,
        inner_n_points: int = None,
        *,
        _vertices: np.ndarray = None,
        _faces: np.ndarray = None,
    ):
        """Creates a new GlobeModel.

        The constructor generates both outer and (optionally) inner sphere
        meshes so the user never needs to call internal geometry functions.

        Args:
            method (str, optional): Sphere generation method —
                ``'fibonacci'`` or ``'icosahedron'``. Defaults to ``'fibonacci'``.
            n_points (int, optional): Number of outer-shell vertices
                (used when *method* is ``'fibonacci'``). Defaults to 100000.
            radius (float, optional): Globe radius in mm. Defaults to 40.0.
            center (tuple, optional): Sphere center. Defaults to ``(0, 0, 0)``.
            subdivisions (int, optional): Number of icosahedron subdivision
                steps (used when *method* is ``'icosahedron'``).
            hollow (bool, optional): If ``True``, generate an inner mesh
                automatically. Defaults to ``False``.
            inner_ratio (float, optional): Inner-mesh radius as a fraction
                of ``radius`` (0 < inner_ratio < 1). Defaults to 0.8.
            inner_n_points (int, optional): Number of inner-shell vertices.
                Defaults to ``n_points // 5`` when *method* is ``'fibonacci'``,
                or ``max(subdivisions - 1, 1)`` when *method* is
                ``'icosahedron'``.
            _vertices (numpy.ndarray, optional): **Internal use only.**
                Pre-computed outer vertices (bypasses sphere generation).
            _faces (numpy.ndarray, optional): **Internal use only.**
                Pre-computed outer faces (bypasses sphere generation).

        Raises:
            ValueError: If *method* is unknown, or *subdivisions* is missing
                when ``method='icosahedron'``.
        """
        # --- Outer mesh ---------------------------------------------------
        if _vertices is not None and _faces is not None:
            # Internal fast-path used by from_fibonacci / from_icosahedron
            self.outer_vertices = np.asarray(_vertices, dtype=np.float64)
            self.outer_faces = np.asarray(_faces, dtype=np.int32)
        else:
            method = method.lower()
            if method == 'fibonacci':
                v, f = generate_sphere_points_fibonacci(n_points, radius, center)
            elif method == 'icosahedron':
                if subdivisions is None:
                    raise ValueError(
                        "subdivisions must be specified when method='icosahedron'."
                    )
                v, f = generate_sphere_points_icosahedron(subdivisions, radius, center)
            else:
                raise ValueError(
                    f"Unknown sphere method '{method}'. "
                    f"Supported: 'fibonacci', 'icosahedron'."
                )
            self.outer_vertices = v
            self.outer_faces = f

        self.outer_colors = None

        # --- Inner mesh ---------------------------------------------------
        self.inner_vertices = None
        self.inner_faces = None
        self.inner_colors = None

        if hollow:
            inner_radius = radius * inner_ratio
            if method == 'fibonacci':
                inner_np = inner_n_points or max(n_points // 5, 100)
                iv, if_ = generate_sphere_points_fibonacci(inner_np, inner_radius, center)
            elif method == 'icosahedron':
                inner_sub = inner_n_points or max((subdivisions or 1) - 1, 1)
                iv, if_ = generate_sphere_points_icosahedron(inner_sub, inner_radius, center)
            else:
                iv, if_ = generate_sphere_points_fibonacci(
                    inner_n_points or max(n_points // 5, 100),
                    inner_radius, center,
                )
            self.inner_vertices = iv
            self.inner_faces = if_

        # --- Metadata & recipes -------------------------------------------
        self.magnet_settings = None
        self.recipe = []            # outer-shell recipe
        self._inner_recipe = []     # inner-shell recipe
        self._radius = radius
        self._center = center

        # --- Proxies (created on first access) ----------------------------
        self._outer_proxy = None
        self._inner_proxy = None

    # ------------------------------------------------------------------
    # Backward-compatible factory methods
    # ------------------------------------------------------------------

    @classmethod
    def from_fibonacci(cls, n_points: int, radius: float = 1.0,
                       center=(0.0, 0.0, 0.0)) -> "GlobeModel":
        """Creates a GlobeModel using a Fibonacci lattice (convenience wrapper).

        Args:
            n_points (int): Number of outer-shell vertices.
            radius (float, optional): Sphere radius in mm. Defaults to 1.0.
            center (array-like, optional): Sphere center. Defaults to ``(0, 0, 0)``.

        Returns:
            GlobeModel: A new model instance.
        """
        v, f = generate_sphere_points_fibonacci(n_points, radius, center)
        model = cls.__new__(cls)
        model.outer_vertices = v
        model.outer_faces = f
        model.outer_colors = None
        model.inner_vertices = None
        model.inner_faces = None
        model.inner_colors = None
        model.magnet_settings = None
        model.recipe = []
        model._inner_recipe = []
        model._radius = radius
        model._center = center
        model._outer_proxy = None
        model._inner_proxy = None
        return model

    @classmethod
    def from_icosahedron(cls, subdivisions: int, radius: float = 1.0,
                         center=(0.0, 0.0, 0.0)) -> "GlobeModel":
        """Creates a GlobeModel by subdividing an icosahedron (convenience wrapper).

        Args:
            subdivisions (int): Number of subdivision steps.
            radius (float, optional): Sphere radius in mm. Defaults to 1.0.
            center (array-like, optional): Sphere center. Defaults to ``(0, 0, 0)``.

        Returns:
            GlobeModel: A new model instance.
        """
        v, f = generate_sphere_points_icosahedron(subdivisions, radius, center)
        model = cls.__new__(cls)
        model.outer_vertices = v
        model.outer_faces = f
        model.outer_colors = None
        model.inner_vertices = None
        model.inner_faces = None
        model.inner_colors = None
        model.magnet_settings = None
        model.recipe = []
        model._inner_recipe = []
        model._radius = radius
        model._center = center
        model._outer_proxy = None
        model._inner_proxy = None
        return model

    # ------------------------------------------------------------------
    # Proxy accessors
    # ------------------------------------------------------------------

    @property
    def outer(self) -> _MeshProxy:
        """Proxy for the outer shell (use ``model.outer.displace(...)`` etc.)."""
        if self._outer_proxy is None:
            self._outer_proxy = _MeshProxy(self, "outer")
        return self._outer_proxy

    @property
    def inner(self) -> _MeshProxy:
        """Proxy for the inner shell (use ``model.inner.displace(...)`` etc.).

        Raises:
            ValueError: If inner geometry has not been initialized.
        """
        if self.inner_vertices is None:
            raise ValueError(
                "Inner geometry is not initialized. Create the model with "
                "hollow=True, or call model.create_inner_mesh(thickness)."
            )
        if self._inner_proxy is None:
            self._inner_proxy = _MeshProxy(self, "inner")
        return self._inner_proxy

    # ------------------------------------------------------------------
    # Convenience wrappers (delegate to outer proxy)
    # ------------------------------------------------------------------

    def displace(self, displacer: Displacer, scale: float = 1.0):
        """Displaces the **outer** vertices.  Shortcut for ``model.outer.displace(...)``.

        Args:
            displacer (Displacer): The displacement object to apply.
            scale (float, optional): Scaling multiplier. Defaults to 1.0.

        Raises:
            ValueError: If outer geometry is not initialized.
        """
        self.outer.displace(displacer, scale=scale)

    def displace_constant(self, amount: float, scale: float = 1.0):
        """Displaces the **outer** vertices by a constant radial amount.

        Shortcut for ``model.outer.displace_constant(...)``.

        Args:
            amount (float): The constant displacement in mm.
            scale (float, optional): Scaling multiplier. Defaults to 1.0.

        Raises:
            ValueError: If outer geometry is not initialized.
        """
        self.outer.displace_constant(amount, scale=scale)

    def colour(self, colouring: Colourer, target: str = "outer",
               selection=None, selection_kwargs=None):
        """Assigns colors to a subset of the model's vertices and records the step in the recipe.

        Args:
            colouring (Colourer): The coloring object to apply.
            target (str, optional): Target to color (``'outer'`` or ``'inner'``).
                Defaults to ``'outer'``.
            selection (str, callable, or array-like, optional): Vertex subset selection.
                Can be ``'inward_facing'``, ``'outward_facing'``, a custom callable,
                or a list of indices.
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

            new_colors = colouring(vertices[selected_indices], current_colors=current_colors[selected_indices])
            current_colors[selected_indices] = new_colors
            setattr(self, f"{target}_colors", current_colors)

        recipe = self.recipe if target == "outer" else self._inner_recipe
        recipe.append({
            "type": "colouring",
            "colouring": colouring,
            "target": target,
            "selection": selection,
            "selection_kwargs": selection_kwargs
        })

    # ------------------------------------------------------------------
    # Inner mesh helpers
    # ------------------------------------------------------------------

    def create_inner_mesh(self, thickness: float):
        """Generates the inner mesh by scaling down the outer mesh.

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

    # ------------------------------------------------------------------
    # Magnet configuration
    # ------------------------------------------------------------------

    def configure_magnets(self, **kwargs):
        """Configures magnet settings for hemisphere generation.

        All keyword arguments are forwarded to :class:`MagnetSettings`.
        Common parameters include ``diameter``, ``height``, ``n_magnets``,
        ``position``, ``horizontal_tolerance``, ``vertical_tolerance``,
        ``vertical_offset``, ``min_thickness``, ``add_bosses``,
        ``min_magnets``, ``min_angular_spacing``, and ``step_degrees``.

        Args:
            **kwargs: Keyword arguments forwarded to :class:`MagnetSettings`.
        """
        self.magnet_settings = MagnetSettings(**kwargs)

    # ------------------------------------------------------------------
    # Trimesh conversion
    # ------------------------------------------------------------------

    def to_trimesh(self, part: str = "outer") -> trimesh.Trimesh:
        """Generates a :class:`trimesh.Trimesh` representation.

        Args:
            part (str, optional): Part to generate — ``'outer'``, ``'inner'``,
                or ``'combined'``. Defaults to ``'outer'``.

        Returns:
            trimesh.Trimesh: The requested mesh.
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

    # ------------------------------------------------------------------
    # Recipe re-application (after boolean splits create new vertices)
    # ------------------------------------------------------------------

    def _classify_mesh_vertices(self, mesh_vertices: np.ndarray) -> tuple:
        """Classifies each vertex in mesh_vertices as belonging to the outer or inner shell.

        Uses a direction-based radial comparison to handle radial displacements robustly.

        Args:
            mesh_vertices (numpy.ndarray): (M, 3) vertex coordinates to classify.

        Returns:
            tuple: (is_outer, is_inner) boolean masks of shape (M,).
        """
        from scipy.spatial import KDTree
        C = np.asarray(self._center)
        
        # Outer original displaced vertices
        dir_outer = self.outer_vertices - C
        norm_outer = np.linalg.norm(dir_outer, axis=1, keepdims=True)
        u_outer = dir_outer / np.where(norm_outer == 0, 1.0, norm_outer)
        
        # Inner original displaced vertices
        dir_inner = self.inner_vertices - C
        norm_inner = np.linalg.norm(dir_inner, axis=1, keepdims=True)
        u_inner = dir_inner / np.where(norm_inner == 0, 1.0, norm_inner)
        
        # Query vertices
        dir_query = mesh_vertices - C
        norm_query = np.linalg.norm(dir_query, axis=1, keepdims=True)
        u_query = dir_query / np.where(norm_query == 0, 1.0, norm_query)
        
        # Direction KD-trees
        tree_outer = KDTree(u_outer)
        tree_inner = KDTree(u_inner)
        
        _, idx_outer = tree_outer.query(u_query)
        _, idx_inner = tree_inner.query(u_query)
        
        r_outer_matched = norm_outer[idx_outer, 0]
        r_inner_matched = norm_inner[idx_inner, 0]
        
        r_query = norm_query[:, 0]
        
        dist_to_outer = np.abs(r_query - r_outer_matched)
        dist_to_inner = np.abs(r_query - r_inner_matched)
        
        is_outer = dist_to_outer < dist_to_inner
        is_inner = dist_to_inner <= dist_to_outer
        
        return is_outer, is_inner

    def _apply_recipe_colors_to_mesh(self, mesh: trimesh.Trimesh):
        """Re-applies colouring steps from both recipes to a post-processed mesh."""
        all_color_steps = [
            s for s in self.recipe if s["type"] == "colouring"
        ] + [
            s for s in self._inner_recipe if s["type"] == "colouring"
        ]
        if not all_color_steps:
            return

        colors = np.ones((len(mesh.vertices), 3), dtype=np.float64)

        if self.inner_vertices is not None:
            is_outer, is_inner = self._classify_mesh_vertices(mesh.vertices)
        else:
            is_outer = np.ones(len(mesh.vertices), dtype=bool)
            is_inner = np.zeros(len(mesh.vertices), dtype=bool)

        for step in all_color_steps:
            colouring = step["colouring"]
            selection = step["selection"]
            selection_kwargs = step["selection_kwargs"] or {}
            target = step.get("target", "outer")

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
                selected_indices = np.asarray(selection, dtype=np.int32)
                selected_indices = selected_indices[(selected_indices >= 0) & (selected_indices < len(mesh.vertices))]

            # Filter selected indices to target shell
            target_mask = is_outer if target == "outer" else is_inner
            if len(selected_indices) > 0:
                selected_indices = selected_indices[target_mask[selected_indices]]

            if len(selected_indices) > 0:
                new_colors = colouring(mesh.vertices[selected_indices], current_colors=colors[selected_indices])
                colors[selected_indices] = new_colors

        mesh.visual.vertex_colors = (colors * 255.0).astype(np.uint8)

    # ------------------------------------------------------------------
    # Hemisphere generation
    # ------------------------------------------------------------------

    def generate_hemispheres(
        self,
        plane_normal=(0, 0, 1),
        plane_origin=(0, 0, 0),
        hollow: bool = True,
        thickness: float = 1.5,
        engine: str = None,
    ) -> tuple:
        """Cuts the globe into top and bottom capped hemispheres, optionally hollowed with magnets.

        Args:
            plane_normal (array-like, optional): Cutting plane normal.
                Defaults to ``(0, 0, 1)``.
            plane_origin (array-like, optional): Cutting plane origin.
                Defaults to ``(0, 0, 0)``.
            hollow (bool, optional): If ``True``, hollow the hemispheres.
                Defaults to ``True``.
            thickness (float, optional): Shell thickness in mm (used only if
                inner mesh has not been created yet). Defaults to 1.5.
            engine (str, optional): Boolean engine for trimesh.
                Defaults to ``None``.

        Returns:
            tuple: ``(top_half, bottom_half)`` as :class:`trimesh.Trimesh` objects.
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

    # ------------------------------------------------------------------
    # Visualization & Preview
    # ------------------------------------------------------------------

    def preview(
        self,
        part: str = "whole",
        hollow: bool = True,
        thickness: float = 1.5,
        engine: str = None,
        **kwargs,
    ):
        """Visualizes the model (whole, or upper/lower hemisphere) in 3D.

        Args:
            part (str, optional): The part of the model to visualize:
                - ``'whole'`` (or ``'combined'``, ``'outer'``, ``'inner'``): visualizes the entire model.
                - ``'upper'`` (or ``'top'``): visualizes the upper/top hemisphere.
                - ``'lower'`` (or ``'bottom'``): visualizes the lower/bottom hemisphere.
                Defaults to ``'whole'``.
            hollow (bool, optional): If visualizing a hemisphere, whether it
                should be hollowed. Defaults to ``True``.
            thickness (float, optional): Shell thickness in mm (used only if
                inner mesh has not been created yet). Defaults to 1.5.
            engine (str, optional): Boolean engine for hollowing/splitting.
                Defaults to ``None``.
            **kwargs: Extra keyword arguments passed to the trimesh visualizer
                (e.g., `mesh.show(**kwargs)`).

        Returns:
            trimesh.Scene: The trimesh Scene object representing the 3D viewer.

        Raises:
            ValueError: If an unknown part is specified.
        """
        part_lower = part.lower()
        if part_lower in ("whole", "combined"):
            if self.inner_vertices is not None:
                mesh = self.to_trimesh(part="combined")
            else:
                mesh = self.to_trimesh(part="outer")
        elif part_lower == "outer":
            mesh = self.to_trimesh(part="outer")
        elif part_lower == "inner":
            mesh = self.to_trimesh(part="inner")
        elif part_lower in ("upper", "top"):
            top_half, _ = self.generate_hemispheres(
                hollow=hollow, thickness=thickness, engine=engine
            )
            mesh = top_half
        elif part_lower in ("lower", "bottom"):
            _, bottom_half = self.generate_hemispheres(
                hollow=hollow, thickness=thickness, engine=engine
            )
            mesh = bottom_half
        else:
            raise ValueError(
                f"Unknown part '{part}'. Supported: 'whole', 'combined', 'outer', 'inner', 'upper', 'top', 'lower', 'bottom'."
            )

        return mesh.show(**kwargs)

    # ------------------------------------------------------------------
    # Export
    # ------------------------------------------------------------------

    def export(self, filename: str, part: str = "outer", include_color: bool = True,
               fix_normals: bool = False):
        """Exports the model to disk.  File format is inferred from the extension.

        Supported formats: ``.stl`` (binary STL, no color), ``.obj`` (OBJ
        with vertex colors when *include_color* is ``True``).

        Args:
            filename (str): Output file path (must end with ``.stl`` or ``.obj``).
            part (str, optional): Part to export — ``'outer'``, ``'inner'``,
                or ``'combined'``. Defaults to ``'outer'``.
            include_color (bool, optional): Embed vertex colors (OBJ only).
                Defaults to ``True``.
            fix_normals (bool, optional): Force outward-facing normals via
                chirality fix (only for simple convex meshes).
                Defaults to ``False``.

        Raises:
            ValueError: If the file extension is not supported.
        """
        import os as _os
        ext = _os.path.splitext(filename)[1].lower()

        if ext == '.stl':
            self.write_stl(filename, part=part)
        elif ext == '.obj':
            self.write_obj(filename, part=part, fix_normals=fix_normals)
        else:
            raise ValueError(
                f"Unsupported file extension '{ext}'. Use '.stl' or '.obj'."
            )

    def export_hemispheres(
        self,
        top_filename: str,
        bottom_filename: str,
        include_color: bool = True,
        hollow: bool = True,
        thickness: float = 1.5,
        engine: str = 'manifold',
        plane_normal=(0, 0, 1),
        plane_origin=(0, 0, 0),
    ):
        """Splits, hollows, colors, and exports both hemispheres in one call.

        This is the highest-level export helper — it performs the entire
        split → hollow → color → write pipeline so the user never needs to
        manually extract colors or import internal writers.

        Args:
            top_filename (str): Output path for the top hemisphere.
            bottom_filename (str): Output path for the bottom hemisphere.
            include_color (bool, optional): Embed vertex colors (OBJ only).
                Defaults to ``True``.
            hollow (bool, optional): Hollow the hemispheres.
                Defaults to ``True``.
            thickness (float, optional): Shell thickness in mm (used only if
                inner mesh has not been created yet). Defaults to 1.5.
            engine (str, optional): Boolean engine. Defaults to ``'manifold'``.
            plane_normal (array-like, optional): Cutting plane normal.
                Defaults to ``(0, 0, 1)``.
            plane_origin (array-like, optional): Cutting plane origin.
                Defaults to ``(0, 0, 0)``.

        Raises:
            RuntimeError: If hemisphere generation fails.
        """
        import os as _os
        from globe3d.io import write_stl_binary, write_obj_with_vertex_colors

        top_half, bottom_half = self.generate_hemispheres(
            plane_normal=plane_normal,
            plane_origin=plane_origin,
            hollow=hollow,
            thickness=thickness,
            engine=engine,
        )

        if top_half is None or bottom_half is None:
            raise RuntimeError("Hemisphere generation failed.")

        for fname, mesh in [(top_filename, top_half), (bottom_filename, bottom_half)]:
            # Ensure output directory exists
            out_dir = _os.path.dirname(fname)
            if out_dir:
                _os.makedirs(out_dir, exist_ok=True)

            ext = _os.path.splitext(fname)[1].lower()
            if ext == '.stl':
                write_stl_binary(fname, mesh.vertices, mesh.faces)
            elif ext == '.obj':
                if include_color and hasattr(mesh.visual, 'vertex_colors') and mesh.visual.vertex_colors is not None:
                    colors = mesh.visual.vertex_colors[:, :3].astype(np.float64) / 255.0
                else:
                    colors = np.ones((len(mesh.vertices), 3), dtype=np.float64)
                write_obj_with_vertex_colors(fname, mesh.vertices, mesh.faces, colors)
            else:
                raise ValueError(
                    f"Unsupported file extension '{ext}'. Use '.stl' or '.obj'."
                )

    # ------------------------------------------------------------------
    # Legacy export helpers
    # ------------------------------------------------------------------

    def write_stl(self, filename: str, part: str = "outer"):
        """Exports the model geometry to a binary STL file.

        Args:
            filename (str): Path to export the STL.
            part (str, optional): Part to export (``'outer'``, ``'inner'``,
                or ``'combined'``). Defaults to ``'outer'``.
        """
        mesh = self.to_trimesh(part=part)
        from globe3d.io import write_stl_binary
        write_stl_binary(filename, mesh.vertices, mesh.faces)

    def write_obj(self, filename: str, part: str = "outer",
                  center=(0.0, 0.0, 0.0), fix_normals=False):
        """Exports the model geometry with vertex colors to an OBJ file.

        Args:
            filename (str): Path to export the OBJ.
            part (str, optional): Part to export (``'outer'``, ``'inner'``,
                or ``'combined'``). Defaults to ``'outer'``.
            center (array-like, optional): Center point. Defaults to ``(0, 0, 0)``.
            fix_normals (bool, optional): If ``True``, corrects face normals
                winding order. Defaults to ``False``.
        """
        mesh = self.to_trimesh(part=part)
        from globe3d.io import write_obj_with_vertex_colors

        if hasattr(mesh.visual, "vertex_colors") and mesh.visual.vertex_colors is not None:
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

    if (outer_colors is not None) or (inner_colors is not None):
        if outer_colors is None:
            outer_colors = np.ones((len(outer_vertices), 3), dtype=np.float64)
        if inner_colors is None:
            inner_colors = np.ones((len(inner_vertices), 3), dtype=np.float64)
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
            raise RuntimeError(
                "Error: Boolean operation failed (Trimesh object is not iterable). Check the mesh geometry."
            ) from e
        else:
            raise RuntimeError(f"Error performing boolean difference: {e}") from e

    if hollowed_mesh is None:
        raise ValueError("Error: Boolean difference returned None.")

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
            raise RuntimeError(f"Error saving hollowed mesh: {e}") from e
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
        raise RuntimeError(f"Error splitting mesh: {e}") from e


def create_hollow_hemispheres(
    outer_vertices, outer_faces,
    inner_vertices, inner_faces,
    plane_normal=(0, 0, 1),
    plane_origin=(0, 0, 0),
    engine=None,
    magnet_params=None,
):
    """Creates two hollow hemispheres for 3D printing, optionally with magnet voids.

    Args:
        outer_vertices (numpy.ndarray): Array of shape (n_points, 3) representing outer vertices.
        outer_faces (numpy.ndarray): Array of shape (n_faces, 3) representing outer faces.
        inner_vertices (numpy.ndarray): Array of shape (n_points_inner, 3) representing inner vertices.
        inner_faces (numpy.ndarray): Array of shape (n_faces_inner, 3) representing inner faces.
        plane_normal (array-like, optional): Winding normal direction for the cutting plane. Defaults to (0, 0, 1).
        plane_origin (array-like, optional): Origin point of the cutting plane. Defaults to (0, 0, 0).
        engine (str, optional): Boolean engine name. Defaults to None.
        magnet_params (MagnetSettings, optional): Configuration settings for inserting magnet voids. Defaults to None.

    Returns:
        tuple: (top_hollow, bottom_hollow) as trimesh.Trimesh objects.

    Raises:
        RuntimeError: If mesh splitting, boolean subtraction, or magnet insertion fails.
        ValueError: If slice plane operations or boolean difference operations return None.
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
        raise RuntimeError(f"Error splitting outer mesh: {e}") from e

    if top_outer is None or bottom_outer is None:
        raise ValueError("slice_plane returned None, splitting outer mesh failed.")

    bool_kwargs = {}
    if engine is not None:
        bool_kwargs['engine'] = engine

    try:
        top_hollow = trimesh.boolean.difference(
            [top_outer, inner_mesh], **bool_kwargs
        )
    except Exception as e:
        raise RuntimeError(f"Error performing boolean subtraction on top hemisphere: {e}") from e

    if top_hollow is None:
        raise ValueError("Boolean subtraction on top hemisphere returned None.")

    try:
        bottom_hollow = trimesh.boolean.difference(
            [bottom_outer, inner_mesh], **bool_kwargs
        )
    except Exception as e:
        raise RuntimeError(f"Error performing boolean subtraction on bottom hemisphere: {e}") from e

    if bottom_hollow is None:
        raise ValueError("Boolean subtraction on bottom hemisphere returned None.")

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
            raise RuntimeError(f"Error inserting magnets: {e}") from e

    return top_hollow, bottom_hollow

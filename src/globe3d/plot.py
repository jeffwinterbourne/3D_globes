import numpy as np
import matplotlib.pyplot as plt
from .displacement import cartesian_to_spherical


def plot_vertex_distribution(vertices, title='Vertex Distribution', sample_size=0):
    """Creates a quick scatter plot (using lat/lon) of the vertex distribution.

    For very large meshes, a random subset (sample_size) is shown.

    Args:
        vertices (numpy.ndarray): (n_points, 3) vertex coordinates.
        title (str, optional): Plot title. Defaults to 'Vertex Distribution'.
        sample_size (int, optional): Number of points to sample for plotting. Set to 0 to plot all points.
            Defaults to 0.
    """
    if vertices.shape[0] > sample_size and sample_size > 0:
        idx = np.random.choice(vertices.shape[0], sample_size, replace=False)
        pts = vertices[idx]
    else:
        pts = vertices

    # Convert Cartesian (x,y,z) to geographic (lat, lon)
    _, lat, lon = cartesian_to_spherical(pts)
    plt.figure(figsize=(8, 4))
    plt.scatter(lon, lat, s=1, alpha=0.5)
    plt.xlabel("Longitude")
    plt.ylabel("Latitude")
    plt.title(title)
    plt.grid(True)
    plt.show()


def plot_globe_preview(
    model,
    elev: float = 20.0,
    azim: float = 0.0,
    title: str = "3D Globe Preview",
    sample_size: int = 15000,
    point_size: float = 8.0,
    figsize: tuple = (6.0, 6.0),
    ax=None,
):
    """Renders a 3D orthographic preview of a GlobeModel mesh using Matplotlib.

    Visualizes the displaced outer spherical mesh colored with its vertex colors
    from a specified viewing angle (elevation and azimuth).

    Args:
        model (GlobeModel or trimesh.Trimesh): Model or mesh to preview.
        elev (float, optional): Elevation viewing angle in degrees. Defaults to 20.0.
        azim (float, optional): Azimuth viewing angle in degrees. Defaults to 0.0.
        title (str, optional): Plot title. Defaults to '3D Globe Preview'.
        sample_size (int, optional): Number of vertices to sample for speed.
            Set to 0 to plot all vertices. Defaults to 15000.
        point_size (float, optional): Matplotlib scatter point size. Defaults to 8.0.
        figsize (tuple, optional): Figure dimensions. Defaults to (6.0, 6.0).
        ax (matplotlib.axes.Axes, optional): Target 3D axes. Defaults to None.

    Returns:
        matplotlib.axes.Axes: The rendered 3D matplotlib axes.
    """
    mesh = model.outer if hasattr(model, "outer") else model

    verts = np.asarray(mesh.vertices)
    n_verts = len(verts)

    # Extract vertex colors if available
    colors = None
    if hasattr(mesh, "visual") and hasattr(mesh.visual, "vertex_colors"):
        vc = np.asarray(mesh.visual.vertex_colors)
        if len(vc) == n_verts:
            colors = vc[:, :3] / 255.0

    if sample_size > 0 and n_verts > sample_size:
        idx = np.random.choice(n_verts, sample_size, replace=False)
        verts_sub = verts[idx]
        colors_sub = colors[idx] if colors is not None else None
    else:
        verts_sub = verts
        colors_sub = colors

    if ax is None:
        fig = plt.figure(figsize=figsize)
        ax = fig.add_subplot(111, projection="3d")

    if colors_sub is not None:
        ax.scatter(
            verts_sub[:, 0],
            verts_sub[:, 1],
            verts_sub[:, 2],
            c=colors_sub,
            s=point_size,
            alpha=0.9,
            edgecolors="none",
        )
    else:
        ax.scatter(
            verts_sub[:, 0],
            verts_sub[:, 1],
            verts_sub[:, 2],
            c="silver",
            s=point_size,
            alpha=0.8,
            edgecolors="none",
        )

    ax.view_init(elev=elev, azim=azim)
    ax.set_axis_off()
    ax.set_title(title, fontsize=12, fontweight="bold", pad=12)

    # Equal scaling
    max_range = (
        np.array([
            verts_sub[:, 0].max() - verts_sub[:, 0].min(),
            verts_sub[:, 1].max() - verts_sub[:, 1].min(),
            verts_sub[:, 2].max() - verts_sub[:, 2].min(),
        ]).max()
        / 2.0
    )
    mid_x = (verts_sub[:, 0].max() + verts_sub[:, 0].min()) * 0.5
    mid_y = (verts_sub[:, 1].max() + verts_sub[:, 1].min()) * 0.5
    mid_z = (verts_sub[:, 2].max() + verts_sub[:, 2].min()) * 0.5
    ax.set_xlim(mid_x - max_range, mid_x + max_range)
    ax.set_ylim(mid_y - max_range, mid_y + max_range)
    ax.set_zlim(mid_z - max_range, mid_z + max_range)

    plt.tight_layout()
    return ax


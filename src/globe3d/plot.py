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

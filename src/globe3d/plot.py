import numpy as np
import matplotlib.pyplot as plt

def plot_vertex_distribution(vertices, title='Vertex Distribution', sample_size=0):
    """
    Creates a quick scatter plot (using lat/lon) of the vertex distribution.
    For very large meshes, a random subset (sample_size) is shown.

    Parameters:
      vertices: (n_points x 3) numpy array.
      title (str): Plot title.
      sample_size (int): Number of points to sample for plotting (default 0). Set to 0 to plot all points.
    """
    if vertices.shape[0] > sample_size and sample_size > 0:
        idx = np.random.choice(vertices.shape[0], sample_size, replace=False)
        pts = vertices[idx]
    else:
        pts = vertices

    # Convert Cartesian (x,y,z) to geographic (lat, lon)
    r = np.linalg.norm(pts, axis=1)
    lat = np.degrees(np.arcsin(pts[:, 2] / r))
    lon = np.degrees(np.arctan2(pts[:, 1], pts[:, 0]))
    plt.figure(figsize=(8, 4))
    plt.scatter(lon, lat, s=1, alpha=0.5)
    plt.xlabel("Longitude")
    plt.ylabel("Latitude")
    plt.title(title)
    plt.grid(True)
    plt.show()

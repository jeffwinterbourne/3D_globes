# 8. Where to Get Data

To build your 3D globes, you need high-quality global grids. Luckily, the Earth and planetary science communities make vast catalogs of global data freely available. This page lists the best open-access repositories to find compatible grids of topography, planetary surfaces, geoid heights, crustal thickness, and seismic tomography, and documents how to load them directly using the built-in `datasets` module.

---

## 📦 The `globe3d.datasets` Helper Module

Rather than manually downloading and formatting these files, you can use the built-in `globe3d.datasets` module to automatically fetch, cache, and load standard datasets as `GeographicGrid` objects.

To see all available datasets programmatically, call:
```python
from globe3d import datasets
print(datasets.list_datasets())
```

All datasets are organized in a clean, hierarchical structure:
- `datasets.topography` (Earth, Mars, Moon, Venus, Mercury, ETOPO, GEBCO)
- `datasets.tomography` (S40RTS)
- `datasets.geoid` (EGM2008)
- `datasets.crust` (CRUST1.0)
- `datasets.dynamic_topography` (Hoggard 2016)
- `datasets.gravity` (Bouguer Anomaly)
- `datasets.magnetics` (EMAG2v3)
- `datasets.shapefiles` (Natural Earth land and coastline vector data)

---

## 🌍 1. Earth Topography & Bathymetry

For standard Earth models showing both land elevation and ocean depths:

*   **ETOPO (2022 or ETOPO1)**
    *   **What it is**: The gold standard for global relief, integrating land topography and ocean bathymetry into a single grid.
    *   **Where to download**: [NOAA National Centers for Environmental Information (NCEI) ETOPO page](https://www.ncei.noaa.gov/products/etopo-global-relief-model).
    *   **Format to select**: NetCDF (usually `.nc` or `.grd`).
    *   **Recommended Resolution**: A grid spacing of **60 arc-seconds (1 arc-minute)** is perfect. It provides high detail but keeps file sizes and computation times manageable in Python.
*   **GEBCO Grid**
    *   **What it is**: The General Bathymetric Chart of the Oceans, containing very high-resolution global bathymetry.
    *   **Where to download**: [GEBCO Data Store](https://www.gebco.net/data_and_products/gridded_bathymetry_data/).
    *   **Format**: NetCDF format.
*   **Quick access via `datasets`**:
    ```python
    # Load default 30m resolution Earth relief from GMT servers
    grid = datasets.topography.earth(resolution="30m")
    
    # Load high-resolution ETOPO1 bedrock grid (automatically downloads from NOAA)
    etopo_grid = datasets.topography.etopo(resolution="high")
    
    # Load GEBCO grid (requires local file path since it is very large)
    gebco_grid = datasets.topography.gebco(url="path/to/gebco_file.nc")
    ```

---

## 🚀 2. Planetary Topography (Celestial Bodies)

To print other planets or the Moon:

*   **The Moon (LOLA)**
    *   **What it is**: Laser altimetry data from the Lunar Orbiter Laser Altimeter (LOLA) aboard NASA's Lunar Reconnaissance Orbiter.
    *   **Where to download**: [NASA PDS Geosciences Node](https://pds-geosciences.wustl.edu/missions/lro/lola.htm) or the [USGS Astrogeology Science Center](https://astrogeology.usgs.gov/search/map/Moon/LRO/LOLA/Lunar_LRO_LOLA_Global_LDEM_118m_Mar2014).
*   **Mars (MOLA)**
    *   **What it is**: Topography from the Mars Orbiter Laser Altimeter (MOLA) aboard Mars Global Surveyor, showing the Martian dichotomy and Olympus Mons.
    *   **Where to download**: [NASA PDS Mars Archive](https://pds-geosciences.wustl.edu/missions/mgs/mola.htm) or [USGS Astrogeology Mars Search](https://astrogeology.usgs.gov/search/results?q=MOLA).
*   **Other Bodies (Venus, Mercury, Vesta)**
    *   Find Magellan Venus radar altimetry grids and Messenger Mercury altimetry grids at [USGS Astrogeology Astro-Explorer](https://astrogeology.usgs.gov/).
*   **Quick access via `datasets`**:
    ```python
    # Load planetary topography
    moon_grid = datasets.topography.moon(resolution="30m")
    mars_grid = datasets.topography.mars(resolution="30m")
    venus_grid = datasets.topography.venus(resolution="30m")
    mercury_grid = datasets.topography.mercury(resolution="30m")
    
    # Note: Vesta is highly irregular (non-spherical) and shapefiles/mesh models 
    # should be imported directly. datasets.topography.vesta() will raise a guide error.
    ```

---

## 🌊 3. The Geoid (Gravity Potentials)

The geoid represents the shape that the global ocean surface would take under the influence of Earth's gravity and rotation alone, ignoring winds and tides. It is often described as the gravitational "lumpiness" of the Earth:

*   **ICGEM (International Centre for Global Earth Models)**
    *   **What it is**: A service hosted by GFZ Potsdam containing all modern global gravity field models (like EGM2008 or EIGEN-6C4).
    *   **Where to download**: [ICGEM Model Visualization & Download](http://icgem.gfz-potsdam.de/).
    *   **How to get a grid**: Use their online calculation service to generate a grid of **"Geoid heights"** relative to a reference ellipsoid (like WGS84) in ASCII or NetCDF format.
*   **Quick access via `datasets`**:
    ```python
    # Load EGM2008 geoid undulations
    geoid_grid = datasets.geoid.egm2008(downsample_factor=5)
    ```

---

## 🕳️ 4. Crustal Thickness

To print a globe that opens up to reveal the depth of the Earth's crust (the Moho boundary):

*   **CRUST1.0**
    *   **What it is**: A global 1-degree model of the Earth's crust, including sediment thickness, ice cover, and the depth of the boundary between the crust and the mantle (the Mohorovičić discontinuity, or Moho).
    *   **Where to download**: [University of California, San Diego (UCSD) Crustal Models website](https://igppweb.ucsd.edu/~gabi/crust1.html).
    *   **How to use**: Download the dataset files and use their accompanying scripts (or the helper loaders in `globe3d`) to read the Moho depth grid.
*   **Quick access via `datasets`**:
    ```python
    # Load Moho boundary from CRUST1.0
    moho_grid = datasets.crust.crust1(layer="moho", as_meters=True)
    ```

---

## 🌋 5. Seismic Tomography (Deep Earth Interior)

For creating "Russian Nesting Doll" (Matryoshka) models showing seismic wave velocity variations deep within the mantle:

*   **SubMachine (University of Oxford)**
    *   **What it is**: An excellent web-based database and tool for visualizing and downloading grids of global seismic tomography models (including shear-wave and compressional-wave models like SP12RTS, S40RTS, or GLAD-M25).
    *   **Where to download**: [SubMachine Web Portal](https://submachine.earth.ox.ac.uk/).
    *   **Instructions**: Select your model of interest, specify the depth slice you want (e.g. 50 km, 660 km, or 2,850 km), and export the slice as a GMT-compatible `.grd` or NetCDF file.
*   **IRIS DMC Products**
    *   **What it is**: The Incorporated Research Institutions for Seismology Data Management Center.
    *   **Where to download**: [IRIS EMC (Earth Model Collaboration)](https://ds.iris.edu/ds/products/emc/).
*   **Quick access via `datasets`**:
    ```python
    # Load 2D depth slice of S40RTS shear-wave tomography at 2850 km depth
    tomo_grid = datasets.tomography.s40rts(depth=2850.0)
    ```

---

## 🌊 6. Dynamic Topography

Dynamic topography is the surface expression of mantle convection (upwellings pushing the crust up, and downwellings pulling it down):

*   **Hoggard et al. (2016) Dataset**
    *   **What it is**: A comprehensive global model of dynamic topography derived from oceanic residual measurements.
    *   **Where to download**: The supplementary material of their Nature Geoscience paper (*Hoggard et al., 2016, "Global update of oceanic residual depth measurements..."* - [link to paper](https://www.nature.com/articles/ngeo2709)) or via global data shares on Zenodo.
*   **Quick access via `datasets`**:
    ```python
    # Load Hoggard dynamic topography grid
    dyn_grid = datasets.dynamic_topography.hoggard2016(grid_step=1.0)
    ```

---

## 🗺️ 7. Vector Shapefiles (Land & Coastlines)

For applying sharp step displacements or coloring boundaries (like coastlines and continents):

*   **Natural Earth**
    *   **What it is**: A public domain map dataset available at various scales, featuring tightly integrated vector and raster data.
    *   **Where to download**: [Natural Earth Downloads](https://www.naturalearthdata.com/downloads/).
*   **Quick access via `datasets`**:
    ```python
    # Automatically download, cache, extract and retrieve the path to the 1:110m land polygons shapefile
    land_shp = datasets.shapefiles.land()
    
    # Automatically download, cache, extract and retrieve the path to the 1:110m coastlines shapefile
    coastline_shp = datasets.shapefiles.coastline()
    ```

---

## 🛠️ Formatting Checklist for globe3d
When downloading datasets, verify the following to ensure they load without errors:
1.  **Coordinate Range**: Longitude should span $[-180^\circ, 180^\circ]$ or $[0^\circ, 360^\circ]$, and latitude should span $[-90^\circ, 90^\circ]$.
2.  **Ascending Order**: The grid arrays must have latitude and longitude sorted in ascending order (increasing values).
3.  **Equirectangular Mapping**: For TIFF/JPEG image overlays, ensure the map projection is a simple **equirectangular (Plate Carrée)** projection (unprojected lat/lon grid) with a 2:1 aspect ratio.

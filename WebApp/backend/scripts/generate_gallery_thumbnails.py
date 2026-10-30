import os
import json
import numpy as np

WEBAPP_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
PRESETS_DIR = os.path.join(WEBAPP_DIR, "presets")
THUMBNAILS_DIR = os.path.join(PRESETS_DIR, "thumbnails")


def generate_all_preset_thumbnails():
    """Generates visual thumbnail PNGs for all built-in presets."""
    os.makedirs(THUMBNAILS_DIR, exist_ok=True)
    index_path = os.path.join(PRESETS_DIR, "index.json")
    if not os.path.exists(index_path):
        print("No presets/index.json found.")
        return

    with open(index_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    presets = data if isinstance(data, list) else data.get("presets", [])

    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    # Pre-generate a 64x128 synthetic spherical harmonic elevation grid
    lats = np.linspace(-np.pi / 2, np.pi / 2, 80)
    lons = np.linspace(-np.pi, np.pi, 160)
    lon_grid, lat_grid = np.meshgrid(lons, lats)
    base_topo = (
        np.sin(2 * lat_grid) * np.cos(3 * lon_grid)
        + 0.5 * np.cos(5 * lat_grid) * np.sin(lon_grid)
        + 0.25 * np.sin(7 * lon_grid)
    )

    colormap_defaults = {
        "example_1_procedural_globe": ("viridis", "Procedural Wave"),
        "example_2_hollow_globe": ("terrain", "Hollow + Magnets"),
        "example_3_earth_topography": ("terrain", "Earth Hypsometry"),
        "example_4_tectonic_globe": ("copper", "Tectonic Plates"),
        "example_5_3mf_multicolor_globe": ("cubehelix", "4-Filament Mix"),
        "example_6_paleo_permian_triassic_250ma": ("gist_earth", "250 Ma Pangea"),
        "example_7_earth_interior_prem": ("inferno", "PREM Core/Mantle"),
        "example_8_mars_mola_topography": ("magma", "Mars MOLA"),
        "example_9_moon_lola_topography": ("cividis", "Moon LOLA"),
        "example_10_ocean_crust_age": ("plasma", "Seafloor Age"),
        "example_11_geoid_anomaly": ("jet", "Geoid Anomaly"),
        "example_12_magnetic_anomaly_emag2": ("Spectral", "EMAG2 Magnetic"),
        "example_13_litho1_crust_thickness": ("turbo", "LITHO1.0 Crust"),
        "example_14_mantle_tomography_s40rts": ("seismic", "S40RTS Mantle"),
        "example_15_paleo_cretaceous_66ma": ("gist_earth", "66 Ma KT Boundary"),
        "example_16_paleo_jurassic_150ma": ("gist_earth", "150 Ma Jurassic"),
        "example_17_paleo_devonian_380ma": ("gist_earth", "380 Ma Devonian"),
        "example_18_paleo_cambrian_540ma": ("gist_earth", "540 Ma Cambrian"),
        "example_19_paleo_rodinia_750ma": ("gist_earth", "750 Ma Rodinia"),
        "example_20_venus_magellan_topography": ("hot", "Venus Magellan"),
        "example_21_mercury_messenger_topography": ("bone", "Mercury Relief"),
        "example_22_free_air_gravity": ("Spectral", "Free-Air Gravity"),
        "example_23_crustal_heat_flow": ("afmhot", "Heat Flow"),
        "example_24_dynamic_topography": ("coolwarm", "Dynamic Topo"),
        "example_25_concentric_matryoshka_core": ("inferno", "Matryoshka Core"),
        "example_26_california_fault_lines": ("copper", "Fault Lines"),
        "example_27_ring_of_fire_volcanoes": ("YlOrRd", "Ring of Fire"),
    }

    for p in presets:
        pid = p["id"]
        out_png = os.path.join(THUMBNAILS_DIR, f"{pid}.png")
        cmap_name, subtitle = colormap_defaults.get(pid, ("viridis", p.get("name", pid)))

        fig = plt.figure(figsize=(3.2, 2.0), dpi=90, facecolor="#090d16")
        ax = fig.add_axes([0, 0, 1, 1])
        ax.set_facecolor("#090d16")
        ax.axis("off")

        # Create aesthetic thumbnail visualization
        if "interior" in pid or "matryoshka" in pid or "prem" in pid:
            # Concentric circular cross section
            theta = np.linspace(0, 2 * np.pi, 200)
            for r, c in [(0.9, "#334155"), (0.75, "#b45309"), (0.55, "#ea580c"), (0.35, "#facc15"), (0.15, "#ffffff")]:
                ax.fill(r * np.cos(theta), r * np.sin(theta), color=c, alpha=0.9)
            ax.set_xlim(-1.1, 1.1)
            ax.set_ylim(-1.1, 1.1)
        elif "paleo" in pid:
            # Styled continents pattern
            paleo_wave = np.sin(3 * lat_grid) * np.cos(2 * lon_grid + 0.5) + np.cos(lat_grid)
            ax.imshow(paleo_wave, cmap="gist_earth", extent=[-180, 180, -90, 90], aspect="auto")
        else:
            # Relief / colormap
            ax.imshow(base_topo, cmap=cmap_name, extent=[-180, 180, -90, 90], aspect="auto")

        # Subtle dark gradient overlay at bottom for readability
        ax.axhspan(-90, -40, color="#090d16", alpha=0.7)
        title_text = p.get("name", pid).split(":")[0].replace("Example ", "Ex ")
        ax.text(
            0.05, 0.12, title_text,
            transform=ax.transAxes, color="#f8fafc",
            fontsize=9, fontweight="bold", family="sans-serif",
        )
        ax.text(
            0.05, 0.04, subtitle,
            transform=ax.transAxes, color="#38bdf8",
            fontsize=7, family="sans-serif",
        )

        fig.savefig(out_png, format="png", dpi=90)
        plt.close(fig)
        print(f"Generated thumbnail: {out_png}")

    print("All gallery thumbnails generated successfully.")


if __name__ == "__main__":
    generate_all_preset_thumbnails()

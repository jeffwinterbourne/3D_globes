"""Interactive Jupyter Notebook widgets and GUI components for globe3d.

This module houses interactive frontend controls (built with ipywidgets), keeping
core backend computation and mathematical modules headless and decoupled from GUI dependencies.
"""

import io
from typing import Dict, List, Optional, Sequence, Tuple, Union
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.colors import BoundaryNorm, ListedColormap

from .filaments import (
    apply_banded_colormap,
    create_banded_colormap,
    plot_banded_colormap_preview,
)
from .presets import DEFAULT_ELEVATION_BANDS


class InteractiveColormapBuilder:
    """Interactive Jupyter Widget for designing banded colormaps from physical filaments.

    Allows interactive selection of filament mixtures from an available palette,
    dynamic addition/deletion of elevation bands, custom threshold boundary adjustment,
    and live dual preview of both the discrete colorbar and the 2D equirectangular terrain map.
    """

    def __init__(
        self,
        palette: Sequence[Dict],
        dem_grid: Optional[object] = None,
        default_bands: Optional[Sequence[Dict]] = None,
    ):
        """Initializes an InteractiveColormapBuilder widget.

        Args:
            palette (sequence of dict): Palette items from create_filament_palette.
            dem_grid (GeographicGrid or np.ndarray, optional): Terrain grid for live map preview.
                Defaults to None.
            default_bands (sequence of dict, optional): Initial bands configuration.
                Defaults to rich 8-band geological hypsometric defaults from presets.
        """
        try:
            import ipywidgets as widgets
        except ImportError:
            raise ImportError(
                "InteractiveColormapBuilder requires 'ipywidgets'. "
                "Please install it via Conda or pip: conda install -c conda-forge ipywidgets"
            )

        self._widgets = widgets
        self.palette = list(palette)
        self.dem_grid = dem_grid

        if default_bands is None:
            self.bands_config = [dict(b) for b in DEFAULT_ELEVATION_BANDS]
        else:
            self.bands_config = [dict(b) for b in default_bands]

        self.initial_bands = [dict(b) for b in self.bands_config]
        self._options = [
            (f"[{i:02d}] {p['name']} ({p.get('hex', '')})", i)
            for i, p in enumerate(self.palette)
        ]
        self._build_ui()

    def _sync_state_from_widgets(self):
        """Synchronizes internal bands_config from active input widgets."""
        if not hasattr(self, "rows") or len(self.color_dropdowns) != len(self.bands_config):
            return
        for i, (name_w, color_w, thresh_w) in enumerate(
            zip(self.name_inputs, self.color_dropdowns, self.thresh_inputs)
        ):
            self.bands_config[i]["name"] = name_w.value
            self.bands_config[i]["index"] = color_w.value
            if i < len(self.bands_config) - 1:
                self.bands_config[i]["threshold"] = thresh_w.value
            else:
                self.bands_config[i]["threshold"] = None

    def _rebuild_rows(self):
        """Reconstructs the interactive row widgets for the current bands configuration."""
        widgets = self._widgets
        self.rows = []
        self.color_dropdowns = []
        self.thresh_inputs = []
        self.name_inputs = []
        self.swatch_htmls = []

        n_bands = len(self.bands_config)
        for i, b in enumerate(self.bands_config):
            is_last = (i == n_bands - 1)
            name_w = widgets.Text(
                value=b.get("name", f"Band {i+1}"),
                continuous_update=False,
                layout=widgets.Layout(width="180px"),
            )
            color_w = widgets.Dropdown(
                options=self._options,
                value=b["index"],
                layout=widgets.Layout(width="280px"),
            )
            hex_c = self.palette[b["index"]]["hex"]
            swatch_w = widgets.HTML(
                value=f'<div style="width:24px;height:24px;background-color:{hex_c};border:1px solid #333;border-radius:3px;"></div>',
                layout=widgets.Layout(width="35px"),
            )
            thresh_val = b["threshold"] if b["threshold"] is not None else 0
            thresh_w = widgets.IntText(
                value=thresh_val,
                disabled=is_last,
                continuous_update=False,
                layout=widgets.Layout(width="100px"),
            )

            del_btn = widgets.Button(
                description="✖",
                tooltip="Delete this band",
                button_style="danger",
                disabled=(n_bands <= 2),
                layout=widgets.Layout(width="36px"),
            )
            del_btn.on_click(self._make_delete_handler(i))

            color_w.observe(self._on_change, names="value")
            thresh_w.observe(self._on_change, names="value")
            name_w.observe(self._on_change, names="value")

            self.color_dropdowns.append(color_w)
            self.thresh_inputs.append(thresh_w)
            self.name_inputs.append(name_w)
            self.swatch_htmls.append(swatch_w)

            thresh_label = "Upper (m):" if not is_last else "(Top zone)"
            row = widgets.HBox([
                widgets.Label(f"Band {i+1}:", layout=widgets.Layout(width="55px")),
                name_w,
                color_w,
                swatch_w,
                widgets.Label(thresh_label, layout=widgets.Layout(width="80px")),
                thresh_w,
                del_btn,
            ])
            self.rows.append(row)

        self.rows_box.children = self.rows

    def _make_delete_handler(self, idx: int):
        def handler(_):
            self._delete_band(idx)
        return handler

    def _build_ui(self):
        widgets = self._widgets
        self.rows_box = widgets.VBox([])
        self._rebuild_rows()

        self.add_btn = widgets.Button(
            description="➕ Add Band",
            button_style="success",
            tooltip="Add a new elevation band",
            layout=widgets.Layout(width="130px"),
        )
        self.add_btn.on_click(self._on_add_band)

        self.sort_btn = widgets.Button(
            description="↕ Sort Thresholds",
            button_style="info",
            tooltip="Sort bands in ascending elevation order",
            layout=widgets.Layout(width="145px"),
        )
        self.sort_btn.on_click(self._on_sort_bands)

        self.reset_btn = widgets.Button(
            description="↺ Reset Defaults",
            tooltip="Reset bands to original configuration",
            layout=widgets.Layout(width="140px"),
        )
        self.reset_btn.on_click(self._on_reset_bands)

        action_bar = widgets.HBox(
            [self.add_btn, self.sort_btn, self.reset_btn],
            layout=widgets.Layout(margin="6px 0 10px 0"),
        )

        self.status_label = widgets.HTML(value="")

        # Dedicated single Image preview widget: avoids output stacking and rendering repeats
        self.preview_image = widgets.Image(
            format="png",
            layout=widgets.Layout(max_width="100%", margin="6px 0"),
        )

        self.container = widgets.VBox([
            widgets.HTML(
                "<h4>🎨 Interactive Banded Colormap Builder</h4>"
                "<p style='margin:0 0 6px 0;'>Select filament mixtures, adjust elevation boundaries, "
                "or add/delete bands. Live preview updates automatically:</p>"
            ),
            self.rows_box,
            action_bar,
            self.status_label,
            self.preview_image,
        ])
        self._update_preview()

    def _on_add_band(self, _):
        self._sync_state_from_widgets()
        n = len(self.bands_config)
        if n >= 2 and self.bands_config[-2]["threshold"] is not None:
            prev_thresh = self.bands_config[-2]["threshold"]
            new_thresh = prev_thresh + 1000
        else:
            new_thresh = 0

        used_indices = {b["index"] for b in self.bands_config}
        next_idx = 0
        for idx in range(len(self.palette)):
            if idx not in used_indices:
                next_idx = idx
                break
        else:
            next_idx = (self.bands_config[-1]["index"] + 1) % len(self.palette)

        new_band = {
            "index": next_idx,
            "threshold": new_thresh,
            "name": f"New Zone {n}",
        }
        self.bands_config.insert(-1, new_band)
        self._rebuild_rows()
        self._update_preview()

    def _delete_band(self, idx: int):
        if len(self.bands_config) <= 2:
            return
        self._sync_state_from_widgets()
        self.bands_config.pop(idx)
        self.bands_config[-1]["threshold"] = None
        self._rebuild_rows()
        self._update_preview()

    def _on_sort_bands(self, _):
        self._sync_state_from_widgets()
        top_band = self.bands_config[-1]
        other_bands = sorted(self.bands_config[:-1], key=lambda b: b["threshold"])
        self.bands_config = other_bands + [top_band]
        self._rebuild_rows()
        self._update_preview()

    def _on_reset_bands(self, _):
        self.bands_config = [dict(b) for b in self.initial_bands]
        self._rebuild_rows()
        self._update_preview()

    def _on_change(self, change):
        for drop, swatch in zip(self.color_dropdowns, self.swatch_htmls):
            hex_c = self.palette[drop.value]["hex"]
            swatch.value = f'<div style="width:24px;height:24px;background-color:{hex_c};border:1px solid #333;border-radius:3px;"></div>'
        self._update_preview()

    def get_colormap(self) -> Tuple[ListedColormap, BoundaryNorm, List[Tuple[int, int, int]], List[float], List[str]]:
        """Returns the currently configured colormap, norm, colors, thresholds, and labels.

        Returns:
            tuple: (cmap, norm, selected_colors, thresholds, band_names).
        """
        self._sync_state_from_widgets()
        colors = [self.palette[b["index"]]["color"] for b in self.bands_config]
        thresholds = [float(b["threshold"]) for b in self.bands_config[:-1]]
        band_names = [b["name"] for b in self.bands_config]
        cmap, norm = create_banded_colormap(colors, thresholds)
        return cmap, norm, colors, thresholds, band_names

    def _update_preview(self):
        self._sync_state_from_widgets()
        thresh_vals = [self.bands_config[i]["threshold"] for i in range(len(self.bands_config) - 1)]
        is_ascending = all(x < y for x, y in zip(thresh_vals[:-1], thresh_vals[1:])) if len(thresh_vals) > 1 else True

        if not is_ascending:
            self.status_label.value = (
                '<div style="color:#d9534f;font-weight:bold;margin:4px 0;">'
                '⚠️ Warning: Thresholds must be in strictly ascending order for printing. '
                'Click "↕ Sort Thresholds" to fix.</div>'
            )
        else:
            self.status_label.value = ""

        if is_ascending:
            valid_thresh = [float(t) for t in thresh_vals]
        else:
            valid_thresh = sorted([float(t) for t in thresh_vals])
            for k in range(1, len(valid_thresh)):
                if valid_thresh[k] <= valid_thresh[k - 1]:
                    valid_thresh[k] = valid_thresh[k - 1] + 1.0

        colors = [self.palette[b["index"]]["color"] for b in self.bands_config]
        band_names = [b["name"] for b in self.bands_config]

        try:
            cmap, norm = create_banded_colormap(colors, valid_thresh)
        except Exception as e:
            self.status_label.value = f'<div style="color:#d9534f;">Colormap error: {e}</div>'
            return

        has_grid = self.dem_grid is not None
        fig_rows = 2 if has_grid else 1
        # Generous height ratio for 2D equirectangular map preview
        fig, axes = plt.subplots(
            fig_rows, 1,
            figsize=(14, 8 if has_grid else 1.8),
            height_ratios=[1, 4] if has_grid else None,
            dpi=100
        )
        try:
            if not has_grid:
                ax_cbar = axes
            else:
                ax_cbar, ax_map = axes[0], axes[1]

            plot_banded_colormap_preview(
                cmap, norm, valid_thresh, band_labels=band_names, ax=ax_cbar, title="Interactive Banded Colorbar"
            )

            if has_grid:
                if isinstance(self.dem_grid, np.ndarray):
                    raw_arr = self.dem_grid
                elif hasattr(self.dem_grid, "data") and isinstance(self.dem_grid.data, np.ndarray):
                    raw_arr = self.dem_grid.data
                else:
                    raw_arr = np.asarray(self.dem_grid)

                step_y = max(1, raw_arr.shape[0] // 200)
                step_x = max(1, raw_arr.shape[1] // 400)
                sub = raw_arr[::step_y, ::step_x]
                img = apply_banded_colormap(sub, colors, valid_thresh, flip_y=True)
                ax_map.imshow(img)
                ax_map.set_title("Live 2D Map Preview (North at Top)", fontsize=9, fontweight="bold")
                ax_map.axis("off")

            plt.tight_layout()
            buf = io.BytesIO()
            fig.savefig(buf, format="png", bbox_inches="tight")
            self.preview_image.value = buf.getvalue()
        finally:
            plt.close(fig)

    def show(self):
        """Displays the interactive widget in the Jupyter notebook."""
        from IPython.display import display
        display(self.container)

    def _ipython_display_(self):
        from IPython.display import display
        display(self.container)

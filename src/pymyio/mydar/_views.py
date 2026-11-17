"""Charts of a myDAR walk (R ``mydar_*_view()`` and ``mydar_dashboard()``)."""

from __future__ import annotations

import base64
import math
import uuid
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

import numpy as np
import pandas as pd

from ..chart import MyIO, link_charts, pointcloud_mesh, pointcloud_terrain
from ._read import MYDAR_CLASSES, MydarWalk, _check_flag

Line = Dict[str, np.ndarray]


def mydar_plan_view(walk: MydarWalk, profile: Optional[Mapping[str, Sequence[float]]] = None,
                    points: Optional[bool] = None, height: str = "460px") -> MyIO:
    """The walk from above: the orthophoto with the track, point features and,
    when ``profile`` is given (``{"from": (x, y), "to": (x, y)}``), the profile
    line on it, drawn to scale with the walk's Shape and Map accuracy as a
    caption. ``points`` draws the points, colored by class, small and
    translucent over the orthophoto; it defaults to True only when the walk
    has no orthophoto. Brushing the plan view selects these points.
    """
    pts = _need(walk, "points", "mydar_plan_view")
    if points is None:
        points = walk.orthophoto is None
    _check_flag(points, "points", "mydar_plan_view")
    pts = pts.sort_values("class", kind="stable")

    w = _add_orthophoto(MyIO(title="Plan view", height=height), walk)
    if points:
        w.add_layer(type="point", label="points", data=_rows(pts),
                    color=_class_colors(pts["class"]),
                    mapping={"x_var": "x", "y_var": "y", "group": "class_name"},
                    options={"pointRadius": 2} if walk.orthophoto is None
                    else {"pointRadius": 1.2, "opacity": 0.45})
    _add_track(w, walk)
    features = _feature_points(walk)
    if features is not None:
        w.add_layer(type="point", label="Features", data=_rows(features), color="#CC79A7",
                    mapping={"x_var": "x", "y_var": "y"})
    if profile is not None:
        line = _check_line(profile.get("from"), profile.get("to"), "mydar_plan_view")
        w.add_layer(type="line", label="Profile line", color="#0072B2",
                    data=[{"x": float(line["from"][0]), "y": float(line["from"][1])},
                          {"x": float(line["to"][0]), "y": float(line["to"][1])}],
                    mapping={"x_var": "x", "y_var": "y"},
                    options={"curveType": "linear", "showPoints": False})
    return _plan_axes(_add_caption(w, walk), walk)


def mydar_orthophoto_view(walk: MydarWalk, height: str = "460px") -> MyIO:
    """The orthophoto alone, to scale, with the track."""
    _check_walk(walk, "mydar_orthophoto_view")
    if walk.orthophoto is None:
        raise ValueError("mydar_orthophoto_view(): this walk has no orthophoto.")
    w = _add_orthophoto(MyIO(title="Orthophoto", height=height), walk)
    _add_track(w, walk)
    _add_caption(w, walk)
    w.suppress_legend()
    return _plan_axes(w, walk)


def mydar_terrain_view(walk: MydarWalk, hillshade: bool = True, azimuth: float = 315,
                       altitude: float = 45, height: str = "420px") -> MyIO:
    """The DEM as a ``raster`` layer, colored by height and, by default, shaded
    by a hillshade lit from ``azimuth`` (degrees clockwise from north) and
    ``altitude`` (degrees above the horizon), to scale.
    """
    terrain = _need(walk, "terrain", "mydar_terrain_view")
    _check_flag(hillshade, "hillshade", "mydar_terrain_view")
    cell = terrain.attrs.get("cell_size")
    mapping = {"x_var": "x", "y_var": "y", "value": "z"}
    terrain = terrain.copy()
    if hillshade:
        terrain["shade"] = _hillshade(terrain, cell, azimuth, altitude)
        mapping["shade"] = "shade"
    options = {"cellWidth": cell[0], "cellHeight": cell[1]} if cell is not None and len(cell) == 2 else {}
    w = MyIO(title="Terrain (DEM, hillshaded)" if hillshade else "Terrain (DEM)", height=height)
    w.add_layer(type="raster", label="Height", data=_rows(terrain), mapping=mapping,
                options=options)
    return _plan_axes(w, walk)


def mydar_profile(walk: MydarWalk, from_: Optional[Sequence[float]] = None,
                  to: Optional[Sequence[float]] = None, width: float = 0.5) -> pd.DataFrame:
    """Points within ``width / 2`` meters of the line from ``from_`` to ``to``.

    Returns the corridor points with ``distance`` (meters along the line) and
    ``offset`` (meters left of the line, negative to the right) ahead of the
    point columns, ordered along the line; ``attrs["line"]`` holds the line.
    When both ends are None, the line crosses the track at its midpoint and
    spans the point cloud.
    """
    pts = _need(walk, "points", "mydar_profile")
    if not _is_real(width) or not math.isfinite(width) or width <= 0:
        raise ValueError("mydar_profile(): `width` must be a single positive number of meters.")
    if from_ is None and to is None:
        line = _default_profile(walk)
    else:
        line = _check_line(from_, to, "mydar_profile")
    along, offset, length = _line_frame(line, pts["x"].to_numpy(), pts["y"].to_numpy())
    keep = (along >= 0) & (along <= length) & (np.abs(offset) <= width / 2)
    out = pd.concat([pd.DataFrame({"distance": along[keep], "offset": offset[keep]}),
                     pts[keep].reset_index(drop=True)], axis=1)
    out = out.sort_values("distance", kind="stable").reset_index(drop=True)
    out.attrs["line"] = line
    return out


def mydar_profile_view(walk: MydarWalk, from_: Optional[Sequence[float]] = None,
                       to: Optional[Sequence[float]] = None, width: float = 0.5,
                       height: str = "360px") -> MyIO:
    """The profile as height against distance along the line, points colored by
    class, with the DEM height along the same line."""
    prof = mydar_profile(walk, from_=from_, to=to, width=width)
    if len(prof) == 0:
        raise ValueError(f"mydar_profile_view(): no points within {width / 2:g} m of the profile line.")
    line = prof.attrs["line"]
    prof = prof.sort_values("class", kind="stable")

    w = MyIO(title=f"Profile ({width:.1f} m corridor)", height=height)
    w.add_layer(type="point", label="points", data=_rows(prof), color=_class_colors(prof["class"]),
                mapping={"x_var": "distance", "y_var": "z", "group": "class_name"})
    dem = _terrain_profile(walk.terrain, line)
    if dem is not None and len(dem) > 1:
        w.add_layer(type="line", label="DEM", data=_rows(dem), color="#111827",
                    mapping={"x_var": "distance", "y_var": "z"},
                    options={"curveType": "linear", "showPoints": False})
    return w.set_axis_format(
        x_format=".1f", y_format=".2f", x_label="Distance along line (m)",
        y_label="Height above lowest ground (m)" if _is_local(walk, "z") else "Height (m)",
    )


def mydar_trajectory_view(walk: MydarWalk, height: str = "320px") -> MyIO:
    """The 95% map-position radius along the walk over time, with each GPS
    fix's reported horizontal accuracy."""
    tp = _need(walk, "track_points", "mydar_trajectory_view")
    tp = tp[np.isfinite(tp["t_s"]) & np.isfinite(tp["map_95_m"])].sort_values("t_s", kind="stable")
    w = MyIO(title="Map position uncertainty along the walk", height=height)
    w.add_layer(type="line", label="Map position 95%", data=_rows(tp), color="#0072B2",
                mapping={"x_var": "t_s", "y_var": "map_95_m"})
    gps = walk.gps_fixes
    if gps is not None:
        gps = gps[np.isfinite(gps["t_s"]) & np.isfinite(gps["h_acc_m"])]
        if len(gps) > 0:
            w.add_layer(type="point", label="GPS horizontal accuracy", data=_rows(gps),
                        color="#E69F00", mapping={"x_var": "t_s", "y_var": "h_acc_m"})
    return w.set_axis_format(x_format=".1f", y_format=".1f", x_label="Time since start (s)",
                             y_label="Meters")


def mydar_sigma_view(walk: MydarWalk, height: str = "320px") -> MyIO:
    """The distribution of per-point ``sigma_m`` for LiDAR and camera points, on
    a log10 axis because camera sigma can be a hundred times LiDAR's."""
    pts = _need(walk, "points", "mydar_sigma_view")
    pts = pts.loc[np.isfinite(pts["sigma_m"]) & (pts["sigma_m"] > 0), ["source", "sigma_m"]]
    order = {s: i for i, s in enumerate(s for s in ("LiDAR", "camera") if s in set(pts["source"]))}
    pts = pts[pts["source"].isin(order)]
    pts = pts.iloc[np.argsort(pts["source"].map(order).to_numpy(), kind="stable")].copy()
    pts["log10_sigma_m"] = np.log10(pts["sigma_m"])
    w = MyIO(title="Point sigma by source", height=height)
    w.add_layer(type="violin", label="log10 sigma_m", color="#009E73", data=_rows(pts),
                mapping={"x_var": "source", "y_var": "log10_sigma_m"},
                options={"showBox": True, "showMedian": True})
    return w.set_axis_format(y_format=".1f", x_label="Source",
                             y_label="log10 sigma_m (-2 = 1 cm, 0 = 1 m)")


def mydar_accuracy_view(walk: MydarWalk, height: str = "320px") -> MyIO:
    """The accuracy table's 95% figures: shape (by range band) against map
    position, and held-out pin misses when the walk used pins."""
    figures = _accuracy_figures(walk)
    if len(figures) == 0:
        raise ValueError("mydar_accuracy_view(): the walk's accuracy table has no 95% figures.")
    w = MyIO(title="Accuracy figures (95%)", height=height)
    w.add_layer(type="lollipop", label="95% (m)", color="#0072B2", data=_rows(figures),
                mapping={"x_var": "figure", "y_var": "value_m"})
    w.define_categorical_axis(x_axis=True)
    return w.set_axis_format(y_format=".2f", x_label="", y_label="Meters")


def mydar_gps_view(walk: MydarWalk, height: str = "320px") -> MyIO:
    """Each GPS fix's residual against the fused track, with the 95% residual
    the processing expected."""
    gps = _need(walk, "gps_fixes", "mydar_gps_view")
    gps = gps[np.isfinite(gps["t_s"]) & np.isfinite(gps["residual_m"])]
    if len(gps) == 0:
        raise ValueError("mydar_gps_view(): no GPS fix has a residual.")
    gps = gps.sort_values("t_s", kind="stable").copy()
    gps["status"] = np.where(gps["used"] == 1, "Used", "Ignored")
    status_colors = {"Used": "#0072B2", "Ignored": "#D55E00"}
    w = MyIO(title="GPS residuals", height=height)
    w.add_layer(type="point", label="residuals", data=_rows(gps),
                color=[status_colors[s] for s in pd.unique(gps["status"])],
                mapping={"x_var": "t_s", "y_var": "residual_m", "group": "status"})
    bound = gps[np.isfinite(gps["residual_95_m"])]
    if len(bound) > 1:
        w.add_layer(type="line", label="Expected 95%", data=_rows(bound), color="#6B7280",
                    mapping={"x_var": "t_s", "y_var": "residual_95_m"})
    return w.set_axis_format(x_format=".1f", y_format=".2f", x_label="Time since start (s)",
                             y_label="Residual (m)")


def mydar_cloud_view(walk: MydarWalk, points: Optional[pd.DataFrame] = None, color: str = "rgb",
                     mode: str = "3d", point_size: float = 2, ortho: bool = True,
                     profile: Optional[Mapping[str, Sequence[float]]] = None,
                     selectable: bool = True, surface: str = "points", slider: bool = True,
                     height: str = "560px") -> MyIO:
    """Map view of the walk in 2D and 3D: one WebGL viewer (``pointcloud``).

    Laid out like the myDAR app's Results map:

    - a 2D / 3D switch on one canvas. 2D is the plan over the orthophoto with
      a scale bar; 3D is the cloud with the orthophoto draped on the DEM, so
      imagery and points line up in one scene.
    - layer chips that switch on and off independently: LiDAR, Camera (when
      the walk has camera points), Classes and Ortho; and a Photo / Height /
      Sigma choice of point color.
    - in 3D, a Points / Mesh switch when the walk has a mesh (``surface`` sets
      the start), drawn in its vertex colors.
    - the track with its uncertainty band (light to dark orange as the
      map-position uncertainty rises), the ``profile`` line
      (``{"from": (x, y), "to": (x, y)}``) and the accuracy card.
    - in 2D, a Select tool (``selectable``): the rectangle's ``walk.points``
      are sent on ``point_id`` to linked charts, e.g. the profile.
    - when the walk has a track of two or more points, the app's slider
      along the walk (``slider=False`` hides it). In 3D it turns the view
      about that point of the walk and cuts away what lies in front of it,
      so a wall does not hide the room behind; Whole walk goes back to the
      full scan. In 2D it centers the plan on the point and marks it.

    ``points`` defaults to ``walk.points``; pass :func:`mydar_iphone_cloud`
    or ``read_mydar_points(path, max_points=math.inf)`` for a denser cloud.
    ``mode`` is ``"3d"`` or ``"plan"`` (2D). Controls: drag to rotate (2D:
    pan), shift-drag or right-drag to pan, scroll or pinch to zoom,
    double-click to reset.
    """
    _check_walk(walk, "mydar_cloud_view")
    pts = _need(walk, "points", "mydar_cloud_view") if points is None else points
    if (not isinstance(pts, pd.DataFrame) or not {"x", "y", "z"} <= set(pts.columns)
            or len(pts) == 0):
        raise ValueError("mydar_cloud_view(): `points` must be a data frame with x, y and z.")
    if color not in ("rgb", "class", "height", "sigma"):
        raise ValueError("mydar_cloud_view(): `color` must be one of 'rgb', 'class', 'height', 'sigma'.")
    if mode not in ("3d", "plan"):
        raise ValueError("mydar_cloud_view(): `mode` must be '3d' or 'plan'.")
    if surface not in ("points", "mesh"):
        raise ValueError("mydar_cloud_view(): `surface` must be 'points' or 'mesh'.")
    _check_flag(ortho, "ortho", "mydar_cloud_view")
    _check_flag(selectable, "selectable", "mydar_cloud_view")
    _check_flag(slider, "slider", "mydar_cloud_view")
    if not _is_real(point_size) or not math.isfinite(point_size) or point_size <= 0:
        raise ValueError("mydar_cloud_view(): `point_size` must be a single positive number.")

    mapping = {"x_var": "x", "y_var": "y", "z_var": "z"}
    if {"r", "g", "b"} <= set(pts.columns):
        mapping.update({"red": "r", "green": "g", "blue": "b"})
    if "class" in pts.columns:
        mapping["class"] = "class"
    if "sigma_m" in pts.columns:
        mapping["sigma"] = "sigma_m"
    if "source" in pts.columns:
        mapping["source"] = "source"
    if color == "rgb" and "red" not in mapping:
        color = "class"

    present_codes = set(pts["class"].unique()) if "class" in pts.columns else set()
    present = MYDAR_CLASSES[MYDAR_CLASSES["class"].isin(present_codes)]
    options: Dict[str, Any] = {
        "color": color, "mode": mode, "pointSize": point_size, "surface": surface,
        "slider": slider,
        "classColors": {str(c): col for c, col in zip(present["class"], present["color"])},
        "classNames": {str(c): n for c, n in zip(present["class"], present["class_name"])},
        "caption": _caption(walk),
    }
    if walk.track is not None and len(walk.track) > 1:
        tr = walk.track[np.isfinite(walk.track["x"]) & np.isfinite(walk.track["z"])]
        options["track"] = [[float(x), float(y), float(z)]
                            for x, y, z in zip(tr["x"], tr["y"], tr["z"])]
    band = _track_band(walk)
    if band is not None:
        options["trackBand"] = band
    if walk.terrain is not None and len(walk.terrain) > 0:
        options["terrain"] = pointcloud_terrain(walk.terrain)
    if walk.mesh is not None and len(walk.mesh["faces"]) > 0:
        options["mesh"] = pointcloud_mesh(walk.mesh["vertices"], walk.mesh["faces"])
    if ortho and walk.orthophoto is not None:
        ground_z = walk.terrain["z"] if walk.terrain is not None else pts["z"]
        e = walk.orthophoto["extent"]
        options["ortho"] = {
            "src": _png_data_url(walk.orthophoto["png"]),
            "extent": [e["xmin"], e["xmax"], e["ymin"], e["ymax"]],
            "z": float(np.nanmin(ground_z)) - 0.02,
        }
    if profile is not None:
        line = _check_line(profile.get("from"), profile.get("to"), "mydar_cloud_view")
        options["profile"] = [line["from"].tolist(), line["to"].tolist()]
    if selectable and walk.points is not None and "point_id" in walk.points.columns:
        sp = walk.points
        options["selectable"] = {
            "key": "point_id", "ids": [int(i) for i in sp["point_id"]],
            "x": np.round(sp["x"].to_numpy(dtype=float), 3).tolist(),
            "y": np.round(sp["y"].to_numpy(dtype=float), 3).tolist(),
        }

    w = MyIO(height=height)
    w.add_layer(type="pointcloud", label="Point cloud", data=pts, mapping=mapping, options=options)
    w.set_margin(top=0, bottom=0, left=0, right=0)
    w.suppress_axis(x_axis=True, y_axis=True)
    return w.suppress_legend()


class MydarDashboard:
    """A walk laid out on one page, as :func:`mydar_dashboard` builds it.

    ``sections`` is a list of ``(heading, [(chart, wide), ...])``. Use
    :meth:`to_html` for a self-contained page, :meth:`save` to write it, or
    show it in a notebook (it renders in an iframe).
    """

    def __init__(self, sections: List[Tuple[str, List[Tuple[MyIO, bool]]]]):
        self.sections = sections

    @property
    def charts(self) -> List[MyIO]:
        """Every chart on the page, in page order."""
        return [chart for _, cells in self.sections for chart, _ in cells]

    def to_html(self, title: str = "myDAR walk") -> str:
        """A self-contained HTML page with the engine inlined once."""
        from ..standalone import _escape_script_body, _load_assets, _safe_json

        assets = _load_assets()

        def script(key: str) -> str:
            return "<script>" + _escape_script_body(assets[key].decode("utf-8")) + "</script>"

        body: List[str] = ['<div class="mydar-dashboard">']
        configs: List[str] = []
        for heading, cells in self.sections:
            body.append(f'<h3 class="mydar-heading">{_escape(heading)}</h3>')
            for chart, wide in cells:
                uid = uuid.uuid4().hex[:12]
                cls = "mydar-cell mydar-wide" if wide else "mydar-cell"
                body.append(
                    f'<div class="{cls}"><div id="pymyio-chart-{uid}" class="pymyio-chart" '
                    f'style="width:100%;height:{_escape(_css_size(chart.height))}"></div></div>'
                )
                configs.append(
                    f'<script type="application/json" id="pymyio-config-{uid}">'
                    f"{_safe_json(chart.to_config())}</script>"
                )
        body.append("</div>")
        init = (
            "<script>(function(){"
            # The engine's hover code reads HTMLWidgets.shinyMode, which only
            # exists in htmlwidgets hosts.
            "window.HTMLWidgets=window.HTMLWidgets||{shinyMode:false};"
            "document.querySelectorAll('script[id^=\"pymyio-config-\"]').forEach(function(s){"
            "var el=document.getElementById(s.id.replace('pymyio-config-','pymyio-chart-'));"
            "var r=el.getBoundingClientRect();"
            "new window.myIOchart({element:el,config:JSON.parse(s.textContent),"
            "width:r.width||600,height:r.height||400});"
            "});})();</script>"
        )
        css = _escape_script_body(assets["style.css"].decode("utf-8"))
        return "".join([
            '<!doctype html><html><head><meta charset="utf-8">',
            '<meta name="viewport" content="width=device-width, initial-scale=1">',
            f"<title>{_escape(title)}</title>",
            f"<style>{css}{_DASHBOARD_CSS}</style></head><body>",
            *body, *configs,
            script("lib/d3.min.js"), script("lib/d3-hexbin.js"), script("lib/d3-sankey.min.js"),
            script("myIOapi.js"), init, "</body></html>",
        ])

    def save(self, path: str, title: str = "myDAR walk") -> str:
        """Write :meth:`to_html` to ``path`` and return the path."""
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(self.to_html(title=title))
        return path

    def _repr_html_(self) -> str:
        page = self.to_html().replace("&", "&amp;").replace('"', "&quot;")
        return (f'<iframe srcdoc="{page}" style="width:100%;height:1900px;border:0" '
                'sandbox="allow-scripts"></iframe>')


_DASHBOARD_CSS = (
    "body{margin:16px;background:#fff;}"
    ".mydar-dashboard{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:16px;}"
    ".mydar-cell{min-width:0;}"
    ".mydar-wide{grid-column:1/-1;}"
    ".mydar-heading{grid-column:1/-1;margin:12px 0 0;font:600 18px/1.3 system-ui,sans-serif;"
    "color:#1d2430;}"
    "@media (max-width:800px){.mydar-dashboard{grid-template-columns:minmax(0,1fr);}}"
)


def mydar_dashboard(walk: MydarWalk, points: Optional[pd.DataFrame] = None,
                    profile: Optional[Mapping[str, Sequence[float]]] = None,
                    width: float = 0.5) -> MydarDashboard:
    """Lay out a walk the way the myDAR app's Results screen does.

    One map viewer first (:func:`mydar_cloud_view`: the 2D plan over the
    orthophoto or the 3D cloud with the orthophoto draped on the DEM, with the
    track's uncertainty band, the profile line and the Shape / Map accuracy
    card), the profile below it, then the quality charts (map-position
    uncertainty, GPS residuals, point sigma, accuracy figures, terrain). In
    the viewer's 2D mode the Select tool picks points and the profile
    highlights the same ones. When the walk has GPS residuals, the GPS chart
    shares a time cursor with the uncertainty chart. ``profile`` defaults to a
    line across the track at its midpoint.
    """
    if profile is None:
        line = _default_profile(walk)
    else:
        line = _check_line(profile.get("from"), profile.get("to"), "mydar_dashboard")

    viewer, prof = link_charts(
        mydar_cloud_view(walk, points=points, profile=line, height="600px"),
        mydar_profile_view(walk, from_=line["from"], to=line["to"], width=width),
        on="point_id", group=f"mydar_points_{uuid.uuid4().hex[:8]}",
    )
    gps = walk.gps_fixes
    has_gps = (gps is not None and "residual_m" in gps.columns
               and bool(np.isfinite(gps["residual_m"]).any()))
    if has_gps:
        time_charts = list(link_charts(
            mydar_trajectory_view(walk), mydar_gps_view(walk),
            on="t_s", group=f"mydar_time_{uuid.uuid4().hex[:8]}", cursor=True,
        ))
    else:
        time_charts = [mydar_trajectory_view(walk)]
    quality = [(chart, False) for chart in time_charts]
    quality += [(mydar_sigma_view(walk), False), (mydar_accuracy_view(walk), False)]
    if walk.terrain is not None:
        quality.append((mydar_terrain_view(walk), False))
    return MydarDashboard([
        ("Map", [(viewer, True)]),
        ("Profile", [(prof, True)]),
        ("Quality", quality),
    ])


# ---- helpers -----------------------------------------------------------------


def _check_walk(walk: Any, caller: str) -> None:
    if not isinstance(walk, MydarWalk):
        raise TypeError(f"{caller}(): `walk` must be a MydarWalk from read_mydar_walk().")


def _need(walk: Any, part: str, caller: str) -> pd.DataFrame:
    _check_walk(walk, caller)
    df = getattr(walk, part)
    if df is None or len(df) == 0:
        raise ValueError(f"{caller}(): this walk has no {part}.")
    return df


def _is_real(v: Any) -> bool:
    return isinstance(v, (int, float, np.integer, np.floating)) and not isinstance(v, bool)


def _rows(df: pd.DataFrame) -> List[dict]:
    """Rows as dicts with missing cells left out, as jsonlite writes R rows."""
    out = []
    for row in df.to_dict(orient="records"):
        out.append({k: (v.item() if isinstance(v, np.generic) else v) for k, v in row.items()
                    if not (v is None or (isinstance(v, float) and math.isnan(v)))})
    return out


def _class_colors(class_codes: pd.Series) -> List[str]:
    lookup = dict(zip(MYDAR_CLASSES["class"], MYDAR_CLASSES["color"]))
    return [lookup.get(int(c), "#999999") for c in sorted(pd.unique(class_codes))]


def _is_local(walk: MydarWalk, axis: str) -> bool:
    """True when the walk's coordinates on this axis were moved to a local
    origin (a known shift, or one withheld as NaN)."""
    o = walk.origin.get(axis)
    return o is not None and (math.isnan(o) or o != 0)


def _axis_label(walk: MydarWalk, axis: str) -> str:
    name = "Easting" if axis == "x" else "Northing"
    return f"{name} from walk origin (m)" if _is_local(walk, axis) else f"{name} (m)"


def _plan_axes(w: MyIO, walk: MydarWalk) -> MyIO:
    w.set_equal_aspect()
    return w.set_axis_format(x_format=".0f", y_format=".0f", x_label=_axis_label(walk, "x"),
                             y_label=_axis_label(walk, "y"))


def _add_track(w: MyIO, walk: MydarWalk) -> None:
    if walk.track is not None and len(walk.track) > 1:
        w.add_layer(type="line", label="Track", data=_rows(walk.track), color="#1d2430",
                    mapping={"x_var": "x", "y_var": "y"},
                    options={"curveType": "linear", "showPoints": False})


def _feature_points(walk: MydarWalk) -> Optional[pd.DataFrame]:
    rows = []
    for name, df in walk.features.items():
        df = df[np.isfinite(df["x"]) & np.isfinite(df["y"])]
        if len(df) > 0:
            rows.append(pd.DataFrame({"layer": name, "x": df["x"].to_numpy(),
                                      "y": df["y"].to_numpy()}))
    return pd.concat(rows, ignore_index=True) if rows else None


def _check_line(from_: Any, to: Any, caller: str) -> Line:
    def ok(p: Any) -> bool:
        try:
            a = np.asarray(p, dtype=np.float64)
        except (TypeError, ValueError):
            return False
        return a.shape == (2,) and bool(np.isfinite(a).all())

    if not ok(from_) or not ok(to):
        raise ValueError(f"{caller}(): profile `from` and `to` must each be (x, y).")
    a, b = np.asarray(from_, dtype=np.float64), np.asarray(to, dtype=np.float64)
    if np.allclose(a, b, rtol=1.5e-8, atol=0):
        raise ValueError(f"{caller}(): profile `from` and `to` are the same point.")
    return {"from": a, "to": b}


def _line_frame(line: Line, x: np.ndarray, y: np.ndarray) -> Tuple[np.ndarray, np.ndarray, float]:
    d = line["to"] - line["from"]
    length = float(np.sqrt(np.sum(d ** 2)))
    u = d / length
    rx, ry = x - line["from"][0], y - line["from"][1]
    return rx * u[0] + ry * u[1], -rx * u[1] + ry * u[0], length


def _default_profile(walk: MydarWalk) -> Line:
    """Across the track at its midpoint, long enough to span the cloud."""
    pts = _need(walk, "points", "mydar_default_profile")
    track = walk.track
    if (track is not None and len(track) > 1
            and np.isfinite(track[["x", "y"]].to_numpy()).all()):
        a = np.array([track["x"].iloc[0], track["y"].iloc[0]], dtype=np.float64)
        b = np.array([track["x"].iloc[-1], track["y"].iloc[-1]], dtype=np.float64)
    else:
        ym = (pts["y"].min() + pts["y"].max()) / 2
        a = np.array([pts["x"].min(), ym], dtype=np.float64)
        b = np.array([pts["x"].max(), ym], dtype=np.float64)
    if np.allclose(a, b, rtol=1.5e-8, atol=0):
        b = a + np.array([0.0, 1.0])
    mid = (a + b) / 2
    direction = (b - a) / np.sqrt(np.sum((b - a) ** 2))
    perp = np.array([direction[1], -direction[0]])
    reach = float(np.max(np.abs((pts["x"].to_numpy() - mid[0]) * perp[0]
                                + (pts["y"].to_numpy() - mid[1]) * perp[1])))
    return {"from": mid - perp * reach, "to": mid + perp * reach}


def _terrain_profile(terrain: Optional[pd.DataFrame], line: Line) -> Optional[pd.DataFrame]:
    """DEM height along the line at one-cell steps (nearest cell)."""
    if terrain is None or len(terrain) == 0:
        return None
    cell = terrain.attrs.get("cell_size")
    if cell is None or len(cell) != 2:
        step = float(np.min(np.diff(np.sort(terrain["x"].unique()))))
        cell = [step, step]
    x0, y0 = terrain["x"].min(), terrain["y"].min()

    def key(x: np.ndarray, y: np.ndarray) -> np.ndarray:
        return np.round((x - x0) / cell[0]) * 1e6 + np.round((y - y0) / cell[1])

    lookup = pd.Series(terrain["z"].to_numpy(), index=key(terrain["x"].to_numpy(),
                                                          terrain["y"].to_numpy()))
    lookup = lookup[~lookup.index.duplicated()]
    length = float(np.sqrt(np.sum((line["to"] - line["from"]) ** 2)))
    d = np.arange(0, length + 1e-10 * length, min(cell))
    d = d[d <= length]
    u = (line["to"] - line["from"]) / length
    z = lookup.reindex(key(line["from"][0] + d * u[0], line["from"][1] + d * u[1])).to_numpy()
    out = pd.DataFrame({"distance": d, "z": z})
    return out[np.isfinite(out["z"])].reset_index(drop=True)


def _hillshade(terrain: pd.DataFrame, cell: Optional[Sequence[float]], azimuth: float = 315,
               altitude: float = 45) -> np.ndarray:
    """Lambert hillshade (0-1) from central differences on the cell grid; edge
    and missing neighbors count as level."""
    for v in (azimuth, altitude):
        if not _is_real(v) or not math.isfinite(v):
            raise ValueError(
                "mydar_terrain_view(): `azimuth` and `altitude` must be single numbers of degrees."
            )
    x, y, zc = (terrain[c].to_numpy(dtype=np.float64) for c in ("x", "y", "z"))
    if cell is None or len(cell) != 2:
        cell = [float(np.min(np.diff(np.sort(np.unique(x))))),
                float(np.min(np.diff(np.sort(np.unique(y)))))]
    col = np.round((x - x.min()) / cell[0]).astype(np.int64) + 1
    row = np.round((y - y.min()) / cell[1]).astype(np.int64) + 1
    pad = np.full((row.max() + 2, col.max() + 2), np.nan)
    pad[row, col] = zc

    def at(dr: int, dc: int) -> np.ndarray:
        v = pad[row + dr, col + dc]
        return np.where(np.isnan(v), zc, v)

    dzdx = (at(0, 1) - at(0, -1)) / (2 * cell[0])
    dzdy = (at(1, 0) - at(-1, 0)) / (2 * cell[1])
    az, alt = math.radians(azimuth), math.radians(altitude)
    sun = (math.sin(az) * math.cos(alt), math.cos(az) * math.cos(alt), math.sin(alt))
    norm = np.sqrt(dzdx ** 2 + dzdy ** 2 + 1)
    return np.maximum(0, (-dzdx * sun[0] - dzdy * sun[1] + sun[2]) / norm)


_ACCURACY_SPEC = (
    ("shape_95_within_5m_m", "Shape <5 m", "shape"),
    ("shape_95_5_to_10m_m", "Shape 5-10 m", "shape"),
    ("shape_95_10_to_15m_m", "Shape 10-15 m", "shape"),
    ("shape_95_5_to_15m_m", "Shape 5-15 m", "shape"),
    ("map_95_m", "Map median", "map position"),
    ("map_95_max_m", "Map max", "map position"),
    ("loo_stated_95_m", "Pins stated", "pins"),
    ("loo_worst_miss_m", "Pins worst miss", "pins"),
)


def _accuracy_number(acc: Optional[pd.DataFrame], col: str) -> float:
    if acc is None or len(acc) == 0 or col not in acc.columns:
        return math.nan
    try:
        return float(acc[col].iloc[0])
    except (TypeError, ValueError):
        return math.nan


def _accuracy_figures(walk: MydarWalk) -> pd.DataFrame:
    rows = []
    for col, figure, kind in _ACCURACY_SPEC:
        value = _accuracy_number(walk.accuracy, col)
        if math.isfinite(value):
            rows.append({"figure": figure, "kind": kind, "value_m": value})
    return pd.DataFrame(rows, columns=["figure", "kind", "value_m"])


def _png_data_url(png: bytes) -> str:
    return "data:image/png;base64," + base64.b64encode(png).decode("ascii")


def _add_orthophoto(w: MyIO, walk: MydarWalk) -> MyIO:
    """The orthophoto as an ``image`` layer spanning its extent."""
    o = walk.orthophoto
    if o is None:
        return w
    e = o["extent"]
    return w.add_layer(type="image", label="Orthophoto",
                       data=[{"x": e["xmin"], "y": e["ymin"]}, {"x": e["xmax"], "y": e["ymax"]}],
                       mapping={"x_var": "x", "y_var": "y"},
                       options={"src": _png_data_url(o["png"])})


def _fixed(v: float, unit: str, one_decimal_below: float = 10) -> str:
    text = f"{v:.1f}" if v < one_decimal_below else f"{round(v):d}"
    return f"±{text} {unit}"


def _caption(walk: MydarWalk) -> Dict[str, str]:
    """The walk's two accuracy figures the way the myDAR app states them: Shape
    in centimeters, Map position in meters, never merged into one number."""
    acc = walk.accuracy

    def num(col: str) -> float:
        return _accuracy_number(acc, col)

    def cm(m: float) -> str:
        return _fixed(m * 100, "cm")

    out: Dict[str, str] = {}
    shape = num("shape_95_within_5m_m")
    if math.isfinite(shape):
        out["shape"] = cm(shape)
        note = "within 5 m"
        far = num("shape_95_5_to_15m_m")
        withheld = [num("shape_95_5_to_10m_withheld_m"), num("shape_95_10_to_15m_withheld_m")]
        if math.isfinite(far):
            note += f" · {cm(far)} at 5–15 m"
        elif any(math.isfinite(v) for v in withheld):
            note += " · past 5 m withheld, over 15 cm"
            out["cameraNote"] = "Camera: withheld, its 95% error is over 15 cm."
        out["shapeNote"] = note
    map_95 = num("map_95_m")
    if math.isfinite(map_95):
        pins = num("pins_used")
        has_pins = math.isfinite(pins) and pins > 0
        # As the app: one decimal below 100 m ("±16.8 m").
        out["map"] = cm(map_95) if has_pins and map_95 < 1 else _fixed(map_95, "m", 100)
        basis = None
        if acc is not None and len(acc) > 0 and "map_basis" in acc.columns:
            value = acc["map_basis"].iloc[0]
            basis = None if pd.isna(value) else str(value)
        if has_pins:
            pin_text = f"{pins:g} {'pin' if pins == 1 else 'pins'}"
            out["mapNote"] = pin_text if basis is None else f"{basis}, {pin_text}"
        elif basis is not None:
            out["mapNote"] = basis
    return out


def _add_caption(w: MyIO, walk: MydarWalk) -> MyIO:
    """Caption text in the plot's top-left corner: "Shape ±N cm" and "Map ±N m"."""
    cap = _caption(walk)
    lines = [f"{name} {cap[key]}" for name, key in (("Shape", "shape"), ("Map", "map"))
             if key in cap]
    if not lines:
        return w
    return w.add_layer(type="text", label="Accuracy", data=[{"text": t} for t in lines],
                       mapping={"x_var": "text", "y_var": "text", "label": "text"},
                       options={"position": "top-left"})


def _track_band(walk: MydarWalk) -> Optional[List[List[float]]]:
    """The track's uncertainty band for the viewer: track points as
    [x, y, z, u], u the map-position 95% radius scaled to 0-1 over the walk
    (0.5 everywhere when it does not change)."""
    tp = walk.track_points
    if tp is None or not {"x", "y", "map_95_m"} <= set(tp.columns):
        return None
    tp = tp[np.isfinite(tp["x"]) & np.isfinite(tp["y"]) & np.isfinite(tp["map_95_m"])]
    if len(tp) < 2:
        return None
    if "t_s" in tp.columns:
        tp = tp.sort_values("t_s", kind="stable")
    m = tp["map_95_m"].to_numpy(dtype=float)
    lo, hi = m.min(), m.max()
    u = (m - lo) / (hi - lo) if hi > lo else np.full(len(m), 0.5)
    z = tp["z"].to_numpy(dtype=float) if "z" in tp.columns else np.zeros(len(m))
    return [[float(a), float(b), float(c), float(d)]
            for a, b, c, d in zip(tp["x"], tp["y"], z, u)]


def _css_size(v: Any) -> str:
    return f"{int(v)}px" if _is_real(v) else str(v)


def _escape(s: str) -> str:
    return (str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            .replace('"', "&quot;"))

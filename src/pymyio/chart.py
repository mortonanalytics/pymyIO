"""Python builder for myIO chart specifications.

Mirrors the JSON config produced by the R package's ``myIO()``,
``addIoLayer()``, and the ``set*`` family so that the same vendored
``myIOapi.js`` engine renders identically in Jupyter / VSCode / Marimo via
:class:`MyIOWidget`.
"""

from __future__ import annotations

import copy
import math
import time
from typing import Any, Iterable, List, Mapping, Optional, Sequence, Tuple, Union

from .transforms import get_transform

OKABE_ITO_PALETTE: List[str] = [
    "#E69F00", "#56B4E9", "#009E73", "#F0E442",
    "#0072B2", "#D55E00", "#CC79A7", "#000000",
]

# Full canonical type list (matches R/util.R::ALLOWED_TYPES).
ALLOWED_TYPES: List[str] = [
    "line", "point", "bar", "hexbin", "treemap", "gauge",
    "donut", "area", "groupedBar", "histogram", "heatmap",
    "candlestick", "waterfall", "sankey", "boxplot", "violin",
    "ridgeline", "rangeBar", "text", "regression", "bracket",
    "comparison", "qq",
    "lollipop", "dumbbell",
    "waffle", "beeswarm", "bump",
    "radar", "funnel", "parallel",
    "survfit", "histogram_fit",
    "calendarHeatmap",
]

# Allowed (type, transform) combinations (matches R/util.R::VALID_COMBINATIONS).
VALID_COMBINATIONS: dict = {
    "line":            ("identity", "lm", "loess", "polynomial", "smooth"),
    "point":           ("identity", "mean", "summary", "residuals"),
    "area":            ("identity", "ci"),
    "bar":             ("identity", "mean", "summary"),
    "groupedBar":      ("identity",),
    "histogram":       ("identity",),
    "heatmap":         ("identity",),
    "candlestick":     ("identity",),
    "waterfall":       ("identity", "cumulative"),
    "sankey":          ("identity",),
    "boxplot":         ("identity",),
    "violin":          ("identity",),
    "ridgeline":       ("identity",),
    "rangeBar":        ("identity", "mean_ci"),
    "hexbin":          ("identity",),
    "treemap":         ("identity",),
    "donut":           ("identity",),
    "gauge":           ("identity",),
    "text":            ("identity",),
    "bracket":         ("identity", "pairwise_test"),
    "lollipop":        ("identity", "mean", "summary"),
    "dumbbell":        ("identity",),
    "waffle":          ("identity",),
    "beeswarm":        ("identity",),
    "bump":            ("identity",),
    "radar":           ("identity",),
    "funnel":          ("identity",),
    "parallel":        ("identity",),
    "survfit":         ("identity",),
    "histogram_fit":   ("identity",),
    "calendarHeatmap": ("identity",),
}

# Compatibility groups for layer co-existence (matches R/util.R::COMPATIBILITY_GROUPS
# and ::GROUP_MATRIX).
COMPATIBILITY_GROUPS: dict = {
    "line": "axes-continuous", "point": "axes-continuous", "area": "axes-continuous",
    "bar": "axes-categorical", "groupedBar": "axes-categorical",
    "histogram": "axes-binned", "heatmap": "axes-matrix",
    "candlestick": "axes-continuous", "waterfall": "axes-categorical",
    "sankey": "standalone-flow",
    "boxplot": "axes-categorical", "violin": "axes-categorical",
    "ridgeline": "axes-binned", "rangeBar": "axes-continuous",
    "hexbin": "axes-hex", "treemap": "standalone-flow", "donut": "standalone-radial",
    "gauge": "standalone-radial", "text": "axes-continuous",
    "regression": "axes-continuous", "bracket": "axes-continuous",
    "comparison": "axes-continuous", "qq": "axes-continuous",
    "lollipop": "axes-categorical", "dumbbell": "axes-categorical",
    "waffle": "standalone-flow", "beeswarm": "axes-categorical",
    "bump": "axes-continuous", "radar": "standalone-radial",
    "funnel": "standalone-flow", "parallel": "standalone-flow",
    "survfit": "axes-continuous", "histogram_fit": "axes-binned",
    "calendarHeatmap": "axes-matrix",
}

GROUP_MATRIX: dict = {
    "axes-continuous":  ("axes-continuous",),
    "axes-categorical": ("axes-categorical",),
    "axes-binned":      ("axes-binned",),
    "axes-matrix":      ("axes-matrix",),
    "axes-hex":         ("axes-hex",),
    "standalone-flow":  ("standalone-flow",),
    "standalone-radial": ("standalone-radial",),
}

_REQUIRED_MAPPING: dict = {
    "point":           ("x_var", "y_var"),
    "line":            ("x_var", "y_var"),
    "bar":             ("x_var", "y_var"),
    "groupedBar":      ("x_var", "y_var"),
    "area":            ("x_var", "y_var"),
    "histogram":       ("value",),
    "heatmap":         ("x_var", "y_var", "value"),
    "candlestick":     ("x_var", "open", "high", "low", "close"),
    "waterfall":       ("x_var", "y_var"),
    "sankey":          ("source", "target", "value"),
    "boxplot":         ("x_var", "y_var"),
    "violin":          ("x_var", "y_var"),
    "ridgeline":       ("x_var", "y_var", "group"),
    "donut":           ("x_var", "y_var"),
    "gauge":           ("value",),
    "hexbin":          ("x_var", "y_var", "radius"),
    "treemap":         ("level_1", "level_2"),
    "rangeBar":        ("x_var", "low_y", "high_y"),
    "text":            ("x_var", "y_var", "label"),
    "regression":      ("x_var", "y_var"),
    "bracket":         ("x_var", "y_var"),
    "comparison":      ("x_var", "y_var"),
    "qq":              ("y_var",),
    "lollipop":        ("x_var", "y_var"),
    "dumbbell":        ("x_var", "low_y", "high_y"),
    "waffle":          ("category", "value"),
    "beeswarm":        ("x_var", "y_var"),
    "bump":            ("x_var", "y_var", "group"),
    "radar":           ("axis", "value"),
    "funnel":          ("stage", "value"),
    "parallel":        ("dimensions",),
    "survfit":         ("time", "status"),
    "histogram_fit":   ("value",),
    "calendarHeatmap": ("date", "value"),
}

# Composite layer types — each expands into multiple primitive layers.
COMPOSITE_TYPES: Tuple[str, ...] = (
    "boxplot", "violin", "ridgeline", "regression",
    "comparison", "qq", "survfit", "histogram_fit",
)

DataFrameLike = Any


# ---- data coercion ---------------------------------------------------------

def _to_records(data: DataFrameLike) -> List[dict]:
    """Coerce supported containers (pandas/polars/list-of-dicts) to row dicts."""
    if data is None:
        return []
    if isinstance(data, list):
        return [dict(row) for row in data]
    to_dict = getattr(data, "to_dict", None)
    if callable(to_dict):
        try:
            return to_dict(orient="records")
        except TypeError:
            return to_dict("records")
    to_dicts = getattr(data, "to_dicts", None)
    if callable(to_dicts):
        return to_dicts()
    raise TypeError(
        f"Unsupported data type {type(data).__name__}; pass a pandas/polars "
        "DataFrame or a list of dicts."
    )


def _columns(data: DataFrameLike) -> List[str]:
    cols = getattr(data, "columns", None)
    if cols is not None:
        return list(cols)
    records = _to_records(data)
    return list(records[0].keys()) if records else []


# ---- composite expansion ---------------------------------------------------

def _base_color(color: Any, fallback_index: int = 0) -> str:
    if isinstance(color, str) and color:
        return color
    if isinstance(color, (list, tuple)) and color:
        return color[0]
    return OKABE_ITO_PALETTE[fallback_index]


def _palette_for_groups(color: Any, n: int) -> List[str]:
    if isinstance(color, str) and color:
        base = [color]
    elif isinstance(color, (list, tuple)) and color:
        base = list(color)
    else:
        base = list(OKABE_ITO_PALETTE)
    return [base[i % len(base)] for i in range(n)]


def _group_y(records: List[dict], x_col: str, y_col: str) -> Tuple[List[Any], dict]:
    """Stable per-x grouping of float y values; returns (order, {key: [floats]})."""
    groups: dict = {}
    order: list = []
    for row in records:
        key = row.get(x_col)
        if key not in groups:
            groups[key] = []
            order.append(key)
        v = row.get(y_col)
        if v is None or (isinstance(v, float) and math.isnan(v)):
            continue
        groups[key].append(float(v))
    return order, groups


def _expand_boxplot(records, mapping, label, color, options):
    """Port of R/composite_boxplot.R — emits primitive layers the engine knows."""
    from .transforms import _quantile, transform_outliers
    show_outliers = options.get("showOutliers", True) is not False
    whisker_type = options.get("whiskerType", "tukey")
    base_color = _base_color(color)
    x_col, y_col = mapping["x_var"], mapping["y_var"]

    order, groups = _group_y(records, x_col, y_col)
    positions = list(range(1, len(order) + 1))
    rows = []
    for pos, key in zip(positions, order):
        vals = groups[key]
        if not vals:
            continue
        q1 = _quantile(vals, 0.25)
        med = _quantile(vals, 0.5)
        q3 = _quantile(vals, 0.75)
        if whisker_type == "minmax":
            wlo, whi = min(vals), max(vals)
        else:
            iqr = q3 - q1
            lo_fence, hi_fence = q1 - 1.5 * iqr, q3 + 1.5 * iqr
            in_lo = [v for v in vals if v >= lo_fence]
            in_hi = [v for v in vals if v <= hi_fence]
            wlo = min(in_lo) if in_lo else q1
            whi = max(in_hi) if in_hi else q3
        rows.append((pos, q1, q3, med, wlo, whi, str(key)))

    box_data = [{"x_var": p, "low_y": q1, "high_y": q3, "group": g}
                for (p, q1, q3, _m, _wl, _wh, g) in rows]
    wlow_data = [{"x_var": p, "y_var": wl, "low_y": wl, "high_y": q1, "group": g}
                 for (p, q1, _q3, _m, wl, _wh, g) in rows]
    whigh_data = [{"x_var": p, "y_var": wh, "low_y": q3, "high_y": wh, "group": g}
                  for (p, _q1, q3, _m, _wl, wh, g) in rows]
    med_data = [{"x_var": p, "y_var": m, "low_y": m, "high_y": m, "group": g}
                for (p, _q1, _q3, m, _wl, _wh, g) in rows]

    layers = [
        {"type": "rangeBar", "label": f"{label} - iqr_box", "data": box_data,
         "color": base_color, "transform": "identity", "options": {}, "role": "iqr_box",
         "mapping": {"x_var": "x_var", "low_y": "low_y", "high_y": "high_y", "group": "group"}},
        {"type": "point", "label": f"{label} - whisker_low", "data": wlow_data,
         "color": base_color, "transform": "identity", "options": {}, "role": "whisker_low",
         "mapping": {"x_var": "x_var", "y_var": "y_var", "low_y": "low_y",
                     "high_y": "high_y", "group": "group"}},
        {"type": "point", "label": f"{label} - whisker_high", "data": whigh_data,
         "color": base_color, "transform": "identity", "options": {}, "role": "whisker_high",
         "mapping": {"x_var": "x_var", "y_var": "y_var", "low_y": "low_y",
                     "high_y": "high_y", "group": "group"}},
        {"type": "point", "label": f"{label} - median", "data": med_data,
         "color": base_color, "transform": "identity", "options": {}, "role": "median",
         "mapping": {"x_var": "x_var", "y_var": "y_var", "low_y": "low_y",
                     "high_y": "high_y", "group": "group"}},
    ]

    if show_outliers:
        out_records, _ = transform_outliers(records, mapping, options)
        if out_records:
            pos_lookup = {str(k): p for p, k in zip(positions, order)}
            outlier_rows = []
            for r in out_records:
                g = str(r.get(x_col))
                if g not in pos_lookup:
                    continue
                v = r.get(y_col)
                if v is None:
                    continue
                outlier_rows.append({"x_var": pos_lookup[g], "y_var": float(v), "group": g})
            if outlier_rows:
                layers.append({
                    "type": "point", "label": f"{label} - outliers",
                    "data": outlier_rows, "color": base_color,
                    "transform": "identity", "options": {}, "role": "outliers",
                    "mapping": {"x_var": "x_var", "y_var": "y_var", "group": "group"},
                })
    return layers


def _expand_violin(records, mapping, label, color, options):
    """Port of R/composite_violin.R — area + optional rangeBar/point sub-layers."""
    from .transforms import _quantile, transform_density
    show_box = options.get("showBox", True) is not False
    show_median = options.get("showMedian", True) is not False
    show_points = bool(options.get("showPoints", False))
    bandwidth = options.get("bandwidth")
    box_half_width = float(options.get("boxWidth", 0.7)) / 2
    x_col, y_col = mapping["x_var"], mapping["y_var"]

    order, groups = _group_y(records, x_col, y_col)
    positions = list(range(1, len(order) + 1))
    palette = _palette_for_groups(color, len(order))

    densities = []
    max_density = 0.0
    for key in order:
        vals = groups[key]
        if not vals:
            densities.append([])
            continue
        sub_records = [{y_col: v} for v in vals]
        d_records, _ = transform_density(sub_records, {"y_var": y_col},
                                          {"mirror": False, "bandwidth": bandwidth})
        if d_records:
            local_max = max(r["high_y"] for r in d_records)
            if local_max > max_density:
                max_density = local_max
        densities.append(d_records)

    scale = (box_half_width / max_density) if max_density > 0 else 1.0

    layers = []
    for pos, key, dens, col in zip(positions, order, densities, palette):
        if not dens:
            continue
        gstr = str(key)
        violin_data = [
            {"x_var": pos, "y_var": d["x_var"],
             "low_x": pos - d["high_y"] * scale,
             "high_x": pos + d["high_y"] * scale,
             "group": gstr}
            for d in dens
        ]
        layers.append({
            "type": "area", "label": f"{label} - {gstr} - density",
            "data": violin_data, "color": col,
            "transform": "identity", "options": {"orientation": "vertical"},
            "role": "density_area",
            "mapping": {"x_var": "x_var", "y_var": "y_var",
                         "low_x": "low_x", "high_x": "high_x", "group": "group"},
        })

    box_color = palette[0] if palette else _base_color(color)
    if show_box:
        box_data = []
        for pos, key in zip(positions, order):
            vals = groups[key]
            if not vals:
                continue
            q1, q3 = _quantile(vals, 0.25), _quantile(vals, 0.75)
            box_data.append({"x_var": pos, "low_y": q1, "high_y": q3, "group": str(key)})
        if box_data:
            layers.append({
                "type": "rangeBar", "label": f"{label} - iqr_box",
                "data": box_data, "color": box_color,
                "transform": "identity", "options": {}, "role": "iqr_box",
                "mapping": {"x_var": "x_var", "low_y": "low_y",
                             "high_y": "high_y", "group": "group"},
            })

    if show_median:
        med_data = []
        for pos, key in zip(positions, order):
            vals = groups[key]
            if not vals:
                continue
            med_data.append({"x_var": pos, "y_var": _quantile(vals, 0.5), "group": str(key)})
        if med_data:
            layers.append({
                "type": "point", "label": f"{label} - median",
                "data": med_data, "color": box_color,
                "transform": "identity", "options": {}, "role": "median",
                "mapping": {"x_var": "x_var", "y_var": "y_var", "group": "group"},
            })

    if show_points:
        pt_data = []
        for pos, key in zip(positions, order):
            vals = groups[key]
            if not vals:
                continue
            n = len(vals)
            offsets = [0.0] if n == 1 else [
                -0.2 + 0.4 * i / (n - 1) for i in range(n)
            ]
            for off, v in zip(offsets, vals):
                pt_data.append({"x_var": pos + off, "y_var": v, "group": str(key)})
        if pt_data:
            layers.append({
                "type": "point", "label": f"{label} - points",
                "data": pt_data, "color": box_color,
                "transform": "identity", "options": {}, "role": "points",
                "mapping": {"x_var": "x_var", "y_var": "y_var", "group": "group"},
            })
    return layers


def _expand_ridgeline(records, mapping, label, color, options):
    """Port of R/composite_ridgeline.R — stacked density areas keyed by group."""
    from .transforms import transform_density
    overlap = float(options.get("overlap", 0.4))
    bandwidth = options.get("bandwidth")
    group_col = mapping["group"]
    x_col = mapping["x_var"]

    seen, group_order = set(), []
    for r in records:
        g = r.get(group_col)
        if g not in seen:
            seen.add(g)
            group_order.append(g)
    palette = _palette_for_groups(color, len(group_order))

    density_per_group = []
    max_density = 0.0
    for g in group_order:
        sub = [{x_col: r.get(x_col)} for r in records if r.get(group_col) == g
               and r.get(x_col) is not None]
        if not sub:
            density_per_group.append([])
            continue
        d_records, _ = transform_density(sub, {"y_var": x_col},
                                          {"mirror": False, "bandwidth": bandwidth})
        if d_records:
            local_max = max(r["high_y"] for r in d_records)
            if local_max > max_density:
                max_density = local_max
        density_per_group.append(d_records)

    if max_density <= 0:
        return []
    ridge_height = 1 + overlap
    scale = ridge_height / max_density

    layers = []
    for i, (g, dens, col) in enumerate(zip(group_order, density_per_group, palette), start=1):
        if not dens:
            continue
        gstr = str(g)
        ridge_data = [
            {"x_var": d["x_var"], "low_y": float(i),
             "high_y": float(i) + d["high_y"] * scale, "group": gstr}
            for d in dens
        ]
        layers.append({
            "type": "area", "label": f"{label} - {gstr} - density",
            "data": ridge_data, "color": col,
            "transform": "identity", "options": {}, "role": "density_area",
            "mapping": {"x_var": "x_var", "low_y": "low_y",
                         "high_y": "high_y", "group": "group"},
        })
    return layers


def _expand_qq(records, mapping, label, color, options):
    """Port of R/composite_qq.R — point + reference line (envelope deferred).

    Per-group expansion if mapping['group'] is set; otherwise single Q-Q.
    """
    from .transforms import _normal_quantile, _quantile

    base_color = _base_color(color, fallback_index=4)  # blue-ish default like R
    group_col = mapping.get("group")

    def _qq_for(subset, slabel, scolor):
        y_col = mapping["y_var"]
        ys = sorted([float(r[y_col]) for r in subset
                     if r.get(y_col) is not None
                     and not (isinstance(r[y_col], float) and math.isnan(r[y_col]))])
        n = len(ys)
        if n == 0:
            return []
        pts = [{"x_var": _normal_quantile((i + 0.5) / n), "y_var": y}
               for i, y in enumerate(ys)]
        # Henry reference line: through (Φ⁻¹(0.25), q1) and (Φ⁻¹(0.75), q3)
        q1y, q3y = _quantile(ys, 0.25), _quantile(ys, 0.75)
        x1, x3 = _normal_quantile(0.25), _normal_quantile(0.75)
        slope = (q3y - q1y) / (x3 - x1) if x3 != x1 else 0.0
        intercept = q1y - slope * x1
        x_lo, x_hi = pts[0]["x_var"], pts[-1]["x_var"]
        line_data = [
            {"x_var": x_lo, "y_var": intercept + slope * x_lo},
            {"x_var": x_hi, "y_var": intercept + slope * x_hi},
        ]
        return [
            {"type": "line", "label": f"{slabel} - reference",
             "data": line_data, "color": scolor,
             "transform": "identity", "options": {}, "role": "reference",
             "mapping": {"x_var": "x_var", "y_var": "y_var"}},
            {"type": "point", "label": f"{slabel} - points",
             "data": pts, "color": scolor,
             "transform": "identity", "options": {}, "role": "scatter",
             "mapping": {"x_var": "x_var", "y_var": "y_var"}},
        ]

    if group_col and any(r.get(group_col) is not None for r in records):
        seen, gorder = set(), []
        for r in records:
            g = r.get(group_col)
            if g not in seen:
                seen.add(g)
                gorder.append(g)
        palette = _palette_for_groups(color, len(gorder))
        layers = []
        for g, col in zip(gorder, palette):
            subset = [r for r in records if r.get(group_col) == g]
            layers.extend(_qq_for(subset, f"{label} \u2014 {g}", col))
        return layers

    return _qq_for(records, label, base_color)


def _expand_composite(type: str, records: List[dict], mapping: Mapping[str, str],
                      label: str, color: Any, options: Mapping[str, Any]) -> List[dict]:
    """Expand a composite layer type into a list of primitive sub-layer specs."""
    if type == "regression":
        return [
            {"type": "point", "label": f"{label}::points",
             "data": records, "mapping": mapping, "color": color,
             "transform": "identity", "options": options, "role": "raw"},
            {"type": "line", "label": f"{label}::fit",
             "data": records, "mapping": mapping, "color": color,
             "transform": "lm", "options": options, "role": "fit"},
        ]
    if type == "boxplot":
        return _expand_boxplot(records, mapping, label, color, options)
    if type == "violin":
        return _expand_violin(records, mapping, label, color, options)
    if type == "ridgeline":
        return _expand_ridgeline(records, mapping, label, color, options)
    if type == "qq":
        return _expand_qq(records, mapping, label, color, options)
    if type == "comparison":
        return [
            {"type": "point", "label": f"{label}::points",
             "data": records, "mapping": mapping, "color": color,
             "transform": "identity", "options": options, "role": "raw"},
            {"type": "bracket", "label": f"{label}::brackets",
             "data": records, "mapping": mapping, "color": color,
             "transform": "pairwise_test", "options": options, "role": "test"},
        ]
    if type == "survfit":
        return [
            {"type": "line", "label": label,
             "data": records, "mapping": mapping, "color": color,
             "transform": "survfit", "options": options, "role": "km"},
        ]
    if type == "histogram_fit":
        return [
            {"type": "histogram", "label": label,
             "data": records, "mapping": mapping, "color": color,
             "transform": "identity", "options": options, "role": "hist"},
            {"type": "line", "label": f"{label}::fit",
             "data": records, "mapping": mapping, "color": color,
             "transform": "fit_distribution", "options": options, "role": "fit"},
        ]
    raise ValueError(f"Unknown composite type '{type}'.")


# ---- chart -----------------------------------------------------------------

class MyIO:
    """A myIO chart specification built incrementally.

    Methods that begin with ``add_``, ``set_``, ``suppress_``, ``flip_``,
    ``define_``, or ``drag_`` mutate the chart in place and return ``self`` so
    callers can chain. Use :meth:`to_config` to obtain the JSON-serializable
    config dict, or :meth:`render` to produce an :class:`MyIOWidget`.
    """

    def __init__(
        self,
        data: Optional[DataFrameLike] = None,
        width: Union[int, str] = "100%",
        height: Union[int, str] = "400px",
        element_id: Optional[str] = None,
        sparkline: bool = False,
    ):
        self._data = data
        self.width = width
        self.height = height
        self.element_id = element_id

        if sparkline and height == "400px":
            self.height = 20

        self.config: dict = {
            "specVersion": 1,
            "layers": [],
            "layout": {
                "margin": {"top": 30, "bottom": 60, "left": 50, "right": 5},
                "suppressLegend": False,
                "suppressAxis": {"xAxis": False, "yAxis": False},
            },
            "scales": {
                "xlim": {"min": None, "max": None},
                "ylim": {"min": None, "max": None},
                "categoricalScale": {"xAxis": False, "yAxis": False},
                "flipAxis": False,
                "colorScheme": {
                    "colors": list(OKABE_ITO_PALETTE),
                    "domain": ["none"],
                    "enabled": False,
                },
            },
            "axes": {
                "xAxisFormat": "s",
                "yAxisFormat": "s",
                "xAxisLabel": None,
                "yAxisLabel": None,
                "toolTipFormat": "s",
            },
            "interactions": {
                "dragPoints": False,
                "toggleY": {"variable": None, "format": None},
                "toolTipOptions": {"suppressY": False},
            },
            "theme": {},
            "transitions": {"speed": 1000},
            "referenceLines": {"x": None, "y": None},
        }
        if sparkline:
            self.config["sparkline"] = True

    # ----- layer construction ----------------------------------------------

    def add_layer(
        self,
        type: str,
        label: str,
        mapping: Mapping[str, str],
        data: Optional[DataFrameLike] = None,
        color: Union[str, Sequence[str], None] = None,
        transform: str = "identity",
        options: Optional[Mapping[str, Any]] = None,
    ) -> "MyIO":
        if type not in ALLOWED_TYPES:
            raise ValueError(
                f"Unknown layer type '{type}'. Must be one of: "
                f"{', '.join(ALLOWED_TYPES)}"
            )
        if not isinstance(label, str) or not label:
            raise ValueError("`label` must be a non-empty string.")
        if not isinstance(mapping, Mapping):
            raise TypeError("`mapping` must be a dict-like, e.g. {'x_var': 'wt'}.")

        if self.config.get("sparkline") and type not in {"line", "bar", "area"}:
            raise ValueError(
                f"Sparkline mode only supports types: line, bar, area. Got: '{type}'"
            )

        layer_data = data if data is not None else self._data
        if layer_data is None:
            raise ValueError(
                "`data` must be provided to either MyIO(...) or add_layer(...)."
            )

        existing_labels = {layer["label"] for layer in self.config["layers"]}
        if "group" not in mapping and label in existing_labels:
            raise ValueError(
                f"Layer label '{label}' already exists. Each layer must have a "
                "unique label."
            )

        required = _REQUIRED_MAPPING.get(type, ("x_var", "y_var"))
        missing = [k for k in required if k not in mapping]
        if missing:
            raise ValueError(
                f"Missing required mapping for type '{type}': {', '.join(missing)}."
            )

        cols = _columns(layer_data)
        for field in ("x_var", "y_var", "group", "value", "level_1", "level_2",
                      "open", "high", "low", "close", "source", "target", "date",
                      "time", "status", "category", "stage", "axis"):
            col = mapping.get(field)
            if col is not None and cols and col not in cols:
                raise ValueError(
                    f"Column '{col}' not found in data. Available columns: "
                    f"{', '.join(cols)}."
                )

        self._check_layer_compatibility(type)

        if type == "waterfall" and transform == "identity":
            transform = "cumulative"

        if type not in COMPOSITE_TYPES:
            allowed = VALID_COMBINATIONS.get(type, ("identity",))
            if transform not in allowed:
                raise ValueError(
                    f"Transform '{transform}' is not valid for layer type "
                    f"'{type}'. Allowed: {', '.join(allowed)}."
                )

        layer_id = f"layer_{len(self.config['layers']) + 1:03d}"
        records = _to_records(layer_data)
        for i, row in enumerate(records, start=1):
            row.setdefault("_source_key", f"row_{i}")

        if type in COMPOSITE_TYPES:
            sub_specs = _expand_composite(type, records, mapping, label, color,
                                          dict(options or {}))
            for order, spec in enumerate(sub_specs, start=1):
                tx_records, tx_meta = get_transform(spec["transform"])(
                    spec["data"], spec["mapping"], spec.get("options"),
                )
                self.config["layers"].append(self._build_layer(
                    layer_type=spec["type"], label=spec["label"],
                    data=tx_records, mapping=spec["mapping"],
                    color=spec["color"], transform=spec["transform"],
                    options=spec.get("options"),
                    layer_id=layer_id, order=order,
                    transform_meta=tx_meta,
                    composite=type, composite_role=spec["role"],
                ))
            return self

        if "group" in mapping:
            self._append_grouped_layers(
                records, mapping, type, label, color, transform, options, layer_id,
            )
        else:
            tx_records, tx_meta = get_transform(transform)(records, mapping, options)
            self.config["layers"].append(self._build_layer(
                layer_type=type, label=label, data=tx_records, mapping=mapping,
                color=color, transform=transform, options=options,
                layer_id=layer_id, order=1, transform_meta=tx_meta,
            ))
        return self

    def _build_layer(
        self,
        *,
        layer_type: str,
        label: str,
        data: List[dict],
        mapping: Mapping[str, str],
        color: Union[str, Sequence[str], None],
        transform: str,
        options: Optional[Mapping[str, Any]],
        layer_id: str,
        order: int,
        transform_meta: Optional[dict] = None,
        derived_from: Optional[str] = None,
        composite: Optional[str] = None,
        composite_role: Optional[str] = None,
    ) -> dict:
        opts = {"barSize": "large", "toolTipOptions": {"suppressY": False}}
        if options:
            opts.update(dict(options))
        layer = {
            "id": layer_id if order == 1 else f"{layer_id}_sub_{order:02d}",
            "type": layer_type,
            "color": color,
            "label": label,
            "data": data,
            "mapping": dict(mapping),
            "options": opts,
            "transform": transform,
            "transformMeta": transform_meta,
            "encoding": {},
            "sourceKey": "_source_key",
            "derivedFrom": derived_from,
            "order": order,
            "visibility": True,
        }
        if composite is not None:
            layer["_composite"] = composite
            layer["_compositeRole"] = composite_role
        return layer

    def _append_grouped_layers(
        self,
        records: List[dict],
        mapping: Mapping[str, str],
        type: str,
        label: str,
        color: Union[str, Sequence[str], None],
        transform: str,
        options: Optional[Mapping[str, Any]],
        layer_id: str,
    ) -> None:
        group_col = mapping["group"]
        seen, groups = set(), []
        for row in records:
            value = row.get(group_col)
            if value not in seen:
                seen.add(value)
                groups.append(value)

        if color is None:
            palette = OKABE_ITO_PALETTE
        elif isinstance(color, str):
            palette = [color]
        else:
            palette = list(color)

        existing_labels = {layer["label"] for layer in self.config["layers"]}
        for index, value in enumerate(groups, start=1):
            sub_label = f"{label} \u2014 {value}"
            if sub_label in existing_labels:
                raise ValueError(f"Layer label '{sub_label}' already exists.")
            existing_labels.add(sub_label)
            subset = [r for r in records if r.get(group_col) == value]
            tx_records, tx_meta = get_transform(transform)(subset, mapping, options)
            self.config["layers"].append(self._build_layer(
                layer_type=type, label=sub_label, data=tx_records, mapping=mapping,
                color=palette[(index - 1) % len(palette)],
                transform=transform, options=options,
                layer_id=layer_id, order=index, derived_from=layer_id,
                transform_meta=tx_meta,
            ))

    def _check_layer_compatibility(self, type: str) -> None:
        new_group = COMPATIBILITY_GROUPS.get(type)
        if new_group is None:
            return
        current_groups = []
        for layer in self.config["layers"]:
            g = COMPATIBILITY_GROUPS.get(layer["type"])
            if g is not None and g not in current_groups:
                current_groups.append(g)
        for g in current_groups:
            if new_group not in GROUP_MATRIX.get(g, ()):
                allowed = sorted({
                    name for name, grp in COMPATIBILITY_GROUPS.items()
                    if grp in GROUP_MATRIX.get(g, ())
                })
                raise ValueError(
                    f"Cannot add layer type '{type}' because it is incompatible "
                    f"with existing group '{g}'. Compatible types here: "
                    f"{', '.join(allowed)}."
                )

    # ----- chart-level setters ---------------------------------------------

    def set_margin(self, top: int = 30, bottom: int = 60, left: int = 50, right: int = 5) -> "MyIO":
        self.config["layout"]["margin"] = {
            "top": top, "bottom": bottom, "left": left, "right": right,
        }
        return self

    def set_axis_format(
        self,
        x_format: Optional[str] = None,
        y_format: Optional[str] = None,
        x_label: Optional[str] = None,
        y_label: Optional[str] = None,
        tooltip_format: Optional[str] = None,
    ) -> "MyIO":
        axes = self.config["axes"]
        if x_format is not None:        axes["xAxisFormat"] = x_format
        if y_format is not None:        axes["yAxisFormat"] = y_format
        if x_label is not None:         axes["xAxisLabel"] = x_label
        if y_label is not None:         axes["yAxisLabel"] = y_label
        if tooltip_format is not None:  axes["toolTipFormat"] = tooltip_format
        return self

    def set_axis_limits(
        self,
        xlim: Optional[Sequence[float]] = None,
        ylim: Optional[Sequence[float]] = None,
    ) -> "MyIO":
        if xlim is not None:
            self.config["scales"]["xlim"] = {"min": xlim[0], "max": xlim[1]}
        if ylim is not None:
            self.config["scales"]["ylim"] = {"min": ylim[0], "max": ylim[1]}
        return self

    def define_categorical_axis(self, x_axis: bool = False, y_axis: bool = False) -> "MyIO":
        self.config["scales"]["categoricalScale"] = {"xAxis": x_axis, "yAxis": y_axis}
        return self

    def flip_axis(self, flip: bool = True) -> "MyIO":
        self.config["scales"]["flipAxis"] = flip
        return self

    def set_color_scheme(
        self,
        colors: Iterable[str],
        domain: Optional[Iterable[str]] = None,
    ) -> "MyIO":
        self.config["scales"]["colorScheme"] = {
            "colors": list(colors),
            "domain": list(domain) if domain is not None else ["none"],
            "enabled": True,
        }
        return self

    def set_theme(
        self,
        text_color: Optional[str] = None,
        grid_color: Optional[str] = None,
        bg: Optional[str] = None,
        font: Optional[str] = None,
        mode: Optional[str] = None,
        preset: Optional[str] = None,
        overrides: Optional[Mapping[str, str]] = None,
        **css_vars: str,
    ) -> "MyIO":
        if mode is not None and mode not in {"light", "dark", "auto"}:
            raise ValueError("mode must be 'light', 'dark', 'auto', or None.")
        values: dict = {}
        if text_color is not None: values["--chart-text-color"] = text_color
        if grid_color is not None: values["--chart-grid-color"] = grid_color
        if bg is not None:         values["--chart-bg"] = bg
        if font is not None:       values["--chart-font"] = font
        for name, val in css_vars.items():
            if name.startswith("--"):
                values[name] = val
        if overrides:
            values.update(overrides)
        self.config["theme"] = {
            "mode": mode,
            "preset": preset,
            "values": values,
        }
        return self

    def set_transition_speed(self, ms: int) -> "MyIO":
        self.config["transitions"]["speed"] = int(ms)
        return self

    def set_tooltip_options(self, suppress_y: bool = False) -> "MyIO":
        self.config["interactions"]["toolTipOptions"]["suppressY"] = suppress_y
        return self

    def set_reference_lines(
        self,
        x: Optional[Sequence[float]] = None,
        y: Optional[Sequence[float]] = None,
    ) -> "MyIO":
        self.config["referenceLines"] = {
            "x": list(x) if x is not None else None,
            "y": list(y) if y is not None else None,
        }
        return self

    def suppress_legend(self, suppress: bool = True) -> "MyIO":
        self.config["layout"]["suppressLegend"] = suppress
        return self

    def suppress_axis(
        self,
        x_axis: Optional[bool] = None,
        y_axis: Optional[bool] = None,
    ) -> "MyIO":
        self.config["layout"]["suppressAxis"] = {"xAxis": x_axis, "yAxis": y_axis}
        return self

    def set_brush(self, direction: str = "xy", on_select: str = "highlight") -> "MyIO":
        if direction not in {"xy", "x", "y"}:
            raise ValueError("direction must be 'xy', 'x', or 'y'.")
        if on_select not in {"highlight", "export"}:
            raise ValueError("on_select must be 'highlight' or 'export'.")
        self.config["interactions"]["brush"] = {
            "enabled": True, "direction": direction, "onSelect": on_select,
        }
        return self

    def set_annotation(
        self,
        labels: Optional[Sequence[str]] = None,
        colors: Optional[Mapping[str, str]] = None,
        mode: str = "click",
    ) -> "MyIO":
        if mode != "click":
            raise ValueError("mode must be 'click'.")
        if labels is not None:
            if not labels or not all(isinstance(s, str) for s in labels):
                raise ValueError("`labels` must be a non-empty sequence of strings.")
        if colors is not None and not isinstance(colors, Mapping):
            raise TypeError("`colors` must be a dict like {'outlier': '#E63946'}.")
        self.config["interactions"]["annotation"] = {
            "enabled": True,
            "presetLabels": list(labels) if labels else None,
            "categoryColors": dict(colors) if colors else None,
            "mode": mode,
        }
        return self

    def set_export_options(
        self,
        png: bool = True,
        svg: bool = True,
        pdf: bool = True,
        clipboard: bool = True,
        csv: bool = True,
        title: Optional[str] = None,
    ) -> "MyIO":
        self.config["export"] = {
            "png": png, "svg": svg, "pdf": pdf,
            "clipboard": clipboard, "csv": csv, "title": title,
        }
        return self

    def set_facet(
        self,
        var: str,
        ncol: Optional[int] = None,
        min_width: int = 200,
        scales: str = "fixed",
        label_position: str = "top",
    ) -> "MyIO":
        if scales not in {"fixed", "free_x", "free_y", "free"}:
            raise ValueError("scales must be one of fixed/free_x/free_y/free.")
        if label_position not in {"top", "bottom"}:
            raise ValueError("label_position must be 'top' or 'bottom'.")
        if ncol is not None and ncol < 1:
            raise ValueError("ncol must be >= 1.")
        if min_width <= 0:
            raise ValueError("min_width must be positive.")
        self.config["facet"] = {
            "enabled": True, "var": var,
            "ncol": int(ncol) if ncol is not None else None,
            "minWidth": int(min_width),
            "scales": scales, "labelPosition": label_position,
        }
        return self

    def set_layer_opacity(self, label: str, opacity: float) -> "MyIO":
        if not 0.0 <= opacity <= 1.0:
            raise ValueError("opacity must be between 0 and 1.")
        for layer in self.config["layers"]:
            if layer["label"] == label:
                layer["options"]["opacity"] = opacity
                return self
        raise ValueError(f"Layer '{label}' not found.")

    def set_slider(
        self,
        param: str,
        label: str,
        min: float,
        max: float,
        value: float,
        step: Optional[float] = None,
        debounce: int = 200,
    ) -> "MyIO":
        if min >= max:
            raise ValueError(f"`min` must be less than `max` (got min={min}, max={max}).")
        if not (min <= value <= max):
            raise ValueError(
                f"`value` must be in [{min}, {max}] (got value={value})."
            )
        if debounce <= 0:
            raise ValueError("`debounce` must be positive.")
        sliders = self.config["interactions"].setdefault("sliders", [])
        sliders.append({
            "param": param, "label": label,
            "min": float(min), "max": float(max), "value": float(value),
            "step": float(step) if step is not None else None,
            "debounce": int(debounce),
        })
        return self

    def set_toggle(self, variable: str, format: Optional[str] = None) -> "MyIO":
        self.config["interactions"]["toggleY"] = {"variable": variable, "format": format}
        return self

    def set_linked_cursor(self, enabled: bool = True, axis: str = "x") -> "MyIO":
        if axis not in {"x", "y", "xy"}:
            raise ValueError("axis must be 'x', 'y', or 'xy'.")
        existing = self.config["interactions"].get("linked") or {}
        existing["cursor"] = bool(enabled)
        existing["cursorAxis"] = axis
        self.config["interactions"]["linked"] = existing
        return self

    def drag_points(self, enabled: bool = True) -> "MyIO":
        self.config["interactions"]["dragPoints"] = bool(enabled)
        return self

    # ----- output ----------------------------------------------------------

    def to_config(self) -> dict:
        return copy.deepcopy(self.config)

    def render(self) -> "MyIOWidget":
        from .widget import MyIOWidget
        return MyIOWidget(
            config=self.to_config(),
            width=self.width,
            height=self.height,
        )

    def _repr_mimebundle_(self, **kwargs):
        return self.render()._repr_mimebundle_(**kwargs)


# ---- module-level helpers --------------------------------------------------

def link_charts(
    *charts: MyIO,
    on: str,
    group: Optional[str] = None,
    cursor: bool = False,
    cursor_axis: str = "x",
) -> Tuple[MyIO, ...]:
    """Wire two or more :class:`MyIO` charts together for cross-selection.

    Mirrors R's ``linkCharts()``. Sets matching ``interactions.linked`` config
    on every chart so brush selections in one propagate to the others when
    rendered on the same page (no Crosstalk required — uses a shared group
    identifier and key column).
    """
    if len(charts) < 2:
        raise ValueError("link_charts() requires at least 2 charts.")
    if not isinstance(on, str) or not on:
        raise ValueError("`on` must be a non-empty column name.")
    if cursor_axis not in {"x", "y", "xy"}:
        raise ValueError("cursor_axis must be 'x', 'y', or 'xy'.")
    group_name = group or f"link_{int(time.time())}"
    for chart in charts:
        if not isinstance(chart, MyIO):
            raise TypeError("link_charts() only accepts MyIO instances.")
        chart.config["interactions"]["linked"] = {
            "enabled": True,
            "keyColumn": on,
            "group": group_name,
            "mode": "bidirectional",
            "cursor": bool(cursor),
            "cursorAxis": cursor_axis,
        }
    return charts

"""Python builder for myIO chart specifications.

Mirrors the JSON config produced by the R package's ``myIO()`` and
``addIoLayer()`` functions so that the same vendored ``myIOapi.js`` engine
renders identically in Jupyter / VSCode / Marimo via :class:`MyIOWidget`.
"""

from __future__ import annotations

import copy
from typing import Any, Iterable, List, Mapping, Optional, Sequence, Union

OKABE_ITO_PALETTE: List[str] = [
    "#E69F00", "#56B4E9", "#009E73", "#F0E442",
    "#0072B2", "#D55E00", "#CC79A7", "#000000",
]

ALLOWED_TYPES: List[str] = [
    "point", "line", "bar", "groupedBar", "area", "histogram", "heatmap",
    "candlestick", "waterfall", "sankey", "boxplot", "violin", "ridgeline",
    "donut", "gauge", "hexbin", "treemap",
]

_REQUIRED_MAPPING: dict[str, Sequence[str]] = {
    "point":       ("x_var", "y_var"),
    "line":        ("x_var", "y_var"),
    "bar":         ("x_var", "y_var"),
    "groupedBar":  ("x_var", "y_var"),
    "area":        ("x_var", "y_var"),
    "histogram":   ("value",),
    "heatmap":     ("x_var", "y_var", "value"),
    "candlestick": ("x_var", "open", "high", "low", "close"),
    "waterfall":   ("x_var", "y_var"),
    "sankey":      ("source", "target", "value"),
    "boxplot":     ("x_var", "y_var"),
    "violin":      ("x_var", "y_var"),
    "ridgeline":   ("x_var", "y_var", "group"),
    "donut":       ("x_var", "y_var"),
    "gauge":       ("value",),
    "hexbin":      ("x_var", "y_var", "radius"),
    "treemap":     ("level_1", "level_2"),
}

DataFrameLike = Any  # pandas / polars / list[dict]; resolved by _to_records


def _to_records(data: DataFrameLike) -> List[dict]:
    """Coerce the supported data containers into a list of row dicts.

    Accepts: list/tuple of mappings, pandas.DataFrame, polars.DataFrame,
    or anything with a ``to_dict(orient="records")`` / ``to_dicts()`` method.
    """
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
    to_dicts = getattr(data, "to_dicts", None)  # polars
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


class MyIO:
    """A myIO chart specification built incrementally.

    Methods that begin with ``add_`` or ``set_`` mutate the chart in place
    and return ``self`` so callers can chain. Use :meth:`to_config` to obtain
    the JSON-serializable config dict, or :meth:`render` to produce an
    :class:`MyIOWidget` for display in Jupyter-compatible frontends.
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
        self._next_layer_id = 1

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

    # ----- layer construction --------------------------------------------------

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
                      "open", "high", "low", "close", "source", "target", "date"):
            col = mapping.get(field)
            if col is not None and cols and col not in cols:
                raise ValueError(
                    f"Column '{col}' not found in data. Available columns: "
                    f"{', '.join(cols)}."
                )

        if type == "waterfall" and transform == "identity":
            transform = "cumulative"

        layer_id = f"layer_{self._next_layer_id:02d}"
        self._next_layer_id += 1

        records = _to_records(layer_data)
        for i, row in enumerate(records, start=1):
            row.setdefault("_source_key", i)

        if "group" in mapping:
            self._append_grouped_layers(
                records, mapping, type, label, color, transform, options, layer_id
            )
        else:
            self.config["layers"].append(
                self._build_layer(
                    layer_type=type, label=label, data=records, mapping=mapping,
                    color=color, transform=transform, options=options,
                    layer_id=layer_id, order=1,
                )
            )
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
        derived_from: Optional[str] = None,
    ) -> dict:
        opts = {"barSize": "large", "toolTipOptions": {"suppressY": False}}
        if options:
            opts.update(dict(options))
        return {
            "id": layer_id if order == 1 else f"{layer_id}_sub_{order:02d}",
            "type": layer_type,
            "color": color,
            "label": label,
            "data": data,
            "mapping": dict(mapping),
            "options": opts,
            "transform": transform,
            "transformMeta": None,
            "encoding": {},
            "sourceKey": "_source_key",
            "derivedFrom": derived_from,
            "order": order,
            "visibility": True,
        }

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
            self.config["layers"].append(
                self._build_layer(
                    layer_type=type, label=sub_label, data=subset, mapping=mapping,
                    color=palette[(index - 1) % len(palette)],
                    transform=transform, options=options,
                    layer_id=layer_id, order=index, derived_from=layer_id,
                )
            )

    # ----- chart-level setters -------------------------------------------------

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

    def set_theme(self, **tokens: Any) -> "MyIO":
        self.config["theme"].update(tokens)
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

    # ----- output --------------------------------------------------------------

    def to_config(self) -> dict:
        """Return a deep copy of the JSON-serializable chart config."""
        return copy.deepcopy(self.config)

    def render(self) -> "MyIOWidget":
        """Return an anywidget bound to this chart's current config."""
        from .widget import MyIOWidget
        return MyIOWidget(
            config=self.to_config(),
            width=self.width,
            height=self.height,
        )

    def _repr_mimebundle_(self, **kwargs):
        return self.render()._repr_mimebundle_(**kwargs)

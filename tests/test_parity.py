"""Feature-parity tests against the R myIO package surface.

For each R export listed in NAMESPACE we exercise the Python equivalent and
verify the JSON config it produces matches the R-side shape.
"""

import math

import pytest

from pymyio import (
    ALLOWED_TYPES,
    COMPATIBILITY_GROUPS,
    VALID_COMBINATIONS,
    MyIO,
    link_charts,
)
from pymyio.transforms import REGISTRY, get_transform


SAMPLE = [
    {"wt": 2.620, "mpg": 21.0, "cyl": 6, "Species": "a"},
    {"wt": 2.875, "mpg": 21.0, "cyl": 6, "Species": "a"},
    {"wt": 2.320, "mpg": 22.8, "cyl": 4, "Species": "b"},
    {"wt": 3.215, "mpg": 21.4, "cyl": 6, "Species": "b"},
    {"wt": 3.440, "mpg": 18.7, "cyl": 8, "Species": "a"},
    {"wt": 3.460, "mpg": 18.1, "cyl": 4, "Species": "b"},
]


# ---- canonical lists match R/util.R --------------------------------------

def test_allowed_types_matches_r_canon():
    expected = {
        "line", "point", "bar", "hexbin", "treemap", "gauge", "donut", "area",
        "groupedBar", "histogram", "heatmap", "candlestick", "waterfall",
        "sankey", "boxplot", "violin", "ridgeline", "rangeBar", "text",
        "regression", "bracket", "comparison", "qq", "lollipop", "dumbbell",
        "waffle", "beeswarm", "bump", "radar", "funnel", "parallel",
        "survfit", "histogram_fit", "calendarHeatmap",
    }
    assert set(ALLOWED_TYPES) == expected


def test_valid_combinations_covers_every_primitive_type():
    # Composite types are validated via the composite expansion path, not
    # against VALID_COMBINATIONS — match R's behavior in addIoLayer.R.
    from pymyio.chart import COMPOSITE_TYPES
    for t in ALLOWED_TYPES:
        if t in COMPOSITE_TYPES:
            continue
        assert t in VALID_COMBINATIONS, f"missing valid combinations for {t}"
        assert "identity" in VALID_COMBINATIONS[t]


def test_compatibility_groups_covers_every_type():
    for t in ALLOWED_TYPES:
        assert t in COMPATIBILITY_GROUPS, f"missing compat group for {t}"


# ---- transforms ----------------------------------------------------------

def test_transform_registry_completeness():
    expected = {
        "identity", "lm", "cumulative", "quantiles", "median", "outliers",
        "density", "mean", "summary", "loess", "polynomial", "smooth",
        "residuals", "ci", "mean_ci", "pairwise_test", "qq", "survfit",
        "fit_distribution",
    }
    assert set(REGISTRY.keys()) == expected


def test_lm_recovers_known_slope_intercept():
    # y = 2x + 1 exactly; lm should recover that.
    rows = [{"x": x, "y": 2 * x + 1} for x in range(10)]
    fitted, meta = get_transform("lm")(rows, {"x_var": "x", "y_var": "y"}, None)
    assert meta["name"] == "lm"
    assert math.isclose(meta["slope"], 2.0, abs_tol=1e-9)
    assert math.isclose(meta["intercept"], 1.0, abs_tol=1e-9)
    assert math.isclose(fitted[0]["y"], 1.0, abs_tol=1e-9)
    assert math.isclose(fitted[-1]["y"], 19.0, abs_tol=1e-9)


def test_cumulative_running_sum():
    rows = [{"x": i, "y": v} for i, v in enumerate([1, 2, 3, 4])]
    out, meta = get_transform("cumulative")(rows, {"x_var": "x", "y_var": "y"}, None)
    assert [r["y"] for r in out] == [1, 3, 6, 10]
    assert meta["name"] == "cumulative"


def test_mean_groups_by_x():
    rows = [
        {"x": "a", "y": 1}, {"x": "a", "y": 3},
        {"x": "b", "y": 10}, {"x": "b", "y": 20},
    ]
    out, _ = get_transform("mean")(rows, {"x_var": "x", "y_var": "y"}, None)
    out_map = {r["x"]: r["y"] for r in out}
    assert out_map == {"a": 2.0, "b": 15.0}


def test_summary_emits_low_high_y():
    rows = [{"x": "a", "y": v} for v in [10, 12, 14]]
    out, _ = get_transform("summary")(rows, {"x_var": "x", "y_var": "y"}, None)
    assert math.isclose(out[0]["mean"], 12.0)
    assert math.isclose(out[0]["sd"], 2.0)
    assert out[0]["n"] == 3
    assert math.isclose(out[0]["low_y"], 10.0)
    assert math.isclose(out[0]["high_y"], 14.0)


def test_polynomial_recovers_quadratic():
    rows = [{"x": x, "y": x * x - 2 * x + 1} for x in range(6)]
    fitted, meta = get_transform("polynomial")(
        rows, {"x_var": "x", "y_var": "y"}, {"degree": 2},
    )
    # coefficients are stored highest-degree-first
    assert math.isclose(meta["coefficients"][0], 1.0, abs_tol=1e-6)
    assert math.isclose(meta["coefficients"][1], -2.0, abs_tol=1e-6)
    assert math.isclose(meta["coefficients"][2], 1.0, abs_tol=1e-6)
    assert math.isclose(fitted[0]["y"], 1.0, abs_tol=1e-6)


def test_quantiles_emits_five_number_summary():
    rows = [{"x": "g", "y": v} for v in [1, 2, 3, 4, 5]]
    out, _ = get_transform("quantiles")(rows, {"x_var": "x", "y_var": "y"}, None)
    assert out[0]["q0"] == 1
    assert out[0]["q1"] == 2
    assert out[0]["median"] == 3
    assert out[0]["q3"] == 4
    assert out[0]["q4"] == 5


def test_outliers_flags_iqr_outliers():
    rows = [{"x": "g", "y": v} for v in [10, 11, 12, 13, 14, 100]]
    out, _ = get_transform("outliers")(rows, {"x_var": "x", "y_var": "y"}, None)
    assert any(r["y"] == 100 for r in out)


def test_ci_band_widens_with_variance():
    rows_tight = [{"x": "g", "y": v} for v in [10, 10.1, 9.9]]
    rows_wide = [{"x": "g", "y": v} for v in [5, 10, 15]]
    out_tight, _ = get_transform("ci")(rows_tight, {"x_var": "x", "y_var": "y"}, None)
    out_wide, _ = get_transform("ci")(rows_wide, {"x_var": "x", "y_var": "y"}, None)
    span_tight = out_tight[0]["high_y"] - out_tight[0]["low_y"]
    span_wide = out_wide[0]["high_y"] - out_wide[0]["low_y"]
    assert span_wide > span_tight


# ---- composites ---------------------------------------------------------

def test_regression_composite_expands_into_point_plus_lm_line():
    chart = MyIO(data=SAMPLE).add_layer(
        type="regression", label="reg",
        mapping={"x_var": "wt", "y_var": "mpg"},
    )
    layers = chart.to_config()["layers"]
    assert len(layers) == 2
    assert layers[0]["type"] == "point"
    assert layers[0]["_compositeRole"] == "raw"
    assert layers[1]["type"] == "line"
    assert layers[1]["transform"] == "lm"
    assert layers[1]["_composite"] == "regression"
    assert layers[1]["transformMeta"]["name"] == "lm"


def test_boxplot_composite_emits_box_and_outliers():
    rows = [{"x": "a", "y": v} for v in [10, 11, 12, 13, 100]]
    chart = MyIO(data=rows).add_layer(
        type="boxplot", label="box",
        mapping={"x_var": "x", "y_var": "y"},
    )
    layers = chart.to_config()["layers"]
    assert [layer["type"] for layer in layers] == [
        "rangeBar", "point", "point", "point", "point",
    ]
    assert [layer["_compositeRole"] for layer in layers] == [
        "iqr_box", "whisker_low", "whisker_high", "median", "outliers",
    ]
    assert {layer["transform"] for layer in layers} == {"identity"}
    assert layers[0]["mapping"] == {
        "x_var": "x_var", "low_y": "low_y", "high_y": "high_y", "group": "group",
    }
    assert layers[-1]["data"] == [{"x_var": 1, "y_var": 100.0, "group": "a"}]


def test_violin_composite_emits_density_box_median_and_points():
    rows = [{"x": "a", "y": v} for v in [10, 11, 12, 13, 14, 15]]
    chart = MyIO(data=rows).add_layer(
        type="violin", label="violin",
        mapping={"x_var": "x", "y_var": "y"},
        options={"showPoints": True},
    )
    layers = chart.to_config()["layers"]
    assert [layer["type"] for layer in layers] == ["area", "rangeBar", "point", "point"]
    assert [layer["_compositeRole"] for layer in layers] == [
        "density_area", "iqr_box", "median", "points",
    ]
    assert {layer["transform"] for layer in layers} == {"identity"}
    assert layers[0]["mapping"] == {
        "x_var": "x_var", "y_var": "y_var", "low_x": "low_x",
        "high_x": "high_x", "group": "group",
    }
    assert layers[-1]["data"][0]["group"] == "a"
    assert len(layers[-1]["data"]) == len(rows)


def test_ridgeline_composite_emits_group_density_layers():
    rows = (
        [{"x": v, "group": "a"} for v in [1, 2, 3, 4, 5]]
        + [{"x": v, "group": "b"} for v in [2, 3, 4, 5, 6]]
    )
    chart = MyIO(data=rows).add_layer(
        type="ridgeline", label="ridge",
        mapping={"x_var": "x", "y_var": "x", "group": "group"},
    )
    layers = chart.to_config()["layers"]
    assert [layer["type"] for layer in layers] == ["area", "area"]
    assert [layer["_compositeRole"] for layer in layers] == [
        "density_area", "density_area",
    ]
    assert {layer["transform"] for layer in layers} == {"identity"}
    assert [layer["data"][0]["group"] for layer in layers] == ["a", "b"]
    assert layers[0]["mapping"] == {
        "x_var": "x_var", "low_y": "low_y", "high_y": "high_y", "group": "group",
    }


def test_qq_composite_emits_reference_line_and_points():
    rows = [{"y": v} for v in [1, 2, 3, 4, 5]]
    chart = MyIO(data=rows).add_layer(
        type="qq", label="qq",
        mapping={"y_var": "y"},
    )
    layers = chart.to_config()["layers"]
    assert [layer["type"] for layer in layers] == ["line", "point"]
    assert [layer["_compositeRole"] for layer in layers] == ["reference", "scatter"]
    assert {layer["transform"] for layer in layers} == {"identity"}
    assert len(layers[0]["data"]) == 2
    assert [row["y_var"] for row in layers[1]["data"]] == [1.0, 2.0, 3.0, 4.0, 5.0]


def test_survfit_composite_emits_kaplan_meier_line():
    rows = [{"time": 1, "status": 1}, {"time": 2, "status": 0}, {"time": 3, "status": 1}]
    chart = MyIO(data=rows).add_layer(
        type="survfit", label="km",
        mapping={"time": "time", "status": "status"},
    )
    layers = chart.to_config()["layers"]
    assert [layer["type"] for layer in layers] == ["line"]
    assert layers[0]["_compositeRole"] == "km"
    assert layers[0]["transform"] == "survfit"
    assert layers[0]["transformMeta"]["name"] == "survfit"
    assert {"time", "survival", "n_at_risk", "n_event"} <= set(layers[0]["data"][0])


def test_histogram_fit_composite_emits_histogram_and_fit_line():
    rows = [{"value": v} for v in [1, 2, 3, 4, 5]]
    chart = MyIO(data=rows).add_layer(
        type="histogram_fit", label="hist-fit",
        mapping={"value": "value"},
    )
    layers = chart.to_config()["layers"]
    assert [layer["type"] for layer in layers] == ["histogram", "line"]
    assert [layer["_compositeRole"] for layer in layers] == ["hist", "fit"]
    assert [layer["transform"] for layer in layers] == ["identity", "fit_distribution"]
    assert layers[0]["data"] == [
        {"value": 1, "_source_key": "row_1"},
        {"value": 2, "_source_key": "row_2"},
        {"value": 3, "_source_key": "row_3"},
        {"value": 4, "_source_key": "row_4"},
        {"value": 5, "_source_key": "row_5"},
    ]
    assert layers[1]["transformMeta"]["name"] == "fit_distribution"


# ---- setters ------------------------------------------------------------

def test_set_brush_sets_interaction_block():
    cfg = MyIO().set_brush(direction="x", on_select="export").to_config()
    assert cfg["interactions"]["brush"] == {
        "enabled": True, "direction": "x", "onSelect": "export",
    }


def test_set_brush_validates_direction():
    with pytest.raises(ValueError, match="direction"):
        MyIO().set_brush(direction="diagonal")


def test_set_annotation_with_labels_and_colors():
    cfg = MyIO().set_annotation(
        labels=["outlier", "normal"],
        colors={"outlier": "#E63946", "normal": "#2A9D8F"},
    ).to_config()
    ann = cfg["interactions"]["annotation"]
    assert ann["enabled"] is True
    assert ann["presetLabels"] == ["outlier", "normal"]
    assert ann["categoryColors"] == {"outlier": "#E63946", "normal": "#2A9D8F"}


def test_set_export_options():
    cfg = MyIO().set_export_options(pdf=False, title="My Chart").to_config()
    assert cfg["export"] == {
        "png": True, "svg": True, "pdf": False,
        "clipboard": True, "csv": True, "title": "My Chart",
    }


def test_set_facet():
    cfg = MyIO().set_facet("Species", ncol=3, scales="free_y").to_config()
    assert cfg["facet"] == {
        "enabled": True, "var": "Species", "ncol": 3,
        "minWidth": 200, "scales": "free_y", "labelPosition": "top",
    }


def test_set_facet_validates_scales():
    with pytest.raises(ValueError, match="scales"):
        MyIO().set_facet("Species", scales="bogus")


def test_set_layer_opacity_targets_named_layer():
    chart = MyIO(data=SAMPLE).add_layer(
        type="point", label="pts", mapping={"x_var": "wt", "y_var": "mpg"},
    )
    chart.set_layer_opacity("pts", 0.5)
    assert chart.to_config()["layers"][0]["options"]["opacity"] == 0.5


def test_set_layer_opacity_unknown_label_raises():
    with pytest.raises(ValueError, match="not found"):
        MyIO().set_layer_opacity("ghost", 0.5)


def test_set_slider_appends():
    cfg = (
        MyIO()
        .set_slider("ci_level", "Confidence", 0.80, 0.99, 0.95, step=0.01)
        .set_slider("degree", "Polynomial degree", 1, 5, 2)
        .to_config()
    )
    sliders = cfg["interactions"]["sliders"]
    assert len(sliders) == 2
    assert sliders[0]["param"] == "ci_level"
    assert sliders[0]["value"] == 0.95
    assert sliders[1]["param"] == "degree"


def test_set_slider_validates_range():
    with pytest.raises(ValueError, match="must be in"):
        MyIO().set_slider("p", "Param", 0, 1, 5)


def test_set_toggle():
    cfg = MyIO().set_toggle(variable="Percent", format=".0%").to_config()
    assert cfg["interactions"]["toggleY"] == {"variable": "Percent", "format": ".0%"}


def test_suppress_axis():
    cfg = MyIO().suppress_axis(x_axis=True).to_config()
    assert cfg["layout"]["suppressAxis"] == {"xAxis": True, "yAxis": None}


def test_drag_points():
    cfg = MyIO().drag_points().to_config()
    assert cfg["interactions"]["dragPoints"] is True


def test_set_linked_cursor_preserves_existing_link():
    cfg = (
        MyIO()
        .set_linked_cursor(enabled=True, axis="xy")
        .to_config()
    )
    linked = cfg["interactions"]["linked"]
    assert linked["cursor"] is True
    assert linked["cursorAxis"] == "xy"


def test_set_theme_emits_css_vars():
    cfg = MyIO().set_theme(
        text_color="#222", grid_color="#ddd", bg="#fff",
        font="Inter", mode="dark", overrides={"--chart-tooltip-bg": "#000"},
    ).to_config()
    theme = cfg["theme"]
    assert theme["mode"] == "dark"
    assert theme["values"]["--chart-text-color"] == "#222"
    assert theme["values"]["--chart-grid-color"] == "#ddd"
    assert theme["values"]["--chart-bg"] == "#fff"
    assert theme["values"]["--chart-font"] == "Inter"
    assert theme["values"]["--chart-tooltip-bg"] == "#000"


def test_set_theme_validates_mode():
    with pytest.raises(ValueError, match="mode"):
        MyIO().set_theme(mode="psychedelic")


# ---- link_charts --------------------------------------------------------

def test_link_charts_sets_matching_link_config_on_all():
    a = MyIO(data=SAMPLE).add_layer(
        type="point", label="a", mapping={"x_var": "wt", "y_var": "mpg"},
    )
    b = MyIO(data=SAMPLE).add_layer(
        type="point", label="b", mapping={"x_var": "wt", "y_var": "mpg"},
    )
    link_charts(a, b, on="cyl", group="my-group", cursor=True)
    for chart in (a, b):
        link = chart.to_config()["interactions"]["linked"]
        assert link["enabled"] is True
        assert link["keyColumn"] == "cyl"
        assert link["group"] == "my-group"
        assert link["cursor"] is True
        assert link["cursorAxis"] == "x"


def test_link_charts_requires_two():
    with pytest.raises(ValueError, match="at least 2"):
        link_charts(MyIO(), on="cyl")


# ---- layer compatibility -------------------------------------------------

def test_incompatible_layer_types_raise():
    chart = MyIO(data=SAMPLE).add_layer(
        type="bar", label="b", mapping={"x_var": "cyl", "y_var": "mpg"},
    )
    with pytest.raises(ValueError, match="incompatible"):
        chart.add_layer(
            type="hexbin", label="h",
            mapping={"x_var": "wt", "y_var": "mpg", "radius": "wt"},
        )


def test_invalid_transform_for_type_raises():
    with pytest.raises(ValueError, match="not valid"):
        MyIO(data=SAMPLE).add_layer(
            type="histogram", label="h", mapping={"value": "mpg"},
            transform="lm",
        )


# ---- ID + source-key formats match R ------------------------------------

def test_layer_ids_use_three_digit_format():
    chart = (
        MyIO(data=SAMPLE)
        .add_layer(type="point", label="a",
                   mapping={"x_var": "wt", "y_var": "mpg"})
        .add_layer(type="line", label="b",
                   mapping={"x_var": "wt", "y_var": "mpg"})
    )
    ids = [layer["id"] for layer in chart.to_config()["layers"]]
    assert ids == ["layer_001", "layer_002"]


def test_source_keys_are_row_strings():
    chart = MyIO(data=SAMPLE).add_layer(
        type="point", label="p", mapping={"x_var": "wt", "y_var": "mpg"},
    )
    keys = [r["_source_key"] for r in chart.to_config()["layers"][0]["data"]]
    assert keys == [f"row_{i}" for i in range(1, 7)]

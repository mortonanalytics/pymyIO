"""Config-shape tests — verify the JSON pymyIO produces matches the contract
the vendored myIOapi.js engine expects (and what the R package emits)."""

import pytest

from pymyio import MyIO, ALLOWED_TYPES, OKABE_ITO_PALETTE


SAMPLE = [
    {"wt": 2.620, "mpg": 21.0, "cyl": 6},
    {"wt": 2.875, "mpg": 21.0, "cyl": 6},
    {"wt": 2.320, "mpg": 22.8, "cyl": 4},
    {"wt": 3.215, "mpg": 21.4, "cyl": 6},
    {"wt": 3.440, "mpg": 18.7, "cyl": 8},
    {"wt": 3.460, "mpg": 18.1, "cyl": 4},
]


def test_default_config_shape():
    cfg = MyIO().to_config()
    assert cfg["specVersion"] == 2
    assert cfg["layers"] == []
    assert cfg["layout"]["margin"] == {"top": 30, "bottom": 60, "left": 50, "right": 5}
    assert cfg["layout"]["suppressLegend"] is False
    assert cfg["scales"]["colorScheme"]["enabled"] is False
    assert cfg["scales"]["colorScheme"]["colors"] == OKABE_ITO_PALETTE
    assert cfg["axes"]["xAxisFormat"] == ""
    assert cfg["axes"]["yAxisFormat"] == ""
    assert cfg["axes"]["toolTipFormat"] == ""
    assert cfg["axes"]["xTickLabels"] is None
    assert cfg["transitions"]["speed"] == 1000


def test_add_layer_appends_with_expected_fields():
    chart = MyIO(data=SAMPLE).add_layer(
        type="point", label="points",
        mapping={"x_var": "wt", "y_var": "mpg"},
        color="#E69F00",
    )
    layers = chart.to_config()["layers"]
    assert len(layers) == 1
    layer = layers[0]
    assert layer["type"] == "point"
    assert layer["label"] == "points"
    assert layer["color"] == "#E69F00"
    assert layer["transform"] == "identity"
    assert layer["sourceKey"] == "_source_key"
    assert layer["visibility"] is True
    assert layer["mapping"] == {"x_var": "wt", "y_var": "mpg"}
    assert layer["data"][0]["_source_key"] == "row_1"
    assert layer["data"][0]["wt"] == 2.620
    assert layer["id"] == "layer_001"


def test_unknown_type_raises():
    with pytest.raises(ValueError, match="Unknown layer type"):
        MyIO(data=SAMPLE).add_layer(
            type="rainbow", label="x", mapping={"x_var": "wt", "y_var": "mpg"}
        )


def test_missing_required_mapping_raises():
    with pytest.raises(ValueError, match="Missing required mapping"):
        MyIO(data=SAMPLE).add_layer(type="point", label="x", mapping={"x_var": "wt"})


def test_rangebar_mean_ci_builds_via_transform_mapping():
    # PYMYIO-C05: required-mapping check runs against the transform-injected
    # mapping, so mean_ci's low_y/high_y satisfy rangeBar's contract.
    rows = [{"g": "a", "y": 1.0}, {"g": "a", "y": 2.0}, {"g": "a", "y": 3.0},
            {"g": "b", "y": 4.0}, {"g": "b", "y": 5.0}, {"g": "b", "y": 6.0}]
    layer = (
        MyIO(data=rows)
        .add_layer(type="rangeBar", label="rb",
                   mapping={"x_var": "g", "y_var": "y"}, transform="mean_ci")
        .to_config()["layers"][0]
    )
    assert layer["mapping"]["low_y"] == "low_y"
    assert layer["mapping"]["high_y"] == "high_y"
    assert all("low_y" in r and "high_y" in r for r in layer["data"])


def test_area_band_form_builds_without_y_var():
    # PYMYIO-C05: area accepts an explicit band (low_y/high_y), no center line.
    rows = [{"t": 1, "lo": 0.5, "hi": 1.5}, {"t": 2, "lo": 1.0, "hi": 2.0}]
    cfg = (
        MyIO(data=rows)
        .add_layer(type="area", label="band",
                   mapping={"x_var": "t", "low_y": "lo", "high_y": "hi"})
        .to_config()
    )
    assert cfg["layers"][0]["mapping"] == {"x_var": "t", "low_y": "lo", "high_y": "hi"}


def test_area_simple_form_preserved_and_band_required():
    # Regression guard: simple area (the gallery cumulative-revenue chart) keeps
    # working; area with neither y_var nor a band still raises.
    MyIO(data=SAMPLE).add_layer(type="area", label="simple",
                                mapping={"x_var": "wt", "y_var": "mpg"})
    with pytest.raises(ValueError, match="Missing required mapping"):
        MyIO(data=SAMPLE).add_layer(type="area", label="bad",
                                    mapping={"x_var": "wt"})


def test_missing_column_raises():
    with pytest.raises(ValueError, match="Column 'nope' not found"):
        MyIO(data=SAMPLE).add_layer(
            type="point", label="x", mapping={"x_var": "nope", "y_var": "mpg"}
        )


def test_duplicate_label_raises():
    chart = MyIO(data=SAMPLE).add_layer(
        type="point", label="dup", mapping={"x_var": "wt", "y_var": "mpg"}
    )
    with pytest.raises(ValueError, match="already exists"):
        chart.add_layer(type="line", label="dup",
                        mapping={"x_var": "wt", "y_var": "mpg"})


def test_no_data_raises():
    with pytest.raises(ValueError, match="`data` must be provided"):
        MyIO().add_layer(type="point", label="x",
                         mapping={"x_var": "wt", "y_var": "mpg"})


def test_grouped_mapping_expands_into_one_layer_per_group():
    # v1.3.0 labels grouped layers with the bare group value (encounter order).
    chart = MyIO(data=SAMPLE).add_layer(
        type="line", label="mpg-by-cyl",
        mapping={"x_var": "wt", "y_var": "mpg", "group": "cyl"},
    )
    labels = [layer["label"] for layer in chart.to_config()["layers"]]
    assert labels == ["6", "4", "8"]
    colors = [layer["color"] for layer in chart.to_config()["layers"]]
    assert colors == OKABE_ITO_PALETTE[:3]
    assert all(layer["groupVar"] == "cyl" for layer in chart.to_config()["layers"])


def test_second_grouped_layer_falls_back_to_qualified_label():
    # Mirrors upstream test_grouped_layer_labels.R: same group levels twice.
    chart = MyIO(data=SAMPLE).add_layer(
        type="line", label="A",
        mapping={"x_var": "wt", "y_var": "mpg", "group": "cyl"},
    ).add_layer(
        type="line", label="B",
        mapping={"x_var": "wt", "y_var": "mpg", "group": "cyl"},
    )
    labels = [layer["label"] for layer in chart.to_config()["layers"]]
    assert labels == ["6", "4", "8", "B \u2014 6", "B \u2014 4", "B \u2014 8"]
    assert len(set(labels)) == 6


def test_waterfall_default_transform_is_cumulative():
    chart = MyIO(data=SAMPLE).add_layer(
        type="waterfall", label="wf",
        mapping={"x_var": "wt", "y_var": "mpg"},
    )
    assert chart.to_config()["layers"][0]["transform"] == "cumulative"


def test_setters_chain_and_mutate_config():
    chart = (
        MyIO(data=SAMPLE)
        .set_margin(top=10, bottom=20, left=30, right=40)
        .set_axis_format(x_label="X", y_label="Y", x_format=".2f")
        .set_axis_limits(xlim=(0, 10), ylim=(0, 50))
        .set_color_scheme(["#111", "#222"], domain=["a", "b"])
        .set_transition_speed(500)
        .suppress_legend(True)
        .flip_axis(True)
        .set_reference_lines(x=[0], y=[10, 20])
    )
    cfg = chart.to_config()
    assert cfg["layout"]["margin"] == {"top": 10, "bottom": 20, "left": 30, "right": 40}
    assert cfg["axes"]["xAxisLabel"] == "X"
    assert cfg["axes"]["yAxisLabel"] == "Y"
    assert cfg["axes"]["xAxisFormat"] == ".2f"
    assert cfg["scales"]["xlim"] == {"min": 0, "max": 10}
    assert cfg["scales"]["ylim"] == {"min": 0, "max": 50}
    assert cfg["scales"]["colorScheme"] == {
        "colors": ["#111", "#222"], "domain": ["a", "b"], "enabled": True,
    }
    assert cfg["transitions"]["speed"] == 500
    assert cfg["layout"]["suppressLegend"] is True
    assert cfg["scales"]["flipAxis"] is True
    assert cfg["referenceLines"] == {"x": [0], "y": [10, 20]}


def test_set_axis_format_label_only_preserves_existing_formats():
    cfg = (
        MyIO(data=SAMPLE)
        .set_axis_format(y_format=".1%")
        .set_axis_format(y_label="Rate")
        .to_config()
    )
    assert cfg["axes"]["yAxisFormat"] == ".1%"
    assert cfg["axes"]["yAxisLabel"] == "Rate"
    assert cfg["axes"]["xAxisFormat"] == ""


def test_to_config_returns_independent_copy():
    chart = MyIO(data=SAMPLE).add_layer(
        type="point", label="x", mapping={"x_var": "wt", "y_var": "mpg"}
    )
    snapshot = chart.to_config()
    snapshot["layers"].clear()
    assert len(chart.to_config()["layers"]) == 1


def test_sparkline_sets_height_default():
    chart = MyIO(data=SAMPLE, sparkline=True)
    assert chart.height == 20
    assert chart.config["sparkline"] is True


def test_allowed_types_covers_full_chart_catalog():
    assert set(ALLOWED_TYPES) >= {
        "point", "line", "bar", "groupedBar", "area", "histogram",
        "heatmap", "candlestick", "waterfall", "sankey", "boxplot",
        "violin", "ridgeline", "donut", "gauge", "hexbin", "treemap",
    }


# ---- title surface (parity with R myIO(title=) / setTitle()) ----------------

def test_title_defaults_to_none_in_config():
    assert MyIO().to_config()["title"] is None


def test_title_constructor_kwarg_sets_config_title():
    cfg = MyIO(title="Miles per gallon").to_config()
    assert cfg["title"] == "Miles per gallon"


def test_set_title_builder_sets_and_clears():
    chart = MyIO().set_title("Initial")
    assert chart.to_config()["title"] == "Initial"
    chart.set_title("Updated")
    assert chart.to_config()["title"] == "Updated"
    chart.set_title(None)
    assert chart.to_config()["title"] is None


def test_set_title_rejects_non_string():
    with pytest.raises(TypeError, match="must be NULL or a single character string"):
        MyIO().set_title(123)
    with pytest.raises(TypeError, match="must be NULL or a single character string"):
        MyIO().set_title(["a", "b"])


def test_constructor_title_rejects_non_string():
    with pytest.raises(TypeError, match="must be NULL or a single character string"):
        MyIO(title=42)


def test_okabe_ito_palette_matches_r_canonical_set():
    # R/util.R::OKABE_ITO_PALETTE (post-revert in PR #48 review fixes).
    assert OKABE_ITO_PALETTE == [
        "#E69F00", "#56B4E9", "#009E73", "#F0E442",
        "#0072B2", "#D55E00", "#CC79A7", "#999999",
    ]


# ---- v1.3.0 engine parity additions ----------------------------------------

def test_set_legend_title_stores_derives_and_clears():
    # Mirrors upstream test_setLegendTitle.R.
    chart = MyIO().set_legend_title("Month")
    assert chart.to_config()["layout"]["legendTitle"] == "Month"
    chart.set_legend_title(True)
    assert chart.to_config()["layout"]["legendTitle"] is True
    chart.set_legend_title(None)
    assert "legendTitle" not in chart.to_config()["layout"]
    assert "legendTitle" not in MyIO().to_config()["layout"]


def test_set_legend_title_rejects_non_scalar_string():
    with pytest.raises(ValueError, match="single character string"):
        MyIO().set_legend_title(3)
    with pytest.raises(ValueError, match="single character string"):
        MyIO().set_legend_title(["a", "b"])


def test_set_margin_records_explicit_opt_out_of_auto_fit():
    # Mirrors upstream: explicit margins set layout.marginSet.
    assert "marginSet" not in MyIO().to_config()["layout"]
    chart = MyIO().set_margin(left=30)
    assert chart.to_config()["layout"]["marginSet"] is True


def test_link_charts_mode_is_a_token_linked_js_binds():
    from pymyio import link_charts
    a = MyIO([{"k": 1, "y": 2}])
    b = MyIO([{"k": 1, "y": 3}])
    link_charts(a, b, on="k")
    for chart in (a, b):
        mode = chart.to_config()["interactions"]["linked"]["mode"]
        assert mode == "both"
        assert mode in {"source", "target", "both"}


def test_ridgeline_derives_y_tick_labels_and_axis_label():
    records = [{"v": float(i % 7), "g": name}
               for name in ("beta", "alpha") for i in range(30)]
    chart = MyIO(records).add_layer(
        type="ridgeline", label="ridge",
        mapping={"x_var": "v", "y_var": "v", "group": "g"})
    axes = chart.to_config()["axes"]
    # order_group_values puts alpha at baseline 1 despite beta appearing first
    assert axes["yTickLabels"] == {"1": "alpha", "2": "beta"}
    assert axes["yAxisLabel"] == "g"


def test_violin_median_points_carry_low_and_high_y():
    records = [{"g": name, "v": float(i)}
               for name in ("a", "b") for i in range(1, 12)]
    chart = MyIO(records).add_layer(
        type="violin", label="vio", mapping={"x_var": "g", "y_var": "v"})
    median = next(l for l in chart.to_config()["layers"]
                  if l["_compositeRole"] == "median")
    for row in median["data"]:
        assert row["low_y"] == row["y_var"] == row["high_y"]
    assert median["mapping"]["low_y"] == "low_y"
    assert median["mapping"]["high_y"] == "high_y"


def test_regression_separates_data_and_model_colors():
    records = [{"x": float(i), "y": 2.0 * i + 1} for i in range(10)]
    mapping = {"x_var": "x", "y_var": "y"}

    layers = MyIO(records).add_layer(
        type="regression", label="fit", mapping=mapping,
    ).to_config()["layers"]
    assert layers[0]["color"] == OKABE_ITO_PALETTE[0]   # scatter
    assert layers[1]["color"] == OKABE_ITO_PALETTE[4]   # model

    # data color already the model default -> model shifts to the next hue
    layers = MyIO(records).add_layer(
        type="regression", label="fit", mapping=mapping,
        color=OKABE_ITO_PALETTE[4],
    ).to_config()["layers"]
    assert layers[1]["color"] == OKABE_ITO_PALETTE[5]

    # explicit two-element color vector wins
    layers = MyIO(records).add_layer(
        type="regression", label="fit", mapping=mapping,
        color=["#111111", "#222222"],
    ).to_config()["layers"]
    assert layers[0]["color"] == "#111111"
    assert layers[1]["color"] == "#222222"


@pytest.mark.parametrize("chart_type,mapping", [
    ("radar", {"axis": "a", "value": "v", "group": "g"}),
    ("parallel", {"dimensions": ["v", "w"], "group": "g"}),
])
def test_grouped_radar_and_parallel_stay_one_layer(chart_type, mapping):
    # Parity with myIO #167: the renderer draws every group from mapping group.
    records = [
        {"a": a, "v": v, "w": v * 2, "g": g}
        for g in ("A", "B") for a, v in (("x", 1), ("y", 2), ("z", 3))
    ]
    layers = MyIO(records).add_layer(
        type=chart_type, label="L", mapping=mapping,
    ).to_config()["layers"]
    assert len(layers) == 1
    assert layers[0]["label"] == "L"
    assert layers[0]["mapping"]["group"] == "g"
    assert len(layers[0]["data"]) == 6

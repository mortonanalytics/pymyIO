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
    assert cfg["specVersion"] == 1
    assert cfg["layers"] == []
    assert cfg["layout"]["margin"] == {"top": 30, "bottom": 60, "left": 50, "right": 5}
    assert cfg["layout"]["suppressLegend"] is False
    assert cfg["scales"]["colorScheme"]["enabled"] is False
    assert cfg["scales"]["colorScheme"]["colors"] == OKABE_ITO_PALETTE
    assert cfg["axes"]["xAxisFormat"] == "s"
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
    chart = MyIO(data=SAMPLE).add_layer(
        type="line", label="mpg-by-cyl",
        mapping={"x_var": "wt", "y_var": "mpg", "group": "cyl"},
    )
    labels = [layer["label"] for layer in chart.to_config()["layers"]]
    assert labels == ["mpg-by-cyl \u2014 6", "mpg-by-cyl \u2014 4", "mpg-by-cyl \u2014 8"]
    colors = [layer["color"] for layer in chart.to_config()["layers"]]
    assert colors == OKABE_ITO_PALETTE[:3]


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

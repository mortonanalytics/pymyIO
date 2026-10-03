"""Missing group values — mirrors upstream group_matches()/group_labels() (myIO 1.4.0).

NaN != NaN, so grouping on raw values used to emit a ``"nan"`` layer with no
rows. Missing values now form one group labeled ``"NA"``, renamed to
``"NA (missing)"`` when a present value already reads as ``"NA"``.
"""

import warnings

from pymyio.chart import MyIO
from pymyio.transforms import group_labels, transform_lm


def test_missing_values_label_as_na_unless_that_collides():
    assert group_labels(["a", None, float("nan")]) == ["a", "NA", "NA"]
    assert group_labels(["NA", None]) == ["NA", "NA (missing)"]
    assert group_labels(["NA", "NA (missing)", None]) == ["NA", "NA (missing)", "NA (missing 2)"]


def test_grouped_layer_keeps_rows_with_missing_group():
    records = [
        {"x": 1, "y": 1, "g": "a"},
        {"x": 2, "y": 2, "g": float("nan")},
        {"x": 3, "y": 3, "g": None},
    ]
    chart = MyIO(records).add_layer(
        type="line", label="l", mapping={"x_var": "x", "y_var": "y", "group": "g"})
    layers = {layer["label"]: len(layer["data"]) for layer in chart.to_config()["layers"]}
    assert layers == {"a": 1, "NA": 2}


def test_boxplot_places_missing_group_last_as_na():
    records = (
        [{"g": None, "v": float(i)} for i in range(5)]
        + [{"g": "b", "v": float(i)} for i in range(5)]
    )
    chart = MyIO(records).add_layer(
        type="boxplot", label="box", mapping={"x_var": "g", "y_var": "v"})
    box = next(layer for layer in chart.to_config()["layers"] if layer["type"] == "rangeBar")
    assert [(r["x_var"], r["group"]) for r in box["data"]] == [(1, "b"), (2, "NA")]


def test_lm_drops_non_finite_and_returns_empty_below_two_points():
    rows = [{"x": 1.0, "y": 1.0}, {"x": float("inf"), "y": 2.0}]
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        fitted, _ = transform_lm(rows, {"x_var": "x", "y_var": "y"}, None)
    assert fitted == []
    assert any("at least 2 data points" in str(w.message) for w in caught)

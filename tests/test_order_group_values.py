"""Tests for order_group_values — mirrors upstream test_order_group_values.R.

R's factor-level rule has no Python analog (categorical dtype is lost by
record coercion); the remaining contract — ascending sort, codepoint (C
locale) string order, missing values last — is asserted here, plus the
downstream guarantee that pairwise_test brackets and composite_boxplot
positions agree.
"""

import math

from pymyio.chart import MyIO
from pymyio.transforms import order_group_values, transform_pairwise_test


def test_orders_characters_by_codepoint_like_the_c_locale():
    assert order_group_values(["b", "A", "a", "B"]) == ["A", "B", "a", "b"]


def test_sorts_numerics_numerically_and_puts_missing_last():
    assert order_group_values([10, 2, 33]) == [2, 10, 33]
    assert order_group_values(["b", None, "a"]) == ["a", "b", None]
    out = order_group_values([2.0, float("nan"), 1.0])
    assert out[:2] == [1.0, 2.0] and math.isnan(out[2])


def test_uncomparable_mixed_types_keep_encounter_order():
    assert order_group_values(["b", 1, "a"]) == ["b", 1, "a"]


def test_boxplot_positions_and_pairwise_brackets_agree():
    # "b" appears first in the data, but both boxplot positions and bracket
    # endpoints must place "a" at position 1 under the shared ordering rule.
    records = (
        [{"g": "b", "v": float(i)} for i in range(1, 11)]
        + [{"g": "a", "v": float(i + 20)} for i in range(1, 11)]
    )
    chart = MyIO(records).add_layer(
        type="boxplot", label="box", mapping={"x_var": "g", "y_var": "v"})
    box = next(l for l in chart.to_config()["layers"]
               if l["_compositeRole"] == "iqr_box")
    by_group = {row["group"]: row["x_var"] for row in box["data"]}
    assert by_group == {"a": 1, "b": 2}

    rows, _ = transform_pairwise_test(records, {"x_var": "g", "y_var": "v"}, {})
    assert (rows[0]["group1"], rows[0]["group2"]) == ("a", "b")
    assert (rows[0]["x1"], rows[0]["x2"]) == (1, 2)

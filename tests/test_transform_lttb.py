"""Tests for transform_lttb — Python port of R's transform_lttb (myIO #80).

Mirrors vendor/myIO/tests/testthat/test_transform_lttb.R.
"""

from __future__ import annotations

import math

import pytest

from pymyio import MyIO
from pymyio.transforms import _lttb_select, transform_lttb


def _xy_records(n, y_fn):
    return [{"x": float(i), "y": y_fn(i)} for i in range(1, n + 1)]


def test_lttb_select_keeps_at_most_threshold_points_incl_first_and_last():
    xs = [float(i) for i in range(1, 10001)]
    ys = [math.sin(x / 200) for x in xs]
    idx = _lttb_select(xs, ys, 500)
    assert len(idx) == 500
    assert idx[0] == 0
    assert idx[-1] == 9999
    assert idx == sorted(idx)
    assert len(set(idx)) == len(idx)
    assert all(0 <= i <= 9999 for i in idx)


def test_lttb_select_is_noop_when_n_at_or_below_threshold_or_tiny():
    xs = [float(i) for i in range(100)]
    assert _lttb_select(xs, xs, 500) == list(range(100))
    assert _lttb_select([1.0, 2.0, 3.0], [1.0, 2.0, 3.0], 2) == [0, 1, 2]
    assert _lttb_select([], [], 500) == []


def test_lttb_select_no_duplicate_indices_on_degenerate_geometry():
    # A spike then a collinear tail forces all-zero triangle areas in a bucket,
    # which with an inclusive bucket bound selects the shared endpoint twice.
    xs = [1.0, 2.0, 3.0, 4.0, 5.0]
    ys = [0.0, 0.0, 5.0, 3.5, 2.0]
    idx = _lttb_select(xs, ys, 4)
    assert len(idx) == 4
    assert len(set(idx)) == 4
    assert idx[0] == 0
    assert idx[-1] == 4


def test_lttb_select_keeps_uniqueness_on_flat_series():
    xs = [float(i) for i in range(1, 2001)]
    ys = [7.0] * 2000
    idx = _lttb_select(xs, ys, 300)
    assert len(idx) == 300
    assert len(set(idx)) == 300
    assert idx == sorted(idx)


def test_transform_lttb_downsamples_and_preserves_columns_and_extremes():
    records = [{"x": float(i), "y": math.sin(i / 100), "g": "a"}
               for i in range(1, 5001)]
    out, meta = transform_lttb(records, {"x_var": "x", "y_var": "y"},
                               {"threshold": 1000})
    assert len(out) == 1000
    assert set(out[0]) == {"x", "y", "g"}
    assert out[0]["x"] == 1
    assert out[-1]["x"] == 5000
    assert meta["name"] == "lttb"


def test_transform_lttb_defaults_to_threshold_2000():
    records = _xy_records(5000, float)
    out, _ = transform_lttb(records, {"x_var": "x", "y_var": "y"}, {})
    assert len(out) == 2000


@pytest.mark.parametrize("threshold", [2, "lots", float("nan"), True])
def test_transform_lttb_rejects_invalid_threshold(threshold):
    records = _xy_records(10, float)
    with pytest.raises(ValueError, match="threshold"):
        transform_lttb(records, {"x_var": "x", "y_var": "y"},
                       {"threshold": threshold})


def test_transform_lttb_errors_informatively_on_missing_values():
    records = _xy_records(100, float)
    records[50]["y"] = None
    with pytest.raises(ValueError, match="non-NA"):
        transform_lttb(records, {"x_var": "x", "y_var": "y"}, {"threshold": 50})


def test_add_layer_accepts_lttb_for_line_rejects_elsewhere():
    records = [{"x": float(i), "y": math.sin(i / 100)} for i in range(1, 3001)]
    chart = MyIO(data=records).add_layer(
        type="line", label="l", mapping={"x_var": "x", "y_var": "y"},
        transform="lttb", options={"threshold": 500},
    )
    assert len(chart.config["layers"][-1]["data"]) == 500

    with pytest.raises(ValueError, match="lttb"):
        MyIO(data=records).add_layer(
            type="point", label="p", mapping={"x_var": "x", "y_var": "y"},
            transform="lttb",
        )

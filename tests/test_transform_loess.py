"""Tests for transform_loess — design §Slice 1, contract row `loess`."""

from __future__ import annotations

import json
import warnings

import pytest

from pymyio.transforms import transform_loess


def test_loess_linear_fit_within_tolerance(make_xy_records):
    """AC1: 100-point linear fit, every yhat within 0.5 of 2*x+1."""
    records = make_xy_records(n=100)
    out, meta = transform_loess(records, {"x_var": "x", "y_var": "y"}, None)
    assert len(out) == 100
    xs = [r["x"] for r in out]
    assert xs == sorted(xs)
    for r in out:
        expected = 2.0 * r["x"] + 1.0
        assert abs(r["y"] - expected) < 0.5, (
            f"at x={r['x']} yhat={r['y']} expected≈{expected}"
        )
    assert meta["name"] == "loess"
    assert meta["derivedFrom"] == "input_rows"
    assert len(meta["sourceKeys"]) == 100


def test_loess_too_few_points_warns_and_returns_empty():
    """AC2: <4 points -> warn + empty records + sourceKeys == []."""
    records = [
        {"x": 1.0, "y": 2.0, "_source_key": "r1"},
        {"x": 2.0, "y": 3.0, "_source_key": "r2"},
        {"x": 3.0, "y": 4.0, "_source_key": "r3"},
    ]
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        out, meta = transform_loess(records, {"x_var": "x", "y_var": "y"}, None)
    assert out == []
    assert meta["sourceKeys"] == []
    assert any("4 data points" in str(w.message) for w in caught)


def test_loess_output_is_json_safe(make_xy_records):
    """AC3: json.dumps(records) succeeds without TypeError."""
    records = make_xy_records(n=50)
    out, meta = transform_loess(records, {"x_var": "x", "y_var": "y"}, None)
    json.dumps(out, allow_nan=False)
    json.dumps(meta, allow_nan=False)


def test_loess_source_key_is_grid_indexed(make_xy_records):
    records = make_xy_records(n=20)
    out, _ = transform_loess(records, {"x_var": "x", "y_var": "y"}, {"n_grid": 10})
    assert len(out) == 10
    assert [r["_source_key"] for r in out] == [f"grid_{i + 1}" for i in range(10)]


def test_loess_determinism(make_xy_records):
    """AC21 (phase-level): two invocations on identical input yield byte-identical output."""
    records = make_xy_records(n=50)
    a, ma = transform_loess(records, {"x_var": "x", "y_var": "y"}, None)
    b, mb = transform_loess(records, {"x_var": "x", "y_var": "y"}, None)
    assert a == b
    assert ma == mb

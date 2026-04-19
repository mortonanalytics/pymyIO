"""Tests for transform_density — design §Slice 3, contract row `density`."""

from __future__ import annotations

import json
import warnings

import pytest

from pymyio.transforms import transform_density


def test_density_standard_normal_peaks_near_zero(seeded_rng):
    """AC8: 1000 draws from N(0,1), peak within [-0.3, 0.3], max in [0.30, 0.45]."""
    ys = seeded_rng.standard_normal(1000)
    records = [
        {"y": float(v), "_source_key": f"row_{i + 1}"}
        for i, v in enumerate(ys)
    ]
    out, meta = transform_density(records, {"y_var": "y"}, None)
    assert len(out) == 128
    xs = [r["x_var"] for r in out]
    highs = [r["high_y"] for r in out]
    assert xs == sorted(xs)
    peak_idx = highs.index(max(highs))
    assert -0.3 <= xs[peak_idx] <= 0.3
    assert 0.30 <= highs[peak_idx] <= 0.45
    assert meta["sourceKeys"] is None


def test_density_mirror_flips_low_y(seeded_rng):
    """AC9: mirror=True -> low_y == -high_y row-wise."""
    ys = seeded_rng.standard_normal(500)
    records = [{"y": float(v)} for v in ys]
    out, _ = transform_density(records, {"y_var": "y"}, {"mirror": True})
    for r in out:
        assert r["low_y"] == pytest.approx(-r["high_y"], abs=1e-12)


def test_density_constant_input_warns_and_returns_empty():
    """AC10: zero-variance input -> warn + empty."""
    records = [{"y": 3.14}] * 50
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        out, meta = transform_density(records, {"y_var": "y"}, None)
    assert out == []
    assert caught


def test_density_zero_input_warns_and_returns_empty():
    """DA §2 finding 1: zero-valued input that trips scipy's LinAlgError."""
    records = [{"y": 0.0}] * 100
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        out, _ = transform_density(records, {"y_var": "y"}, None)
    assert out == []


def test_density_empty_input_warns_and_returns_empty():
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        out, meta = transform_density([], {"y_var": "y"}, None)
    assert out == []


def test_density_output_is_json_safe(seeded_rng):
    ys = seeded_rng.standard_normal(200)
    records = [{"y": float(v)} for v in ys]
    out, meta = transform_density(records, {"y_var": "y"}, None)
    json.dumps(out, allow_nan=False)
    json.dumps(meta, allow_nan=False)

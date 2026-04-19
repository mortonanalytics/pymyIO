"""Tests for transform_fit_distribution — design §Slice 6, contract row `fit_distribution`."""

from __future__ import annotations

import json

import pytest

from pymyio.transforms import DISTRIBUTIONS, transform_fit_distribution


def _value_rows(values):
    return [
        {"v": float(x), "_source_key": f"r{i + 1}"}
        for i, x in enumerate(values)
    ]


def test_fit_normal_recovers_params(seeded_rng):
    """AC17: N(5, 2) draws -> meta.params ~ [5, 2] within 0.2."""
    draws = seeded_rng.normal(5.0, 2.0, 1000)
    out, meta = transform_fit_distribution(
        _value_rows(draws), {"value": "v"}, {"distribution": "normal"},
    )
    assert len(meta["params"]) == 2
    assert abs(meta["params"][0] - 5.0) < 0.2
    assert abs(meta["params"][1] - 2.0) < 0.2
    assert len(out) == 128


def test_fit_lognormal_rejects_non_positive():
    """AC18: lognormal on non-positive -> ValueError naming lognormal and positivity."""
    rows = _value_rows([1.0, 2.0, 0.0, 3.0])
    with pytest.raises(ValueError) as ei:
        transform_fit_distribution(
            rows, {"value": "v"}, {"distribution": "lognormal"},
        )
    msg = str(ei.value).lower()
    assert "lognormal" in msg
    assert "positiv" in msg


def test_fit_unknown_distribution_lists_valid():
    """AC19: unknown distribution -> ValueError listing all four."""
    rows = _value_rows([1.0, 2.0, 3.0])
    with pytest.raises(ValueError) as ei:
        transform_fit_distribution(
            rows, {"value": "v"}, {"distribution": "banana"},
        )
    msg = str(ei.value)
    for name in DISTRIBUTIONS:
        assert name in msg


def test_fit_empty_raises():
    with pytest.raises(ValueError, match="no data"):
        transform_fit_distribution([], {"value": "v"}, None)


def test_fit_normal_zero_variance_raises():
    """DA §2 finding 2: norm.fit silently returns scale=0; we raise."""
    rows = _value_rows([0.0] * 100)
    with pytest.raises(ValueError):
        transform_fit_distribution(rows, {"value": "v"}, None)


def test_fit_exponential_rejects_negative():
    rows = _value_rows([1.0, 2.0, -1.0])
    with pytest.raises(ValueError):
        transform_fit_distribution(
            rows, {"value": "v"}, {"distribution": "exponential"},
        )


def test_fit_json_safe(seeded_rng):
    draws = seeded_rng.normal(0.0, 1.0, 200)
    out, meta = transform_fit_distribution(
        _value_rows(draws), {"value": "v"}, None,
    )
    json.dumps(out, allow_nan=False)
    json.dumps(meta, allow_nan=False)


def test_fit_enum_exhaustive():
    assert set(DISTRIBUTIONS) == {"normal", "gamma", "lognormal", "exponential"}

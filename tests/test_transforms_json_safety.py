"""Cross-cutting JSON-safety and determinism guard over the full REGISTRY.

Parametrized over every transform in ``pymyio.transforms.REGISTRY``. Any
numpy scalar leaking from a transform's records or meta surfaces here as
a single assertion failure. Determinism (AC21) is verified by a second
parametrized pass that calls each transform twice on identical input and
asserts byte-identical output.
"""

from __future__ import annotations

import json

import numpy as np
import pytest

from pymyio.transforms import REGISTRY


_RNG = np.random.default_rng(42)


def _xy(n=30):
    xs = _RNG.uniform(0, 10, n)
    ys = 2.0 * xs + 1.0 + _RNG.normal(0, 0.1, n)
    return [
        {"x": float(xs[i]), "y": float(ys[i]), "_source_key": f"row_{i + 1}"}
        for i in range(n)
    ]


def _groups():
    rows = []
    for i, v in enumerate(_RNG.normal(0, 1, 20)):
        rows.append({"g": "A", "y": float(v), "_source_key": f"A{i}"})
    for i, v in enumerate(_RNG.normal(1, 1, 20)):
        rows.append({"g": "B", "y": float(v), "_source_key": f"B{i}"})
    return rows


def _values():
    return [
        {"v": float(x), "_source_key": f"r{i}"}
        for i, x in enumerate(_RNG.normal(0, 1, 50))
    ]


def _survival():
    times = _RNG.exponential(1.0, 20)
    statuses = _RNG.integers(0, 2, 20)
    return [
        {"t": float(times[i]), "s": int(statuses[i]), "_source_key": f"s{i}"}
        for i in range(20)
    ]


# Per-transform fixture table — hard-coded so adding a new REGISTRY entry
# without updating FIXTURES fails the coverage guard below instead of
# silently skipping.
FIXTURES = {
    "identity":         (_xy(),        {"x_var": "x", "y_var": "y"}, None),
    "cumulative":       (_xy(),        {"x_var": "x", "y_var": "y"}, None),
    "mean":             (_xy(),        {"x_var": "x", "y_var": "y"}, None),
    "summary":          (_xy(),        {"x_var": "x", "y_var": "y"}, None),
    "lm":               (_xy(),        {"x_var": "x", "y_var": "y"}, None),
    "polynomial":       (_xy(),        {"x_var": "x", "y_var": "y"}, {"degree": 2}),
    "residuals":        (_xy(),        {"x_var": "x", "y_var": "y"}, None),
    "quantiles":        (_xy(),        {"x_var": "x", "y_var": "y"}, None),
    "median":           (_xy(),        {"x_var": "x", "y_var": "y"}, None),
    "outliers":         (_xy(),        {"x_var": "x", "y_var": "y"}, None),
    "ci":               (_xy(),        {"x_var": "x", "y_var": "y"}, None),
    "mean_ci":          (_xy(),        {"x_var": "x", "y_var": "y"}, None),
    "qq":               (_xy(),        {"x_var": "x", "y_var": "y"}, None),
    "loess":            (_xy(),        {"x_var": "x", "y_var": "y"}, None),
    "smooth":           (_xy(),        {"x_var": "x", "y_var": "y"},
                         {"method": "sma", "window": 3}),
    "density":          (_values(),    {"y_var": "v"}, None),
    "survfit":          (_survival(),  {"time": "t", "status": "s"}, None),
    "fit_distribution": (_values(),    {"value": "v"}, None),
    "pairwise_test":    (_groups(),    {"x_var": "g", "y_var": "y"}, None),
}


def test_registry_fixture_coverage():
    """1:1 between REGISTRY and FIXTURES. Fails fast if a new transform is
    added without a fixture — before the parametrized runs produce noisy
    per-case errors."""
    missing = set(REGISTRY.keys()) - set(FIXTURES.keys())
    extra = set(FIXTURES.keys()) - set(REGISTRY.keys())
    assert not missing, f"FIXTURES missing keys: {sorted(missing)}"
    assert not extra, f"FIXTURES has unknown keys: {sorted(extra)}"


@pytest.mark.parametrize("name", sorted(REGISTRY.keys()))
def test_transform_output_is_pure_python(name, assert_pure_python):
    records, mapping, options = FIXTURES[name]
    fn = REGISTRY[name]
    out, meta = fn(records, mapping, options)
    assert_pure_python(out)
    assert_pure_python(meta)
    json.dumps(out, allow_nan=False)
    json.dumps(meta, allow_nan=False)


@pytest.mark.parametrize("name", sorted(REGISTRY.keys()))
def test_transform_is_deterministic(name):
    """AC21: two invocations on identical input yield equal records and meta.

    Any non-seeded RNG inside a transform surfaces here as a failure.
    """
    records, mapping, options = FIXTURES[name]
    fn = REGISTRY[name]
    out_a, meta_a = fn(records, mapping, options)
    out_b, meta_b = fn(records, mapping, options)
    assert out_a == out_b, f"{name}: records differ between invocations"
    assert meta_a == meta_b, f"{name}: meta differs between invocations"

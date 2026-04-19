"""Shared test fixtures for stats-transform tests.

Fixtures here use pytest's auto-discovery (no `tests/__init__.py` needed).
`make_xy_records` is a fixture factory — request it and then call it with
a desired `n`. `assert_pure_python` is a fixture factory that returns a
recursive JSON-safety checker.
"""

from __future__ import annotations

import numpy as np
import pytest


@pytest.fixture
def seeded_rng():
    """Return a numpy Generator seeded with 0 for reproducibility."""
    return np.random.default_rng(0)


@pytest.fixture
def make_xy_records(seeded_rng):
    """Callable that produces n rows of y = 2x + 1 + noise(sigma=0.1)."""

    def _make(n: int = 100):
        xs = seeded_rng.uniform(0.0, 10.0, n)
        ys = 2.0 * xs + 1.0 + seeded_rng.normal(0.0, 0.1, n)
        return [
            {"x": float(xs[i]), "y": float(ys[i]), "_source_key": f"row_{i + 1}"}
            for i in range(n)
        ]

    return _make


@pytest.fixture
def assert_pure_python():
    """Recursive JSON-safety checker. Uses `type(x) in {...}` to reject
    numpy scalars (numpy.float64 would pass `isinstance(x, float)`).
    """
    native_scalars = {str, int, float, bool, type(None)}

    def _check(obj):
        if isinstance(obj, dict):
            for k, v in obj.items():
                assert type(k) in {str, int}, (
                    f"dict key {k!r} has type {type(k)}"
                )
                _check(v)
        elif isinstance(obj, list):
            for v in obj:
                _check(v)
        else:
            assert type(obj) in native_scalars, (
                f"value {obj!r} has non-native type {type(obj)} "
                f"(numpy leak?); hard-cast at emission site"
            )

    return _check

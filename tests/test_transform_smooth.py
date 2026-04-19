"""Tests for transform_smooth — design §Slice 2, contract row `smooth`."""

from __future__ import annotations

import warnings

import pytest

from pymyio.transforms import SMOOTH_METHODS, transform_smooth


def _rows(ys, keys=None):
    keys = keys or [f"row_{i + 1}" for i in range(len(ys))]
    return [
        {"x": float(i), "y": float(ys[i]), "_source_key": keys[i]}
        for i in range(len(ys))
    ]


def test_smooth_sma_of_constant_preserves_value():
    """AC4: constant y=5.0 window=3 -> all outputs 5.0, 2 rows dropped."""
    records = _rows([5.0] * 20)
    out, meta = transform_smooth(
        records, {"x_var": "x", "y_var": "y"},
        {"method": "sma", "window": 3},
    )
    assert len(out) == 18
    assert all(r["y"] == 5.0 for r in out)


def test_smooth_sma_source_key_alignment():
    """AC5: SMA window=3 forwards _source_key row_2..row_19 in order."""
    records = _rows([1.0 * i for i in range(20)])
    out, meta = transform_smooth(
        records, {"x_var": "x", "y_var": "y"},
        {"method": "sma", "window": 3},
    )
    assert [r["_source_key"] for r in out] == [f"row_{i}" for i in range(2, 20)]
    assert meta["sourceKeys"] == [r["_source_key"] for r in out]


def test_smooth_ema_recurrence():
    """AC6: EMA alpha=0.5 on [0,2] -> [0,1]."""
    records = _rows([0.0, 2.0])
    out, _ = transform_smooth(
        records, {"x_var": "x", "y_var": "y"},
        {"method": "ema", "alpha": 0.5},
    )
    assert len(out) == 2
    assert out[0]["y"] == pytest.approx(0.0, abs=1e-12)
    assert out[1]["y"] == pytest.approx(1.0, abs=1e-12)


def test_smooth_unknown_method_raises():
    """AC7: method='banana' raises ValueError naming sma and ema."""
    records = _rows([1.0, 2.0, 3.0])
    with pytest.raises(ValueError) as ei:
        transform_smooth(
            records, {"x_var": "x", "y_var": "y"}, {"method": "banana"},
        )
    msg = str(ei.value)
    assert "sma" in msg and "ema" in msg


def test_smooth_window_larger_than_data_warns_and_clamps():
    records = _rows([1.0, 2.0, 3.0])
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        out, _ = transform_smooth(
            records, {"x_var": "x", "y_var": "y"},
            {"method": "sma", "window": 99},
        )
    assert any("window" in str(w.message).lower() for w in caught)


def test_smooth_enum_exhaustive():
    assert set(SMOOTH_METHODS) == {"sma", "ema"}

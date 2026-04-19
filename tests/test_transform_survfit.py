"""Tests for transform_survfit — design §Slice 5, contract row `survfit`."""

from __future__ import annotations

import json
import warnings

import pytest

from pymyio.transforms import transform_survfit


def _subjects(times, statuses):
    return [
        {"t": float(times[i]), "s": int(statuses[i]), "_source_key": f"r{i + 1}"}
        for i in range(len(times))
    ]


def test_survfit_all_events_kaplan_meier():
    """AC14: 10 subjects all events, distinct times 1..10, conf_int=None -> 11 rows,
    survival drops linearly 1.0 -> 0.0."""
    recs = _subjects(list(range(1, 11)), [1] * 10)
    out, meta = transform_survfit(
        recs, {"time": "t", "status": "s"}, {"conf_int": None},
    )
    assert len(out) == 11
    anchor = out[0]
    assert anchor == {"time": 0.0, "survival": 1.0, "n_at_risk": 10, "n_event": 0}
    assert "low_y" not in anchor and "high_y" not in anchor
    expected = [1.0, 0.9, 0.8, 0.7, 0.6, 0.5, 0.4, 0.3, 0.2, 0.1, 0.0]
    for row, s in zip(out, expected):
        assert row["survival"] == pytest.approx(s, abs=1e-12)


def test_survfit_all_censored_survival_stays_one():
    """AC15: all status=0 -> every row survival == 1.0, no error."""
    recs = _subjects(list(range(1, 6)), [0] * 5)
    out, _ = transform_survfit(recs, {"time": "t", "status": "s"}, None)
    for row in out:
        assert row["survival"] == 1.0


def test_survfit_conf_int_none_omits_ci_keys():
    """AC16: conf_int=None -> no low_y / high_y keys on any row."""
    recs = _subjects([1, 2, 3], [1, 0, 1])
    out, _ = transform_survfit(
        recs, {"time": "t", "status": "s"}, {"conf_int": None},
    )
    for row in out:
        assert "low_y" not in row
        assert "high_y" not in row


def test_survfit_conf_int_default_emits_ci_keys():
    recs = _subjects([1, 2, 3, 4, 5], [1, 0, 1, 1, 0])
    out, meta = transform_survfit(recs, {"time": "t", "status": "s"}, None)
    assert meta["conf_int"] == 0.95
    for row in out:
        assert "low_y" in row
        assert "high_y" in row


def test_survfit_invalid_status_raises():
    recs = [{"t": 1.0, "s": "alive"}]
    with pytest.raises(ValueError, match="status"):
        transform_survfit(recs, {"time": "t", "status": "s"}, None)


def test_survfit_negative_time_is_dropped_with_warning():
    recs = [{"t": -1.0, "s": 1}, {"t": 1.0, "s": 1}]
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        out, _ = transform_survfit(recs, {"time": "t", "status": "s"}, None)
    assert any("negative" in str(w.message).lower() for w in caught)


def test_survfit_json_safe():
    recs = _subjects([1, 2, 3, 4, 5], [1, 0, 1, 1, 0])
    out, meta = transform_survfit(recs, {"time": "t", "status": "s"}, None)
    json.dumps(out, allow_nan=False)
    json.dumps(meta, allow_nan=False)

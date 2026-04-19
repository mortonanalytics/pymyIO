"""Tests for transform_pairwise_test — design §Slice 4, contract row `pairwise_test`."""

from __future__ import annotations

import json

import pytest

from pymyio.transforms import transform_pairwise_test


def _three_groups(rng):
    a = rng.standard_normal(30)
    b = rng.standard_normal(30)
    c = rng.standard_normal(30) + 3.0
    rows = []
    for v in a:
        rows.append({"g": "A", "y": float(v)})
    for v in b:
        rows.append({"g": "B", "y": float(v)})
    for v in c:
        rows.append({"g": "C", "y": float(v)})
    return rows


def test_pairwise_three_groups_bonferroni(seeded_rng):
    """AC11: A,B ~ N(0,1); C ~ N(3,1). A-C and B-C get *** ; A-B is ns."""
    rows = _three_groups(seeded_rng)
    out, meta = transform_pairwise_test(
        rows, {"x_var": "g", "y_var": "y"},
        {"method": "t.test", "p_adjust": "bonferroni"},
    )
    assert len(out) == 3
    by_pair = {(r["group1"], r["group2"]): r for r in out}
    assert "***" in by_pair[("A", "C")]["label"]
    assert "***" in by_pair[("B", "C")]["label"]
    assert "ns" in by_pair[("A", "B")]["label"]
    for r in out:
        assert r["label"].startswith("p")


def test_pairwise_single_group_raises():
    """AC12: <2 groups -> ValueError containing '2 groups'."""
    rows = [{"g": "A", "y": float(v)} for v in range(5)]
    with pytest.raises(ValueError, match="2 groups"):
        transform_pairwise_test(rows, {"x_var": "g", "y_var": "y"}, None)


def test_pairwise_bh_alias(seeded_rng):
    """AC13: p_adjust='BH' == 'bh'."""
    rows = _three_groups(seeded_rng)
    out_bh, _ = transform_pairwise_test(
        rows, {"x_var": "g", "y_var": "y"}, {"p_adjust": "bh"},
    )
    out_BH, _ = transform_pairwise_test(
        rows, {"x_var": "g", "y_var": "y"}, {"p_adjust": "BH"},
    )
    assert [r["p_value"] for r in out_bh] == [r["p_value"] for r in out_BH]


def test_pairwise_group_size_one_substitutes_none():
    """DA §2 finding 4: ttest_ind of n=1 returns (nan, nan); must become None."""
    rows = [
        {"g": "A", "y": 1.0},
        {"g": "B", "y": 2.0}, {"g": "B", "y": 3.0}, {"g": "B", "y": 4.0},
    ]
    out, _ = transform_pairwise_test(rows, {"x_var": "g", "y_var": "y"}, None)
    assert out[0]["p_value"] is None
    assert out[0]["statistic"] is None
    assert "NA" in out[0]["label"]


def test_pairwise_unknown_method_raises():
    rows = [
        {"g": "A", "y": 1.0}, {"g": "A", "y": 2.0},
        {"g": "B", "y": 3.0}, {"g": "B", "y": 4.0},
    ]
    with pytest.raises(ValueError):
        transform_pairwise_test(
            rows, {"x_var": "g", "y_var": "y"}, {"method": "banana"},
        )


def test_pairwise_unknown_padjust_raises():
    rows = [
        {"g": "A", "y": 1.0}, {"g": "A", "y": 2.0},
        {"g": "B", "y": 3.0}, {"g": "B", "y": 4.0},
    ]
    with pytest.raises(ValueError):
        transform_pairwise_test(
            rows, {"x_var": "g", "y_var": "y"}, {"p_adjust": "banana"},
        )


def test_pairwise_json_safe(seeded_rng):
    rows = _three_groups(seeded_rng)
    out, meta = transform_pairwise_test(rows, {"x_var": "g", "y_var": "y"}, None)
    json.dumps(out, allow_nan=False)
    json.dumps(meta, allow_nan=False)

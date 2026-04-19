# stats-transforms — implementation plan

**Status:** Ready for `/code-the-plan`
**Date:** 2026-04-18
**Design:** [stats-transforms.md](../design/stats-transforms.md)
**Contract:** [stats-transforms-contract.md](../design/stats-transforms-contract.md)

Vertical slices — one transform per phase, red before green every time. Preamble (Phase 0) adds deps, imports, enums, and shared fixtures. Postamble (Phase 7) ships cross-cutting JSON-safety and the README cleanup. Six real transform phases in between.

Conventions used below:
- `.venv/bin/pytest` is the project runner.
- Red commands are the failing command run *before* implementation; green is the same command run *after*. Both are stated explicitly.
- `_not_implemented` count decreases by 1 per phase: 6 → 5 → 4 → 3 → 2 → 1 → 0 by end of Phase 6.
- No file outside the contract's `File locations` table is touched.

---

## Phase 0 — Preamble: deps, imports, enums, fixtures

**Goal.** Hard deps land in `pyproject.toml`; `transforms.py` grows imports + enum tuples at module top; `tests/conftest.py` appears with shared fixtures. No behavior change yet (`REGISTRY` still wires the six stubs to `_not_implemented`).

### 1. File inventory

| File | Action |
|---|---|
| `pyproject.toml` | edit — append `numpy>=1.24`, `scipy>=1.11` to `[project].dependencies` |
| `src/pymyio/transforms.py` | edit — add `import numpy as np`, `from scipy import stats as sst`, `from scipy import linalg as slinalg`, `import warnings`; add four enum tuples at module top |
| `tests/conftest.py` | **new** — `seeded_rng` fixture, `make_xy_records` fixture factory, `assert_pure_python` fixture factory |

### 2. Red test skeleton

`tests/conftest.py` is not a test file; the "red" for this phase is a smoke check that imports still work and fixtures are discoverable:

```python
# tests/conftest.py
import math
import numpy as np
import pytest


@pytest.fixture
def seeded_rng():
    return np.random.default_rng(0)


@pytest.fixture
def make_xy_records(seeded_rng):
    """Fixture factory — callable that produces n rows of a linear y=2x+1+noise(0.1)."""
    def _make(n=100):
        xs = seeded_rng.uniform(0.0, 10.0, n)
        ys = 2.0 * xs + 1.0 + seeded_rng.normal(0.0, 0.1, n)
        return [
            {"x": float(xs[i]), "y": float(ys[i]), "_source_key": f"row_{i+1}"}
            for i in range(n)
        ]
    return _make


@pytest.fixture
def assert_pure_python():
    """Fixture factory — recursive JSON-safety checker; no numpy.generic may leak.

    Uses exact `type(x) in {...}` rather than isinstance to reject numpy
    scalars (e.g. numpy.float64 would pass isinstance(x, float)).
    """
    native_scalars = {str, int, float, bool, type(None)}

    def _check(obj):
        if isinstance(obj, dict):
            for k, v in obj.items():
                assert type(k) in {str, int}, f"dict key {k!r} has type {type(k)}"
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
```

Red command (expects no test files yet for the six new transforms, just that the existing suite still imports):

```
.venv/bin/pytest tests/test_chart_config.py tests/test_parity.py -q
```

### 3. Green implementation

Edit `pyproject.toml`:

```toml
dependencies = [
  "anywidget>=0.10.0,<0.11",
  "traitlets>=5.9,<6",
  "ipywidgets>=8.0",
  "numpy>=1.24",
  "scipy>=1.11",
]
```

Edit `src/pymyio/transforms.py` — add below the existing `import math` (per contract §"Dependencies" and design §"Devil's Advocate" §2 — no lazy imports):

```python
import itertools
import warnings
import numpy as np
from scipy import stats as sst
from scipy import linalg as slinalg
```

Add enum tuples at module top, just below the import block (per contract §"Enum-value cheat sheet"):

```python
SMOOTH_METHODS = ("sma", "ema")
TEST_METHODS = ("t.test", "wilcox.test")
P_ADJUST_METHODS = ("none", "bonferroni", "holm", "bh")  # alias "BH" -> "bh"
DISTRIBUTIONS = ("normal", "gamma", "lognormal", "exponential")
```

Leave `_not_implemented` and the six stub assignments in place for now. Leave `_normal_quantile` unchanged (per prompt — scipy.stats.norm.ppf is fine as an alternative but not required).

### 4. Wiring verification

```
grep -n "^SMOOTH_METHODS\s*=" src/pymyio/transforms.py      # 1 match
grep -n "^TEST_METHODS\s*="   src/pymyio/transforms.py      # 1 match
grep -n "^P_ADJUST_METHODS\s*=" src/pymyio/transforms.py    # 1 match
grep -n "^DISTRIBUTIONS\s*="  src/pymyio/transforms.py      # 1 match
grep -n "^import numpy as np" src/pymyio/transforms.py      # 1 match
grep -n "^from scipy import stats as sst" src/pymyio/transforms.py   # 1 match
grep -c "_not_implemented" src/pymyio/transforms.py         # 7 (1 def + 6 stubs)
```

### 5. Gate command

```
.venv/bin/pip install -e ".[dev]"       # pulls numpy + scipy into the venv
.venv/bin/pytest tests/test_chart_config.py tests/test_parity.py -q
```

Must be green. No new transform tests yet.

---

## Phase 1 — `loess` (vertical slice)

**Per design §Slice 1, contract row `loess`.**

### 1. File inventory

| File | Action |
|---|---|
| `src/pymyio/transforms.py` | replace the `transform_loess = _not_implemented(...)` stub (lines ~307–311) with a real function above it; delete the stub assignment |
| `tests/test_transform_loess.py` | **new** |

### 2. Red test skeleton — write first, run, confirm failure

```python
# tests/test_transform_loess.py
import json
import math
import warnings

import numpy as np
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
        assert abs(r["y"] - expected) < 0.5, f"at x={r['x']} yhat={r['y']} expected≈{expected}"
    assert meta["name"] == "loess"
    assert meta["derivedFrom"] == "input_rows"
    assert len(meta["sourceKeys"]) == 100


def test_loess_too_few_points_warns_and_returns_empty():
    """AC2: <4 points -> warn + empty records + sourceKeys == []."""
    records = [{"x": 1.0, "y": 2.0, "_source_key": "r1"},
               {"x": 2.0, "y": 3.0, "_source_key": "r2"},
               {"x": 3.0, "y": 4.0, "_source_key": "r3"}]
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
    assert [r["_source_key"] for r in out] == [f"grid_{i+1}" for i in range(10)]


def test_loess_determinism(make_xy_records):
    """AC21: two invocations on identical input yield byte-identical output."""
    records = make_xy_records(n=50)
    a, ma = transform_loess(records, {"x_var": "x", "y_var": "y"}, None)
    b, mb = transform_loess(records, {"x_var": "x", "y_var": "y"}, None)
    assert a == b
    assert ma == mb
```

**Red command:**
```
.venv/bin/pytest tests/test_transform_loess.py -q
```
Expect: all tests fail — `NotImplementedError` raised by the stub.

### 3. Green implementation

Replace the stub. Insert *before* the `_not_implemented` block so the function exists when `REGISTRY` initializes. Per prompt verbatim:

```python
def transform_loess(records, mapping, options):
    x_col, y_col = mapping["x_var"], mapping["y_var"]
    xs, ys = _zip_xy(records, x_col, y_col)
    input_keys = [r.get("_source_key") for r in records
                  if r.get(x_col) is not None and r.get(y_col) is not None]
    opts = options or {}
    span = float(opts.get("span", 0.75))
    n_grid = int(opts.get("n_grid", 100))
    if len(xs) < 4:
        warnings.warn("transform_loess requires at least 4 data points.", UserWarning, stacklevel=2)
        return [], _meta("loess", sourceKeys=[], derivedFrom="input_rows")
    xs_np = np.asarray(xs, dtype=float)
    ys_np = np.asarray(ys, dtype=float)
    grid = np.linspace(float(xs_np.min()), float(xs_np.max()), n_grid)
    k = max(2, int(round(span * len(xs_np))))
    fitted = np.empty(n_grid)
    for i, xq in enumerate(grid):
        dists = np.abs(xs_np - xq)
        bw = np.partition(dists, k - 1)[k - 1]  # k-th smallest distance
        if bw == 0.0:
            fitted[i] = float(np.mean(ys_np[dists == 0.0]))
            continue
        u = dists / bw
        w = np.where(u < 1.0, (1.0 - u ** 3) ** 3, 0.0)
        sw = w.sum()
        swx = (w * xs_np).sum()
        swy = (w * ys_np).sum()
        swxx = (w * xs_np * xs_np).sum()
        swxy = (w * xs_np * ys_np).sum()
        det = sw * swxx - swx * swx
        if det == 0.0:
            fitted[i] = float(swy / sw) if sw > 0 else float("nan")
        else:
            a = (swxx * swy - swx * swxy) / det
            b = (sw * swxy - swx * swy) / det
            fitted[i] = float(a + b * xq)
    out = [
        {x_col: float(grid[i]), y_col: float(fitted[i]), "_source_key": f"grid_{i+1}"}
        for i in range(n_grid)
    ]
    return out, _meta("loess", sourceKeys=[str(k) for k in input_keys if k is not None],
                      derivedFrom="input_rows")
```

Delete the `transform_loess = _not_implemented(...)` assignment.

### 4. Wiring verification

```
grep -n "^def transform_loess" src/pymyio/transforms.py    # 1 match
grep -n "\"loess\": transform_loess" src/pymyio/transforms.py   # 1 match (in REGISTRY)
grep -c "_not_implemented" src/pymyio/transforms.py        # 6 (was 7)
```

### 5. Gate command

```
.venv/bin/pytest tests/test_transform_loess.py -q
.venv/bin/pytest tests/test_chart_config.py tests/test_parity.py -q
```
Green on both.

---

## Phase 2 — `smooth`

**Per design §Slice 2, contract row `smooth`.**

### 1. File inventory

| File | Action |
|---|---|
| `src/pymyio/transforms.py` | replace `transform_smooth = _not_implemented(...)` stub |
| `tests/test_transform_smooth.py` | **new** |

### 2. Red test skeleton

```python
# tests/test_transform_smooth.py
import warnings
import pytest

from pymyio.transforms import transform_smooth, SMOOTH_METHODS


def _rows(ys, keys=None):
    keys = keys or [f"row_{i+1}" for i in range(len(ys))]
    return [{"x": float(i), "y": float(ys[i]), "_source_key": keys[i]}
            for i in range(len(ys))]


def test_smooth_sma_of_constant_preserves_value():
    """AC4: constant y=5.0 window=3 -> all outputs 5.0, 2 rows dropped."""
    records = _rows([5.0] * 20)
    out, meta = transform_smooth(records, {"x_var": "x", "y_var": "y"},
                                 {"method": "sma", "window": 3})
    assert len(out) == 18
    assert all(r["y"] == 5.0 for r in out)


def test_smooth_sma_source_key_alignment():
    """AC5: SMA window=3 forwards _source_key row_2..row_19 in order."""
    records = _rows([1.0 * i for i in range(20)])
    out, meta = transform_smooth(records, {"x_var": "x", "y_var": "y"},
                                 {"method": "sma", "window": 3})
    assert [r["_source_key"] for r in out] == [f"row_{i}" for i in range(2, 20)]
    assert meta["sourceKeys"] == [r["_source_key"] for r in out]


def test_smooth_ema_recurrence():
    """AC6: EMA alpha=0.5 on [0,2] -> [0,1]."""
    records = _rows([0.0, 2.0])
    out, _ = transform_smooth(records, {"x_var": "x", "y_var": "y"},
                              {"method": "ema", "alpha": 0.5})
    assert len(out) == 2
    assert out[0]["y"] == pytest.approx(0.0, abs=1e-12)
    assert out[1]["y"] == pytest.approx(1.0, abs=1e-12)


def test_smooth_unknown_method_raises():
    """AC7: method='banana' raises ValueError naming sma and ema."""
    records = _rows([1.0, 2.0, 3.0])
    with pytest.raises(ValueError) as ei:
        transform_smooth(records, {"x_var": "x", "y_var": "y"}, {"method": "banana"})
    msg = str(ei.value)
    assert "sma" in msg and "ema" in msg


def test_smooth_window_larger_than_data_warns_and_clamps():
    records = _rows([1.0, 2.0, 3.0])
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        out, _ = transform_smooth(records, {"x_var": "x", "y_var": "y"},
                                  {"method": "sma", "window": 99})
    assert any("window" in str(w.message).lower() for w in caught)


def test_smooth_enum_exhaustive():
    assert set(SMOOTH_METHODS) == {"sma", "ema"}
```

**Red command:**
```
.venv/bin/pytest tests/test_transform_smooth.py -q
```

### 3. Green implementation

Insert `transform_smooth` above the `_not_implemented` block; delete the stub assignment.

```python
def transform_smooth(records, mapping, options):
    x_col, y_col = mapping["x_var"], mapping["y_var"]
    opts = options or {}
    method = opts.get("method", "sma")
    if method not in SMOOTH_METHODS:
        raise ValueError(
            f"transform_smooth: unknown method {method!r}. "
            f"Valid methods: {', '.join(SMOOTH_METHODS)} (sma or ema)."
        )
    # Filter non-null x/y and keep the source_key alongside.
    triples = []
    for row in records:
        x, y = row.get(x_col), row.get(y_col)
        if x is None or y is None:
            continue
        if isinstance(x, float) and math.isnan(x):
            continue
        if isinstance(y, float) and math.isnan(y):
            continue
        triples.append((float(x), float(y), row.get("_source_key")))
    if not triples:
        return [], _meta("smooth", sourceKeys=[], derivedFrom="input_rows")
    triples.sort(key=lambda t: t[0])
    xs = np.asarray([t[0] for t in triples], dtype=float)
    ys = np.asarray([t[1] for t in triples], dtype=float)
    keys = [t[2] for t in triples]
    if method == "sma":
        window = int(opts.get("window", 7))
        if window > len(ys):
            warnings.warn(
                f"transform_smooth: window={window} exceeds data length {len(ys)}; clamping.",
                UserWarning, stacklevel=2,
            )
            window = len(ys)
        if window < 1:
            window = 1
        kernel = np.ones(window, dtype=float) / window
        smoothed = np.convolve(ys, kernel, mode="valid")  # length = len(ys) - window + 1
        drop = (window - 1) // 2          # left trim
        drop_right = window - 1 - drop     # right trim
        x_mid = xs[drop:len(xs) - drop_right] if drop_right else xs[drop:]
        k_mid = keys[drop:len(keys) - drop_right] if drop_right else keys[drop:]
        out = [
            {x_col: float(x_mid[i]), y_col: float(smoothed[i]),
             "_source_key": k_mid[i] if k_mid[i] is not None else f"row_{drop + i + 1}"}
            for i in range(len(smoothed))
        ]
    else:  # ema
        alpha = float(opts.get("alpha", 0.3))
        if not (0.0 < alpha <= 1.0):
            raise ValueError(f"transform_smooth: alpha must be in (0, 1]; got {alpha!r}.")
        smoothed = np.empty_like(ys)
        smoothed[0] = ys[0]
        for i in range(1, len(ys)):
            smoothed[i] = alpha * ys[i] + (1.0 - alpha) * smoothed[i - 1]
        out = [
            {x_col: float(xs[i]), y_col: float(smoothed[i]),
             "_source_key": keys[i] if keys[i] is not None else f"row_{i+1}"}
            for i in range(len(ys))
        ]
    return out, _meta(
        "smooth",
        sourceKeys=[r["_source_key"] for r in out],
        derivedFrom="input_rows",
    )
```

### 4. Wiring verification

```
grep -n "^def transform_smooth" src/pymyio/transforms.py   # 1
grep -n "\"smooth\": transform_smooth" src/pymyio/transforms.py   # 1
grep -c "_not_implemented" src/pymyio/transforms.py        # 5
```

### 5. Gate command

```
.venv/bin/pytest tests/test_transform_smooth.py -q
.venv/bin/pytest tests/test_chart_config.py tests/test_parity.py -q
```

---

## Phase 3 — `density`

**Per design §Slice 3, contract row `density`. Honors design §"Devil's Advocate" §2 finding 1 (LinAlgError on zero-var + preemptive std-check).**

### 1. File inventory

| File | Action |
|---|---|
| `src/pymyio/transforms.py` | replace `transform_density` stub |
| `tests/test_transform_density.py` | **new** |

### 2. Red test skeleton

```python
# tests/test_transform_density.py
import json
import warnings
import numpy as np
import pytest

from pymyio.transforms import transform_density


def test_density_standard_normal_peaks_near_zero(seeded_rng):
    """AC8: 1000 draws from N(0,1), peak within [-0.3, 0.3], max in [0.30, 0.45]."""
    ys = seeded_rng.standard_normal(1000)
    records = [{"y": float(v), "_source_key": f"row_{i+1}"} for i, v in enumerate(ys)]
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
    """AC10 + DA§2 finding 1: zero-var input -> warn + empty."""
    records = [{"y": 3.14}] * 50
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        out, meta = transform_density(records, {"y_var": "y"}, None)
    assert out == []
    assert caught  # at least one warning

def test_density_zero_input_warns_and_returns_empty():
    """DA§2 finding 1b: zero-valued input that would otherwise trip scipy's LinAlgError."""
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
```

**Red command:**
```
.venv/bin/pytest tests/test_transform_density.py -q
```

### 3. Green implementation

```python
def transform_density(records, mapping, options):
    y_col = mapping["y_var"]
    opts = options or {}
    mirror = bool(opts.get("mirror", False))
    n_grid = int(opts.get("n_grid", 128))
    bandwidth = opts.get("bandwidth", None)
    ys = [float(r[y_col]) for r in records
          if r.get(y_col) is not None
          and not (isinstance(r[y_col], float) and math.isnan(r[y_col]))]
    if not ys:
        warnings.warn("transform_density: empty input.", UserWarning, stacklevel=2)
        return [], _meta("density", sourceKeys=None, derivedFrom="input_rows")
    y_np = np.asarray(ys, dtype=float)
    # design §"Devil's Advocate" §2 finding 1: pre-check zero variance (scipy silently succeeds on constant non-zero).
    if float(np.std(y_np)) == 0.0:
        warnings.warn(
            "transform_density: zero-variance input; density is undefined.",
            UserWarning, stacklevel=2,
        )
        return [], _meta("density", sourceKeys=None, derivedFrom="input_rows")
    try:
        if bandwidth is None:
            kde = sst.gaussian_kde(y_np)
        else:
            kde = sst.gaussian_kde(y_np, bw_method=float(bandwidth))
    except (np.linalg.LinAlgError, slinalg.LinAlgError):
        # design §"Devil's Advocate" §2 finding 1: opaque singular-cov failure.
        warnings.warn(
            "transform_density: scipy gaussian_kde failed (singular covariance).",
            UserWarning, stacklevel=2,
        )
        return [], _meta("density", sourceKeys=None, derivedFrom="input_rows")
    bw = float(kde.factor) * float(np.std(y_np))
    lo = float(y_np.min()) - 3.0 * bw
    hi = float(y_np.max()) + 3.0 * bw
    grid = np.linspace(lo, hi, n_grid)
    high = kde(grid)
    out = []
    for i in range(n_grid):
        h = float(high[i])
        low = -h if mirror else 0.0
        out.append({"x_var": float(grid[i]), "low_y": float(low), "high_y": h})
    return out, _meta("density", sourceKeys=None, derivedFrom="input_rows")
```

### 4. Wiring verification

```
grep -n "^def transform_density" src/pymyio/transforms.py   # 1
grep -n "\"density\": transform_density" src/pymyio/transforms.py   # 1
grep -c "_not_implemented" src/pymyio/transforms.py         # 4
```

### 5. Gate command

```
.venv/bin/pytest tests/test_transform_density.py -q
.venv/bin/pytest tests/test_chart_config.py tests/test_parity.py -q
```

---

## Phase 4 — `pairwise_test`

**Per design §Slice 4, contract row `pairwise_test`. Honors design §"Devil's Advocate" §2 finding 4 (NaN from n=1).**

### 1. File inventory

| File | Action |
|---|---|
| `src/pymyio/transforms.py` | replace `transform_pairwise_test` stub; add `_adjust_p` helper |
| `tests/test_transform_pairwise_test.py` | **new** |

### 2. Red test skeleton

```python
# tests/test_transform_pairwise_test.py
import math
import json
import warnings
import numpy as np
import pytest

from pymyio.transforms import transform_pairwise_test, P_ADJUST_METHODS


def _three_groups(rng):
    a = rng.standard_normal(30)
    b = rng.standard_normal(30)
    c = rng.standard_normal(30) + 3.0
    rows = []
    for v in a: rows.append({"g": "A", "y": float(v)})
    for v in b: rows.append({"g": "B", "y": float(v)})
    for v in c: rows.append({"g": "C", "y": float(v)})
    return rows


def test_pairwise_three_groups_bonferroni(seeded_rng):
    """AC11: A,B N(0,1); C N(3,1). A-C and B-C get *** ; A-B is ns."""
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
    out_bh, _ = transform_pairwise_test(rows, {"x_var": "g", "y_var": "y"},
                                        {"p_adjust": "bh"})
    out_BH, _ = transform_pairwise_test(rows, {"x_var": "g", "y_var": "y"},
                                        {"p_adjust": "BH"})
    assert [r["p_value"] for r in out_bh] == [r["p_value"] for r in out_BH]


def test_pairwise_group_size_one_substitutes_none():
    """design §"Devil's Advocate" §2 finding 4: ttest_ind of n=1 returns (nan, nan); must become None."""
    rows = [{"g": "A", "y": 1.0},
            {"g": "B", "y": 2.0}, {"g": "B", "y": 3.0}, {"g": "B", "y": 4.0}]
    out, _ = transform_pairwise_test(rows, {"x_var": "g", "y_var": "y"}, None)
    assert out[0]["p_value"] is None
    assert out[0]["statistic"] is None
    assert "NA" in out[0]["label"]


def test_pairwise_unknown_method_raises():
    rows = [{"g": "A", "y": 1.0}, {"g": "A", "y": 2.0},
            {"g": "B", "y": 3.0}, {"g": "B", "y": 4.0}]
    with pytest.raises(ValueError):
        transform_pairwise_test(rows, {"x_var": "g", "y_var": "y"},
                                {"method": "banana"})


def test_pairwise_unknown_padjust_raises():
    rows = [{"g": "A", "y": 1.0}, {"g": "A", "y": 2.0},
            {"g": "B", "y": 3.0}, {"g": "B", "y": 4.0}]
    with pytest.raises(ValueError):
        transform_pairwise_test(rows, {"x_var": "g", "y_var": "y"},
                                {"p_adjust": "banana"})


def test_pairwise_json_safe(seeded_rng):
    rows = _three_groups(seeded_rng)
    out, meta = transform_pairwise_test(rows, {"x_var": "g", "y_var": "y"}, None)
    json.dumps(out, allow_nan=False)
    json.dumps(meta, allow_nan=False)
```

**Red command:**
```
.venv/bin/pytest tests/test_transform_pairwise_test.py -q
```

### 3. Green implementation

Add the `_adjust_p` helper and `transform_pairwise_test`. Per prompt, `_adjust_p` body:

```python
def _adjust_p(raw_p, method):
    # None, Bonferroni, Holm, Benjamini-Hochberg. NaN p-values pass through
    # unchanged (they never reach the adjustment frontier).
    if method in ("none", None):
        return list(raw_p)
    n = sum(1 for p in raw_p if p is not None and not math.isnan(p))
    if n == 0:
        return list(raw_p)
    if method == "bonferroni":
        return [None if p is None else (None if math.isnan(p) else min(1.0, float(p) * n))
                for p in raw_p]
    if method == "holm":
        idx = sorted([i for i, p in enumerate(raw_p) if p is not None and not math.isnan(p)],
                     key=lambda i: raw_p[i])
        adj = list(raw_p)
        cur_max = 0.0
        for rank, i in enumerate(idx):
            v = min(1.0, float(raw_p[i]) * (n - rank))
            cur_max = max(cur_max, v)
            adj[i] = float(cur_max)
        return adj
    if method == "bh":
        idx = sorted([i for i, p in enumerate(raw_p) if p is not None and not math.isnan(p)],
                     key=lambda i: raw_p[i])
        adj = list(raw_p)
        running_min = 1.0
        for rank in range(len(idx) - 1, -1, -1):
            i = idx[rank]
            v = min(1.0, float(raw_p[i]) * n / (rank + 1))
            running_min = min(running_min, v)
            adj[i] = float(running_min)
        return adj
    raise ValueError(f"Unknown p_adjust method {method!r}. Valid: none, bonferroni, holm, bh (alias BH).")


def _pairwise_label(p):
    if p is None:
        return "p = NA"
    if p < 0.001:
        return "p < 0.001 ***"
    if p < 0.01:
        return f"p = {p:.3f} **"
    if p < 0.05:
        return f"p = {p:.3f} *"
    return f"p = {p:.2f} ns"


def transform_pairwise_test(records, mapping, options):
    # `itertools` is stdlib — add `import itertools` to the module-top
    # import block in Phase 0 (no lazy imports inside transform bodies).
    x_col, y_col = mapping["x_var"], mapping["y_var"]
    opts = options or {}
    method = opts.get("method", "t.test")
    if method not in TEST_METHODS:
        raise ValueError(
            f"transform_pairwise_test: unknown method {method!r}. "
            f"Valid: {', '.join(TEST_METHODS)}."
        )
    p_adjust_raw = opts.get("p_adjust", "none")
    p_adjust = "bh" if p_adjust_raw == "BH" else p_adjust_raw
    if p_adjust not in ("none", None) and p_adjust not in P_ADJUST_METHODS:
        raise ValueError(
            f"transform_pairwise_test: unknown p_adjust {p_adjust_raw!r}. "
            f"Valid: {', '.join(P_ADJUST_METHODS)} (plus alias BH)."
        )
    paired = bool(opts.get("paired", False))
    step_fraction = float(opts.get("step_fraction", 0.08))
    comparisons = opts.get("comparisons", None)

    # Group in input order; coerce label to str; fail-fast on non-numeric y.
    groups = {}
    order = []
    for row in records:
        g = row.get(x_col)
        if g is None:
            continue
        g = str(g)
        y = row.get(y_col)
        if y is None:
            continue
        if not isinstance(y, (int, float)) or isinstance(y, bool):
            raise TypeError(
                f"transform_pairwise_test: y_var must be numeric; got {type(y).__name__} for group {g!r}."
            )
        if isinstance(y, float) and math.isnan(y):
            continue
        if g not in groups:
            groups[g] = []
            order.append(g)
        groups[g].append(float(y))
    if len(order) < 2:
        raise ValueError(
            f"transform_pairwise_test: need at least 2 groups; got {len(order)}."
        )
    pairs = list(comparisons) if comparisons else list(itertools.combinations(order, 2))
    if len(pairs) > 15:
        warnings.warn(
            f"transform_pairwise_test: {len(pairs)} comparisons exceeds 15; "
            "correction loses power and brackets will overlap.",
            UserWarning, stacklevel=2,
        )
    raw_stats = []
    raw_ps = []
    for g1, g2 in pairs:
        a = np.asarray(groups.get(g1, []), dtype=float)
        b = np.asarray(groups.get(g2, []), dtype=float)
        if len(a) < 2 or len(b) < 2 or (paired and len(a) != len(b)):
            raw_stats.append(None)
            raw_ps.append(None)
            continue
        if method == "t.test":
            if paired:
                res = sst.ttest_rel(a, b)
            else:
                res = sst.ttest_ind(a, b, equal_var=False)
        else:  # wilcox.test
            if paired:
                res = sst.wilcoxon(a, b)
            else:
                res = sst.mannwhitneyu(a, b, alternative="two-sided")
        stat = float(res.statistic)
        p = float(res.pvalue)
        # design §"Devil's Advocate" §2 finding 4: scipy may return nan p-value silently.
        if math.isnan(p):
            raw_stats.append(None); raw_ps.append(None)
        else:
            raw_stats.append(stat); raw_ps.append(p)
    adj_ps = _adjust_p(raw_ps, p_adjust)

    # Vertical bracket stacking based on y_var range.
    all_y = [y for g in order for y in groups[g]]
    y_min = float(min(all_y)); y_max = float(max(all_y))
    y_range = (y_max - y_min) or 1.0
    step = step_fraction * y_range

    # 1-indexed group position in input-order.
    pos = {g: i + 1 for i, g in enumerate(order)}
    out = []
    # Stack narrowest spans first.
    order_idx = sorted(range(len(pairs)), key=lambda i: abs(pos[pairs[i][1]] - pos[pairs[i][0]]))
    level_for = [0] * len(pairs)
    for k, i in enumerate(order_idx):
        level_for[i] = k
    for i, (g1, g2) in enumerate(pairs):
        p = adj_ps[i]
        out.append({
            "x1": int(pos[g1]), "x2": int(pos[g2]),
            "y": float(y_max + step * (level_for[i] + 1)),
            "group1": str(g1), "group2": str(g2),
            "p_value": (None if p is None else float(p)),
            "label": _pairwise_label(None if p is None else float(p)),
            "method": str(method),
            "statistic": (None if raw_stats[i] is None else float(raw_stats[i])),
        })
    return out, _meta("pairwise_test", sourceKeys=None, derivedFrom="input_rows")
```

### 4. Wiring verification

```
grep -n "^def transform_pairwise_test" src/pymyio/transforms.py   # 1
grep -n "\"pairwise_test\": transform_pairwise_test" src/pymyio/transforms.py   # 1
grep -n "^def _adjust_p" src/pymyio/transforms.py                 # 1
grep -c "_not_implemented" src/pymyio/transforms.py               # 3
```

### 5. Gate command

```
.venv/bin/pytest tests/test_transform_pairwise_test.py -q
.venv/bin/pytest tests/test_chart_config.py tests/test_parity.py -q
```

---

## Phase 5 — `survfit`

**Per design §Slice 5, contract row `survfit`.**

### 1. File inventory

| File | Action |
|---|---|
| `src/pymyio/transforms.py` | replace `transform_survfit` stub |
| `tests/test_transform_survfit.py` | **new** |

### 2. Red test skeleton

```python
# tests/test_transform_survfit.py
import json
import warnings
import math
import pytest

from pymyio.transforms import transform_survfit


def _subjects(times, statuses):
    return [{"t": float(times[i]), "s": int(statuses[i]), "_source_key": f"r{i+1}"}
            for i in range(len(times))]


def test_survfit_all_events_kaplan_meier():
    """AC14: 10 subjects all events, distinct times 1..10, conf_int=None -> 11 rows,
    survival drops linearly 1.0 -> 0.0."""
    recs = _subjects(list(range(1, 11)), [1] * 10)
    out, meta = transform_survfit(recs, {"time": "t", "status": "s"}, {"conf_int": None})
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
    out, _ = transform_survfit(recs, {"time": "t", "status": "s"}, {"conf_int": None})
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
```

**Red command:**
```
.venv/bin/pytest tests/test_transform_survfit.py -q
```

### 3. Green implementation

Per prompt verbatim:

```python
def transform_survfit(records, mapping, options):
    t_col, s_col = mapping["time"], mapping["status"]
    opts = options or {}
    conf_int = opts.get("conf_int", 0.95)
    times, statuses, source_keys = [], [], []
    for row in records:
        t, s = row.get(t_col), row.get(s_col)
        key = row.get("_source_key")
        if t is None or s is None:
            warnings.warn("survfit: dropping row with missing time or status.", UserWarning, stacklevel=2)
            continue
        try:
            tv = float(t)
        except (TypeError, ValueError):
            warnings.warn("survfit: dropping row with non-numeric time.", UserWarning, stacklevel=2)
            continue
        if math.isnan(tv) or tv < 0:
            warnings.warn("survfit: dropping row with NaN or negative time.", UserWarning, stacklevel=2)
            continue
        if isinstance(s, bool):
            sv = int(s)
        elif isinstance(s, (int, np.integer)) and int(s) in (0, 1):
            sv = int(s)
        elif isinstance(s, float) and not math.isnan(s) and int(s) in (0, 1) and float(s) == int(s):
            sv = int(s)
        else:
            raise ValueError(
                f"survfit: status value {s!r} is not coercible to 0/1 or bool. "
                "Pass 0 = censored, 1 = event."
            )
        times.append(tv); statuses.append(sv); source_keys.append(key)
    if not times:
        return [], _meta("survfit", sourceKeys=[], derivedFrom="input_rows", conf_int=conf_int)
    ts = np.asarray(times, dtype=float)
    ss = np.asarray(statuses, dtype=int)
    order = np.argsort(ts)
    ts = ts[order]; ss = ss[order]
    unique = np.unique(ts)
    n0 = int(len(ts))
    rows = [{"time": 0.0, "survival": 1.0, "n_at_risk": n0, "n_event": 0}]
    z = None
    if conf_int is not None:
        rows[0]["low_y"] = 1.0
        rows[0]["high_y"] = 1.0
        z = float(sst.norm.ppf(1 - (1 - float(conf_int)) / 2))
    surv = 1.0
    cum_var = 0.0
    for t in unique:
        at = int((ts >= t).sum())
        d = int(((ts == t) & (ss == 1)).sum())
        c = int(((ts == t) & (ss == 0)).sum())
        if at == 0:
            continue
        if d > 0:
            surv *= 1.0 - d / at
            cum_var += d / (at * (at - d)) if at - d > 0 else 0.0
        row = {
            "time": float(t), "survival": float(surv),
            "n_at_risk": at, "n_event": d,
        }
        if conf_int is not None:
            if 0.0 < surv < 1.0 and cum_var > 0.0:
                log_s = math.log(surv)
                se_ll = math.sqrt(cum_var) / abs(log_s)
                low = surv ** math.exp(z * se_ll)
                high = surv ** math.exp(-z * se_ll)
                row["low_y"] = float(max(0.0, min(1.0, low)))
                row["high_y"] = float(max(0.0, min(1.0, high)))
            else:
                row["low_y"] = float(surv)
                row["high_y"] = float(surv)
        rows.append(row)
    return rows, _meta(
        "survfit",
        sourceKeys=[str(k) for k in source_keys if k is not None],
        derivedFrom="input_rows",
        conf_int=conf_int,
    )
```

### 4. Wiring verification

```
grep -n "^def transform_survfit" src/pymyio/transforms.py   # 1
grep -n "\"survfit\": transform_survfit" src/pymyio/transforms.py   # 1
grep -c "_not_implemented" src/pymyio/transforms.py         # 2
```

### 5. Gate command

```
.venv/bin/pytest tests/test_transform_survfit.py -q
.venv/bin/pytest tests/test_chart_config.py tests/test_parity.py -q
```

---

## Phase 6 — `fit_distribution`

**Per design §Slice 6, contract row `fit_distribution`. Honors design §"Devil's Advocate" §2 findings 2 (zero-var normal) and 3 (FitDataError on non-positive).**

### 1. File inventory

| File | Action |
|---|---|
| `src/pymyio/transforms.py` | replace `transform_fit_distribution` stub |
| `tests/test_transform_fit_distribution.py` | **new** |

### 2. Red test skeleton

```python
# tests/test_transform_fit_distribution.py
import json
import numpy as np
import pytest

from pymyio.transforms import transform_fit_distribution, DISTRIBUTIONS


def _value_rows(values):
    return [{"v": float(x), "_source_key": f"r{i+1}"} for i, x in enumerate(values)]


def test_fit_normal_recovers_params(seeded_rng):
    """AC17: N(5, 2) draws -> meta.params ~ [5, 2] within 0.2."""
    draws = seeded_rng.normal(5.0, 2.0, 1000)
    out, meta = transform_fit_distribution(_value_rows(draws), {"value": "v"},
                                           {"distribution": "normal"})
    assert len(meta["params"]) == 2
    assert abs(meta["params"][0] - 5.0) < 0.2
    assert abs(meta["params"][1] - 2.0) < 0.2
    assert len(out) == 128


def test_fit_lognormal_rejects_non_positive():
    """AC18: lognormal on non-positive -> ValueError naming lognormal and positivity."""
    rows = _value_rows([1.0, 2.0, 0.0, 3.0])
    with pytest.raises(ValueError) as ei:
        transform_fit_distribution(rows, {"value": "v"}, {"distribution": "lognormal"})
    msg = str(ei.value).lower()
    assert "lognormal" in msg
    assert "positiv" in msg


def test_fit_unknown_distribution_lists_valid():
    """AC19: unknown distribution -> ValueError listing all four."""
    rows = _value_rows([1.0, 2.0, 3.0])
    with pytest.raises(ValueError) as ei:
        transform_fit_distribution(rows, {"value": "v"}, {"distribution": "banana"})
    msg = str(ei.value)
    for name in DISTRIBUTIONS:
        assert name in msg


def test_fit_empty_raises():
    with pytest.raises(ValueError, match="no data"):
        transform_fit_distribution([], {"value": "v"}, None)


def test_fit_normal_zero_variance_raises():
    """design §"Devil's Advocate" §2 finding 2: norm.fit silently returns scale=0; we raise."""
    rows = _value_rows([0.0] * 100)
    with pytest.raises(ValueError):
        transform_fit_distribution(rows, {"value": "v"}, None)


def test_fit_exponential_rejects_negative():
    rows = _value_rows([1.0, 2.0, -1.0])
    with pytest.raises(ValueError):
        transform_fit_distribution(rows, {"value": "v"}, {"distribution": "exponential"})


def test_fit_json_safe(seeded_rng):
    draws = seeded_rng.normal(0.0, 1.0, 200)
    out, meta = transform_fit_distribution(_value_rows(draws), {"value": "v"}, None)
    json.dumps(out, allow_nan=False)
    json.dumps(meta, allow_nan=False)


def test_fit_enum_exhaustive():
    assert set(DISTRIBUTIONS) == {"normal", "gamma", "lognormal", "exponential"}
```

**Red command:**
```
.venv/bin/pytest tests/test_transform_fit_distribution.py -q
```

### 3. Green implementation

```python
def transform_fit_distribution(records, mapping, options):
    # NOTE: scipy.stats._continuous_distns.FitDataError is a ValueError
    # subclass (verified in scipy 1.17). Catch ValueError broadly below to
    # avoid depending on a private scipy import path.
    v_col = mapping["value"]
    opts = options or {}
    dist_name = opts.get("distribution", "normal")
    n_grid = int(opts.get("n_grid", 128))
    if dist_name not in DISTRIBUTIONS:
        raise ValueError(
            f"transform_fit_distribution: unknown distribution {dist_name!r}. "
            f"Valid: {', '.join(DISTRIBUTIONS)}."
        )
    values = []
    for r in records:
        v = r.get(v_col)
        if v is None:
            continue
        if isinstance(v, float) and math.isnan(v):
            continue
        values.append(float(v))
    if not values:
        raise ValueError("transform_fit_distribution: no data.")
    arr = np.asarray(values, dtype=float)

    # Domain guards per design §Slice 6.
    if dist_name in ("gamma", "lognormal") and np.any(arr <= 0):
        raise ValueError(
            f"transform_fit_distribution: {dist_name} requires strictly positive values."
        )
    if dist_name == "exponential" and np.any(arr < 0):
        raise ValueError(
            "transform_fit_distribution: exponential requires non-negative values."
        )

    # Run scipy's .fit inside a try/except to translate scipy's
    # FitDataError (a ValueError subclass per scipy 1.17) into a pymyio-
    # shaped ValueError. Post-fit degeneracy checks (e.g. scale==0 for
    # normal) happen AFTER the try so they are not wrapped by the
    # positivity-violation messaging.
    try:
        if dist_name == "normal":
            loc, scale = sst.norm.fit(arr)
        elif dist_name == "gamma":
            shape, loc, scale = sst.gamma.fit(arr, floc=0)
        elif dist_name == "lognormal":
            shape, loc, scale = sst.lognorm.fit(arr, floc=0)
        else:  # exponential
            loc, scale = sst.expon.fit(arr, floc=0)
    except ValueError as e:
        # design §"Devil's Advocate" §2 finding 3.
        raise ValueError(
            f"transform_fit_distribution: {dist_name} fit failed — "
            f"positivity / data-domain violation: {e}"
        ) from e

    # Post-fit degeneracy — design §"Devil's Advocate" §2 finding 2:
    # sst.norm.fit(np.zeros(n)) silently returns (0, 0). Raise ourselves.
    if dist_name == "normal":
        if float(scale) == 0.0:
            raise ValueError(
                "transform_fit_distribution: normal fit degenerate (scale==0); "
                "zero-variance input."
            )
        params = [float(loc), float(scale)]
        pdf = sst.norm.pdf
        pdf_args = (float(loc), float(scale))
    elif dist_name == "gamma":
        params = [float(shape), float(loc), float(scale)]
        pdf = sst.gamma.pdf
        pdf_args = (float(shape), float(loc), float(scale))
    elif dist_name == "lognormal":
        params = [float(shape), float(loc), float(scale)]
        pdf = sst.lognorm.pdf
        pdf_args = (float(shape), float(loc), float(scale))
    else:  # exponential
        params = [float(loc), float(scale)]
        pdf = sst.expon.pdf
        pdf_args = (float(loc), float(scale))

    grid = np.linspace(float(arr.min()), float(arr.max()), n_grid)
    ys = pdf(grid, *pdf_args)
    out = [{"x_var": float(grid[i]), "y_var": float(ys[i])} for i in range(n_grid)]
    return out, _meta(
        "fit_distribution",
        sourceKeys=None,
        derivedFrom="input_rows",
        distribution=str(dist_name),
        params=params,
    )
```

### 4. Wiring verification

```
grep -n "^def transform_fit_distribution" src/pymyio/transforms.py     # 1
grep -n "\"fit_distribution\": transform_fit_distribution" src/pymyio/transforms.py   # 1
grep -c "_not_implemented" src/pymyio/transforms.py                    # 1 (only the helper def remains)
```

Note: after this phase the only `_not_implemented` match is the helper `def _not_implemented(name, hint)` itself; all six stub *assignments* are gone. Kept per prompt ("stays but is no longer called for the 6 — keep it for any future stubs").

### 5. Gate command

```
.venv/bin/pytest tests/test_transform_fit_distribution.py -q
.venv/bin/pytest tests/test_chart_config.py tests/test_parity.py -q
```

---

## Phase 7 — Cross-cutting: JSON safety + README cleanup

**Per design AC20 and §Requirements impact.**

### 1. File inventory

| File | Action |
|---|---|
| `tests/test_transforms_json_safety.py` | **new** — parametrized over `REGISTRY.keys()` |
| `README.md` | edit — remove the "six of nineteen ... `NotImplementedError`" sentence |

### 2. Red test skeleton

```python
# tests/test_transforms_json_safety.py
import json
import pytest
import numpy as np

from pymyio.transforms import REGISTRY


_RNG = np.random.default_rng(42)


def _xy(n=30):
    xs = _RNG.uniform(0, 10, n)
    ys = 2.0 * xs + 1.0 + _RNG.normal(0, 0.1, n)
    return [{"x": float(xs[i]), "y": float(ys[i]),
             "_source_key": f"row_{i+1}"} for i in range(n)]


def _groups():
    rows = []
    for i, v in enumerate(_RNG.normal(0, 1, 20)):
        rows.append({"g": "A", "y": float(v), "_source_key": f"A{i}"})
    for i, v in enumerate(_RNG.normal(1, 1, 20)):
        rows.append({"g": "B", "y": float(v), "_source_key": f"B{i}"})
    return rows


def _values():
    return [{"v": float(x), "_source_key": f"r{i}"}
            for i, x in enumerate(_RNG.normal(0, 1, 50))]


def _survival():
    times = _RNG.exponential(1.0, 20)
    statuses = _RNG.integers(0, 2, 20)
    return [{"t": float(times[i]), "s": int(statuses[i]),
             "_source_key": f"s{i}"} for i in range(20)]


# Per-transform fixture table — hard-coded.
FIXTURES = {
    "identity":        (_xy(),          {"x_var": "x", "y_var": "y"}, None),
    "cumulative":      (_xy(),          {"x_var": "x", "y_var": "y"}, None),
    "mean":            (_xy(),          {"x_var": "x", "y_var": "y"}, None),
    "summary":         (_xy(),          {"x_var": "x", "y_var": "y"}, None),
    "lm":              (_xy(),          {"x_var": "x", "y_var": "y"}, None),
    "polynomial":      (_xy(),          {"x_var": "x", "y_var": "y"}, {"degree": 2}),
    "residuals":       (_xy(),          {"x_var": "x", "y_var": "y"}, None),
    "quantiles":       (_xy(),          {"x_var": "x", "y_var": "y"}, None),
    "median":          (_xy(),          {"x_var": "x", "y_var": "y"}, None),
    "outliers":        (_xy(),          {"x_var": "x", "y_var": "y"}, None),
    "ci":              (_xy(),          {"x_var": "x", "y_var": "y"}, None),
    "mean_ci":         (_xy(),          {"x_var": "x", "y_var": "y"}, None),
    "qq":              (_xy(),          {"x_var": "x", "y_var": "y"}, None),
    "loess":           (_xy(),          {"x_var": "x", "y_var": "y"}, None),
    "smooth":          (_xy(),          {"x_var": "x", "y_var": "y"},
                        {"method": "sma", "window": 3}),
    "density":         (_values(),      {"y_var": "v"}, None),
    "survfit":         (_survival(),    {"time": "t", "status": "s"}, None),
    "fit_distribution":(_values(),      {"value": "v"}, None),
    "pairwise_test":   (_groups(),      {"x_var": "g", "y_var": "y"}, None),
}


def test_registry_fixture_coverage():
    """Enforces 1:1 between REGISTRY and FIXTURES. If a new transform is
    added without a corresponding FIXTURES entry, this test fails fast
    before the parametrized runs give confusing per-case errors."""
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

    Cross-cutting in Phase 7 rather than per-phase: REGISTRY covers all 19
    entries including the 6 new transforms. Any non-seeded RNG inside a
    transform surfaces here as a failure.
    """
    records, mapping, options = FIXTURES[name]
    fn = REGISTRY[name]
    out_a, meta_a = fn(records, mapping, options)
    out_b, meta_b = fn(records, mapping, options)
    assert out_a == out_b, f"{name}: records differ between invocations"
    assert meta_a == meta_b, f"{name}: meta differs between invocations"
```

**Red command (before edits / before Phases 1–6 done):**
```
.venv/bin/pytest tests/test_transforms_json_safety.py -q
```
Expected during pre-Phase-1: `NotImplementedError` for the six stubs. After Phase 6 all six run; remaining failures would be real `numpy.generic` leaks.

### 3. Green implementation

No new transform code. If `test_transforms_json_safety.py` flags a numpy leak in any transform (existing or new), fix it at the offending call site with an explicit `float()` / `int()` cast. Expected fixes: none, because Phases 1–6 hard-cast every numeric at emission.

Edit `README.md`. Pre-verify the target text exists (both greps must match before editing; if either returns 0 the README has drifted and the edit must be scoped by re-reading the current file):

```
grep -n "PYMYIO-T0" README.md             # expect ≥ 1 match
grep -n "NotImplementedError" README.md   # expect ≥ 1 match
```

When both pre-checks succeed, delete the sentence beginning "six of nineteen R-side numeric transforms" (which through the README also removes the `NotImplementedError` and `PYMYIO-T01..T05` tokens — they all sit in that one sentence). Do not replace it with any other text. Leave the version in `pyproject.toml` and `src/pymyio/__init__.py` untouched — per user directive, bumps happen in a separate release commit.

If the pre-check greps return zero matches (README has already been edited or the sentence was rewritten), skip the Edit and proceed. The Phase 7 wiring verification below will re-assert final state (zero matches for both tokens).

### 4. Wiring verification

```
grep -c "_not_implemented" src/pymyio/transforms.py                 # 1 (only the helper def)
grep -c "NotImplementedError" src/pymyio/transforms.py              # 1 (inside _not_implemented)
grep -n "NotImplementedError" README.md                             # 0
grep -n "PYMYIO-T0" README.md                                       # 0
grep -c "version\s*=" pyproject.toml                                # unchanged (still 0.1.0)
```

### 5. Gate command

```
.venv/bin/pytest tests/test_transforms_json_safety.py -q
.venv/bin/pytest -q        # full suite must be green
```

Full-suite green closes the design.

---

## Phase ordering summary

| Phase | Deliverable | `_not_implemented` count after |
|---|---|---|
| 0 | deps, imports, enums, conftest | 7 (unchanged stubs) |
| 1 | loess | 6 |
| 2 | smooth | 5 |
| 3 | density | 4 |
| 4 | pairwise_test | 3 |
| 5 | survfit | 2 |
| 6 | fit_distribution | 1 (helper def only) |
| 7 | JSON-safety guard + README cleanup | 1 |

Each phase is self-contained: red → green → grep → gate. Do not merge phases. Do not skip the regression gate (`test_chart_config.py tests/test_parity.py`) at any phase.

---

## Task Manifest

Tasks map 1:1 to phases; per-phase gates reference commands inside that phase. Routing rule: `claude-code` for multi-file changes that touch both `transforms.py` and a new test file (phases 1–6); `codex` for self-contained new test files from clear spec (phase 7 cross-cutting tests + docs-only README edit). The six transform phases are serial because each edits `src/pymyio/transforms.py` — parallel dispatch would race.

| Task | Agent | Files | Depends On | Gate | Status |
|------|-------|-------|------------|------|--------|
| T1: Phase 0 — add numpy + scipy deps, imports, enum tuples, shared fixtures | claude-code | `pyproject.toml`, `src/pymyio/transforms.py`, `tests/conftest.py` | — | `.venv/bin/pip install -e ".[dev]" && .venv/bin/pytest tests/test_chart_config.py tests/test_parity.py -q` | pending |
| T2: Phase 1 — implement `transform_loess` with tricube-weighted local linear regression; create `test_transform_loess.py` | claude-code | `src/pymyio/transforms.py`, `tests/test_transform_loess.py` | T1 | `.venv/bin/pytest tests/test_transform_loess.py tests/test_chart_config.py tests/test_parity.py -q` | pending |
| T3: Phase 2 — implement `transform_smooth` (SMA + EMA); create `test_transform_smooth.py` | claude-code | `src/pymyio/transforms.py`, `tests/test_transform_smooth.py` | T2 | `.venv/bin/pytest tests/test_transform_smooth.py tests/test_chart_config.py tests/test_parity.py -q` | pending |
| T4: Phase 3 — implement `transform_density` with scipy.stats.gaussian_kde; create `test_transform_density.py` | claude-code | `src/pymyio/transforms.py`, `tests/test_transform_density.py` | T3 | `.venv/bin/pytest tests/test_transform_density.py tests/test_chart_config.py tests/test_parity.py -q` | pending |
| T5: Phase 4 — implement `transform_pairwise_test` with inline Bonferroni/Holm/BH; create `test_transform_pairwise_test.py` | claude-code | `src/pymyio/transforms.py`, `tests/test_transform_pairwise_test.py` | T4 | `.venv/bin/pytest tests/test_transform_pairwise_test.py tests/test_chart_config.py tests/test_parity.py -q` | pending |
| T6: Phase 5 — implement `transform_survfit` (KM + Greenwood CI via scipy.stats.norm.ppf); create `test_transform_survfit.py` | claude-code | `src/pymyio/transforms.py`, `tests/test_transform_survfit.py` | T5 | `.venv/bin/pytest tests/test_transform_survfit.py tests/test_chart_config.py tests/test_parity.py -q` | pending |
| T7: Phase 6 — implement `transform_fit_distribution` (scipy.stats named dists + floc=0); create `test_transform_fit_distribution.py` | claude-code | `src/pymyio/transforms.py`, `tests/test_transform_fit_distribution.py` | T6 | `.venv/bin/pytest tests/test_transform_fit_distribution.py tests/test_chart_config.py tests/test_parity.py -q` | pending |
| T8: Phase 7 — create cross-cutting JSON-safety + determinism test (parametrized over REGISTRY) | codex | `tests/test_transforms_json_safety.py` | T7 | `.venv/bin/pytest tests/test_transforms_json_safety.py -q` | pending |
| T9: Phase 7 — delete the obsolete `NotImplementedError`/`PYMYIO-T01..T05` sentence from `README.md` | codex | `README.md` | T7 | `grep -c "NotImplementedError\|PYMYIO-T0" README.md` returns 0 | pending |
| T10: Full-suite gate | claude-code | — | T8, T9 | `.venv/bin/pytest -q` | pending |

**Parallel group** (after T7 completes): T8 and T9 touch disjoint files (`tests/` vs `README.md`) and have no shared state. `/co-code` may dispatch both simultaneously.

**Serial spine:** T1 → T2 → T3 → T4 → T5 → T6 → T7 → (T8 ∥ T9) → T10.

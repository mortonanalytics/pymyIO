"""Layer-data transforms — Python ports of the R package's transform_registry.

Each transform takes ``(records, mapping, options)`` and returns a tuple of
``(records, meta)`` where ``records`` is the post-transform list of row dicts
and ``meta`` is the corresponding ``transformMeta`` block the JS engine reads.

Statistical transforms (loess, smooth, density, survfit, fit_distribution,
pairwise_test) are implemented Python-natively on numpy + scipy; numeric
output is not guaranteed to match R's ``stats`` package. All 19 registry
entries are live — no stubs.
"""

from __future__ import annotations

import itertools
import math
import warnings
from typing import Any, Callable, List, Mapping, Tuple

import numpy as np
from scipy import linalg as slinalg
from scipy import stats as sst

Records = List[dict]
TransformResult = Tuple[Records, dict]


# ---- Enum cheat sheet (contract §"Enum-value cheat sheet") -----------------

SMOOTH_METHODS = ("sma", "ema")
TEST_METHODS = ("t.test", "wilcox.test")
P_ADJUST_METHODS = ("none", "bonferroni", "holm", "bh")  # alias "BH" -> "bh"
DISTRIBUTIONS = ("normal", "gamma", "lognormal", "exponential")


def _meta(name: str, **details: Any) -> dict:
    return {"name": name, "sourceKeys": None, "derivedFrom": None, **details}


# ---- helpers ---------------------------------------------------------------

def _as_floats(records: Records, col: str) -> List[float]:
    out = []
    for row in records:
        v = row.get(col)
        if v is None or (isinstance(v, float) and math.isnan(v)):
            continue
        out.append(float(v))
    return out


def _mean(xs: List[float]) -> float:
    return sum(xs) / len(xs) if xs else float("nan")


def _variance(xs: List[float], ddof: int = 1) -> float:
    n = len(xs)
    if n - ddof <= 0:
        return float("nan")
    m = _mean(xs)
    return sum((x - m) ** 2 for x in xs) / (n - ddof)


def _quantile(xs: List[float], q: float) -> float:
    """Linear-interpolation quantile (R type 7 default)."""
    if not xs:
        return float("nan")
    s = sorted(xs)
    h = (len(s) - 1) * q
    lo = int(math.floor(h))
    hi = int(math.ceil(h))
    if lo == hi:
        return s[lo]
    return s[lo] + (h - lo) * (s[hi] - s[lo])


def _zip_xy(records: Records, x_col: str, y_col: str) -> Tuple[List[float], List[float]]:
    xs, ys = [], []
    for row in records:
        x, y = row.get(x_col), row.get(y_col)
        if x is None or y is None:
            continue
        if isinstance(x, float) and math.isnan(x):
            continue
        if isinstance(y, float) and math.isnan(y):
            continue
        xs.append(float(x))
        ys.append(float(y))
    return xs, ys


# ---- transforms ------------------------------------------------------------

def transform_identity(records: Records, mapping: Mapping[str, str], options) -> TransformResult:
    return records, _meta("identity")


def transform_cumulative(records: Records, mapping: Mapping[str, str], options) -> TransformResult:
    y_col = mapping["y_var"]
    out, running = [], 0.0
    for row in records:
        v = row.get(y_col)
        if v is None or (isinstance(v, float) and math.isnan(v)):
            continue
        running += float(v)
        out.append({**row, y_col: running})
    return out, _meta("cumulative")


def transform_mean(records: Records, mapping: Mapping[str, str], options) -> TransformResult:
    """Group rows by x_var; emit one row per group with mean(y_var)."""
    x_col, y_col = mapping["x_var"], mapping["y_var"]
    groups: dict = {}
    order: list = []
    for row in records:
        key = row.get(x_col)
        if key not in groups:
            groups[key] = []
            order.append(key)
        v = row.get(y_col)
        if v is not None and not (isinstance(v, float) and math.isnan(v)):
            groups[key].append(float(v))
    out = [{x_col: k, y_col: _mean(groups[k])} for k in order]
    return out, _meta("mean")


def transform_summary(records: Records, mapping: Mapping[str, str], options) -> TransformResult:
    """Per-x summary: mean, sd, n, low_y/high_y as mean +/- sd."""
    x_col, y_col = mapping["x_var"], mapping["y_var"]
    groups: dict = {}
    order: list = []
    for row in records:
        key = row.get(x_col)
        if key not in groups:
            groups[key] = []
            order.append(key)
        v = row.get(y_col)
        if v is not None and not (isinstance(v, float) and math.isnan(v)):
            groups[key].append(float(v))
    out = []
    for k in order:
        vals = groups[k]
        m = _mean(vals)
        sd = math.sqrt(_variance(vals)) if len(vals) > 1 else 0.0
        out.append({
            x_col: k, y_col: m,
            "mean": m, "sd": sd, "n": len(vals),
            "low_y": m - sd, "high_y": m + sd,
        })
    return out, _meta("summary")


def transform_lm(records: Records, mapping: Mapping[str, str], options) -> TransformResult:
    """Ordinary least-squares fit; emits the fitted line over the x range."""
    x_col, y_col = mapping["x_var"], mapping["y_var"]
    xs, ys = _zip_xy(records, x_col, y_col)
    if len(xs) < 2:
        return records, _meta("lm", note="insufficient data")
    n = len(xs)
    mean_x, mean_y = _mean(xs), _mean(ys)
    sxx = sum((x - mean_x) ** 2 for x in xs)
    sxy = sum((x - mean_x) * (y - mean_y) for x, y in zip(xs, ys))
    if sxx == 0:
        return records, _meta("lm", note="zero variance in x")
    slope = sxy / sxx
    intercept = mean_y - slope * mean_x
    sorted_xs = sorted(set(xs))
    fitted = [{x_col: x, y_col: intercept + slope * x} for x in sorted_xs]
    return fitted, _meta("lm", slope=slope, intercept=intercept)


def transform_polynomial(records: Records, mapping: Mapping[str, str], options) -> TransformResult:
    """Polynomial least-squares of degree `options['degree']` (default 2)."""
    degree = int((options or {}).get("degree", 2))
    x_col, y_col = mapping["x_var"], mapping["y_var"]
    xs, ys = _zip_xy(records, x_col, y_col)
    if len(xs) <= degree:
        return records, _meta("polynomial", note="insufficient data", degree=degree)
    coeffs = _polyfit(xs, ys, degree)
    sorted_xs = sorted(set(xs))
    fitted = [{x_col: x, y_col: _polyval(coeffs, x)} for x in sorted_xs]
    return fitted, _meta("polynomial", degree=degree, coefficients=list(coeffs))


def transform_residuals(records: Records, mapping: Mapping[str, str], options) -> TransformResult:
    """Subtract the OLS fit from y; emit (x, residual)."""
    x_col, y_col = mapping["x_var"], mapping["y_var"]
    xs, ys = _zip_xy(records, x_col, y_col)
    if len(xs) < 2:
        return records, _meta("residuals", note="insufficient data")
    mean_x, mean_y = _mean(xs), _mean(ys)
    sxx = sum((x - mean_x) ** 2 for x in xs)
    sxy = sum((x - mean_x) * (y - mean_y) for x, y in zip(xs, ys))
    slope = sxy / sxx if sxx else 0.0
    intercept = mean_y - slope * mean_x
    out = [{x_col: x, y_col: y - (intercept + slope * x)} for x, y in zip(xs, ys)]
    return out, _meta("residuals", slope=slope, intercept=intercept)


def transform_quantiles(records: Records, mapping: Mapping[str, str], options) -> TransformResult:
    """Per-x five-number summary (boxplot stats)."""
    x_col, y_col = mapping["x_var"], mapping["y_var"]
    groups: dict = {}
    order: list = []
    for row in records:
        key = row.get(x_col)
        if key not in groups:
            groups[key] = []
            order.append(key)
        v = row.get(y_col)
        if v is not None and not (isinstance(v, float) and math.isnan(v)):
            groups[key].append(float(v))
    out = []
    for k in order:
        vals = groups[k]
        out.append({
            x_col: k,
            "q0": _quantile(vals, 0.0),
            "q1": _quantile(vals, 0.25),
            "median": _quantile(vals, 0.5),
            "q3": _quantile(vals, 0.75),
            "q4": _quantile(vals, 1.0),
            "n": len(vals),
        })
    return out, _meta("quantiles")


def transform_median(records: Records, mapping: Mapping[str, str], options) -> TransformResult:
    x_col, y_col = mapping["x_var"], mapping["y_var"]
    groups: dict = {}
    order: list = []
    for row in records:
        key = row.get(x_col)
        if key not in groups:
            groups[key] = []
            order.append(key)
        v = row.get(y_col)
        if v is not None and not (isinstance(v, float) and math.isnan(v)):
            groups[key].append(float(v))
    out = [{x_col: k, y_col: _quantile(groups[k], 0.5)} for k in order]
    return out, _meta("median")


def transform_outliers(records: Records, mapping: Mapping[str, str], options) -> TransformResult:
    """Per-x rows flagged as outliers under the 1.5*IQR rule."""
    x_col, y_col = mapping["x_var"], mapping["y_var"]
    groups: dict = {}
    for row in records:
        groups.setdefault(row.get(x_col), []).append(row)
    out = []
    for key, rows in groups.items():
        ys = [r.get(y_col) for r in rows if isinstance(r.get(y_col), (int, float))]
        if len(ys) < 4:
            continue
        q1, q3 = _quantile(ys, 0.25), _quantile(ys, 0.75)
        iqr = q3 - q1
        lo, hi = q1 - 1.5 * iqr, q3 + 1.5 * iqr
        for r in rows:
            v = r.get(y_col)
            if isinstance(v, (int, float)) and (v < lo or v > hi):
                out.append(r)
    return out, _meta("outliers")


def transform_ci(records: Records, mapping: Mapping[str, str], options) -> TransformResult:
    """Return a shaded band: per-x mean +/- z*sd/sqrt(n)."""
    level = float((options or {}).get("ci_level", 0.95))
    z = _normal_quantile(0.5 + level / 2)
    x_col, y_col = mapping["x_var"], mapping["y_var"]
    groups: dict = {}
    order: list = []
    for row in records:
        key = row.get(x_col)
        if key not in groups:
            groups[key] = []
            order.append(key)
        v = row.get(y_col)
        if v is not None and not (isinstance(v, float) and math.isnan(v)):
            groups[key].append(float(v))
    out = []
    for k in order:
        vals = groups[k]
        if not vals:
            continue
        m = _mean(vals)
        se = math.sqrt(_variance(vals) / len(vals)) if len(vals) > 1 else 0.0
        out.append({x_col: k, y_col: m, "low_y": m - z * se, "high_y": m + z * se})
    return out, _meta("ci", level=level)


def transform_mean_ci(records: Records, mapping: Mapping[str, str], options) -> TransformResult:
    return transform_ci(records, mapping, options)


def transform_qq(records: Records, mapping: Mapping[str, str], options) -> TransformResult:
    """Sample vs theoretical-normal quantiles."""
    y_col = mapping["y_var"]
    ys = sorted(_as_floats(records, y_col))
    n = len(ys)
    if n == 0:
        return records, _meta("qq", note="empty data")
    pts = []
    for i, y in enumerate(ys, start=1):
        p = (i - 0.5) / n
        pts.append({"x_var": _normal_quantile(p), "y_var": y})
    return pts, _meta("qq")


# ---- not implemented (require scipy / specialized stats) ------------------

def _not_implemented(name: str, hint: str) -> Callable[..., TransformResult]:
    def _fn(records, mapping, options):
        raise NotImplementedError(
            f"transform '{name}' is not yet implemented in pymyIO. {hint}"
        )
    return _fn


def transform_loess(records: Records, mapping: Mapping[str, str], options) -> TransformResult:
    """Tricube-weighted local linear regression on an evenly-spaced grid.

    Python-native smoother (not R-parity). Matches the public shape R's
    ``stats::loess`` → ``predict`` on a ``seq(min, max, length.out=n_grid)``
    grid: returns ``n_grid`` rows keyed by the mapping's column names plus
    a synthetic ``_source_key`` of ``"grid_{i}"`` (1-indexed).
    """
    x_col, y_col = mapping["x_var"], mapping["y_var"]
    xs, ys = _zip_xy(records, x_col, y_col)
    input_keys = [
        r.get("_source_key")
        for r in records
        if r.get(x_col) is not None and r.get(y_col) is not None
        and not (isinstance(r.get(x_col), float) and math.isnan(r.get(x_col)))
        and not (isinstance(r.get(y_col), float) and math.isnan(r.get(y_col)))
    ]
    opts = options or {}
    span = float(opts.get("span", 0.75))
    n_grid = int(opts.get("n_grid", 100))
    if len(xs) < 4:
        warnings.warn(
            "transform_loess requires at least 4 data points; returning empty.",
            UserWarning, stacklevel=2,
        )
        return [], _meta("loess", sourceKeys=[], derivedFrom="input_rows")

    xs_np = np.asarray(xs, dtype=float)
    ys_np = np.asarray(ys, dtype=float)
    grid = np.linspace(float(xs_np.min()), float(xs_np.max()), n_grid)
    k = max(2, int(round(span * len(xs_np))))
    fitted = np.empty(n_grid)
    for i, xq in enumerate(grid):
        dists = np.abs(xs_np - xq)
        bw = float(np.partition(dists, k - 1)[k - 1])  # k-th smallest distance
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
        {x_col: float(grid[i]), y_col: float(fitted[i]),
         "_source_key": f"grid_{i + 1}"}
        for i in range(n_grid)
    ]
    return out, _meta(
        "loess",
        sourceKeys=[str(k) for k in input_keys if k is not None],
        derivedFrom="input_rows",
    )
def transform_smooth(records: Records, mapping: Mapping[str, str], options) -> TransformResult:
    """Simple or exponential moving average over x-sorted data.

    SMA: centered moving average via np.convolve (edge rows dropped).
    EMA: recursive alpha-blended update, seeded with the first value.
    """
    x_col, y_col = mapping["x_var"], mapping["y_var"]
    opts = options or {}
    method = opts.get("method", "sma")
    if method not in SMOOTH_METHODS:
        raise ValueError(
            f"transform_smooth: unknown method {method!r}. "
            f"Valid methods: {', '.join(SMOOTH_METHODS)} (sma or ema)."
        )

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
                f"transform_smooth: window={window} exceeds data length "
                f"{len(ys)}; clamping.",
                UserWarning, stacklevel=2,
            )
            window = len(ys)
        if window < 1:
            window = 1
        kernel = np.ones(window, dtype=float) / window
        smoothed = np.convolve(ys, kernel, mode="valid")
        drop = (window - 1) // 2
        drop_right = window - 1 - drop
        x_mid = xs[drop:len(xs) - drop_right] if drop_right else xs[drop:]
        k_mid = keys[drop:len(keys) - drop_right] if drop_right else keys[drop:]
        out = [
            {x_col: float(x_mid[i]), y_col: float(smoothed[i]),
             "_source_key": k_mid[i] if k_mid[i] is not None
                             else f"row_{drop + i + 1}"}
            for i in range(len(smoothed))
        ]
    else:  # ema
        alpha = float(opts.get("alpha", 0.3))
        if not (0.0 < alpha <= 1.0):
            raise ValueError(
                f"transform_smooth: alpha must be in (0, 1]; got {alpha!r}."
            )
        smoothed = np.empty_like(ys)
        smoothed[0] = ys[0]
        for i in range(1, len(ys)):
            smoothed[i] = alpha * ys[i] + (1.0 - alpha) * smoothed[i - 1]
        out = [
            {x_col: float(xs[i]), y_col: float(smoothed[i]),
             "_source_key": keys[i] if keys[i] is not None else f"row_{i + 1}"}
            for i in range(len(ys))
        ]
    return out, _meta(
        "smooth",
        sourceKeys=[r["_source_key"] for r in out],
        derivedFrom="input_rows",
    )
def transform_density(records: Records, mapping: Mapping[str, str], options) -> TransformResult:
    """Gaussian KDE on the ``y_var`` column, evaluated on a 128-point grid.

    Uses ``scipy.stats.gaussian_kde`` with Scott's rule by default (pass a
    numeric ``bandwidth`` option to override). Returns rows keyed by the
    literal strings ``"x_var"``, ``"low_y"``, ``"high_y"`` — these are NOT
    interpolated from the mapping.
    """
    y_col = mapping["y_var"]
    opts = options or {}
    mirror = bool(opts.get("mirror", False))
    n_grid = int(opts.get("n_grid", 128))
    bandwidth = opts.get("bandwidth", None)

    ys = [
        float(r[y_col]) for r in records
        if r.get(y_col) is not None
        and not (isinstance(r[y_col], float) and math.isnan(r[y_col]))
    ]
    if not ys:
        warnings.warn("transform_density: empty input.", UserWarning, stacklevel=2)
        return [], _meta("density", sourceKeys=None, derivedFrom="input_rows")

    y_np = np.asarray(ys, dtype=float)
    # Zero-variance pre-check: scipy silently succeeds on constant non-zero
    # input but the resulting density is meaningless. Use np.ptp (peak-to-
    # peak) rather than np.std — float-arithmetic noise leaves std slightly
    # above zero on constant arrays (e.g. std([3.14]*50) ~ 8.9e-16).
    if float(np.ptp(y_np)) == 0.0:
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
def transform_survfit(records: Records, mapping: Mapping[str, str], options) -> TransformResult:
    """Kaplan-Meier estimator with optional log-log Greenwood CI bands.

    Pure numpy except for a single ``scipy.stats.norm.ppf`` call that
    computes the confidence-band z-quantile. Returns step-function rows
    with literal string keys; emits a t=0 anchor at survival=1.0.
    """
    t_col, s_col = mapping["time"], mapping["status"]
    opts = options or {}
    conf_int = opts.get("conf_int", 0.95)

    times, statuses, source_keys = [], [], []
    for row in records:
        t, s = row.get(t_col), row.get(s_col)
        key = row.get("_source_key")
        if t is None or s is None:
            warnings.warn(
                "survfit: dropping row with missing time or status.",
                UserWarning, stacklevel=2,
            )
            continue
        try:
            tv = float(t)
        except (TypeError, ValueError):
            warnings.warn(
                "survfit: dropping row with non-numeric time.",
                UserWarning, stacklevel=2,
            )
            continue
        if math.isnan(tv) or tv < 0:
            warnings.warn(
                "survfit: dropping row with NaN or negative time.",
                UserWarning, stacklevel=2,
            )
            continue
        if isinstance(s, bool):
            sv = int(s)
        elif isinstance(s, (int, np.integer)) and int(s) in (0, 1):
            sv = int(s)
        elif (isinstance(s, float) and not math.isnan(s)
              and float(s) == int(s) and int(s) in (0, 1)):
            sv = int(s)
        else:
            raise ValueError(
                f"survfit: status value {s!r} is not coercible to 0/1 or bool. "
                "Pass 0 = censored, 1 = event."
            )
        times.append(tv)
        statuses.append(sv)
        source_keys.append(key)

    if not times:
        return [], _meta(
            "survfit", sourceKeys=[], derivedFrom="input_rows",
            conf_int=conf_int,
        )

    ts = np.asarray(times, dtype=float)
    ss = np.asarray(statuses, dtype=int)
    order = np.argsort(ts)
    ts = ts[order]
    ss = ss[order]
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
def transform_fit_distribution(records: Records, mapping: Mapping[str, str], options) -> TransformResult:
    """MLE fit of a named distribution, evaluated as a PDF on a grid.

    Supported distributions: ``normal``, ``gamma``, ``lognormal``,
    ``exponential``. ``scipy.stats`` provides the fits; positive-support
    distributions pin ``floc=0`` to drop the nuisance location. Output
    rows use LITERAL keys ``"x_var"``/``"y_var"`` (not interpolated).
    """
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

    if dist_name in ("gamma", "lognormal") and np.any(arr <= 0):
        raise ValueError(
            f"transform_fit_distribution: {dist_name} requires "
            "strictly positive values."
        )
    if dist_name == "exponential" and np.any(arr < 0):
        raise ValueError(
            "transform_fit_distribution: exponential requires "
            "non-negative values."
        )

    # scipy's FitDataError is a ValueError subclass (verified in 1.17).
    # Catch ValueError broadly to avoid a private scipy import path. The
    # post-fit degeneracy check for normal (scale==0 silently returned)
    # happens AFTER the try so it is not re-wrapped with positivity text.
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
        raise ValueError(
            f"transform_fit_distribution: {dist_name} fit failed — "
            f"positivity / data-domain violation: {e}"
        ) from e

    if dist_name == "normal":
        if float(scale) == 0.0:
            raise ValueError(
                "transform_fit_distribution: normal fit degenerate "
                "(scale==0); zero-variance input."
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
    out = [
        {"x_var": float(grid[i]), "y_var": float(ys[i])}
        for i in range(n_grid)
    ]
    return out, _meta(
        "fit_distribution",
        sourceKeys=None,
        derivedFrom="input_rows",
        distribution=str(dist_name),
        params=params,
    )
def _adjust_p(raw_p, method):
    """Multiple-testing correction for a list of raw p-values.

    Supports ``"none"`` / ``None``, ``"bonferroni"``, ``"holm"`` (step-down),
    and ``"bh"`` (Benjamini-Hochberg step-up). ``None``/NaN p-values pass
    through unchanged — they never reach the adjustment frontier.
    """
    if method in ("none", None):
        return list(raw_p)
    n = sum(1 for p in raw_p if p is not None and not math.isnan(p))
    if n == 0:
        return list(raw_p)
    if method == "bonferroni":
        return [
            None if p is None else (None if math.isnan(p) else min(1.0, float(p) * n))
            for p in raw_p
        ]
    if method == "holm":
        idx = sorted(
            [i for i, p in enumerate(raw_p) if p is not None and not math.isnan(p)],
            key=lambda i: raw_p[i],
        )
        adj = list(raw_p)
        cur_max = 0.0
        for rank, i in enumerate(idx):
            v = min(1.0, float(raw_p[i]) * (n - rank))
            cur_max = max(cur_max, v)
            adj[i] = float(cur_max)
        return adj
    if method == "bh":
        idx = sorted(
            [i for i, p in enumerate(raw_p) if p is not None and not math.isnan(p)],
            key=lambda i: raw_p[i],
        )
        adj = list(raw_p)
        running_min = 1.0
        for rank in range(len(idx) - 1, -1, -1):
            i = idx[rank]
            v = min(1.0, float(raw_p[i]) * n / (rank + 1))
            running_min = min(running_min, v)
            adj[i] = float(running_min)
        return adj
    raise ValueError(
        f"Unknown p_adjust method {method!r}. "
        "Valid: none, bonferroni, holm, bh (alias BH)."
    )


def _pairwise_label(p):
    """R-style significance label matching stars on the p-value."""
    if p is None:
        return "p = NA"
    if p < 0.001:
        return "p < 0.001 ***"
    if p < 0.01:
        return f"p = {p:.3f} **"
    if p < 0.05:
        return f"p = {p:.3f} *"
    return f"p = {p:.2f} ns"


def transform_pairwise_test(records: Records, mapping: Mapping[str, str], options) -> TransformResult:
    """Pairwise hypothesis test with optional multiple-testing correction.

    Returns bracket rows with literal string keys (``x1``, ``x2``, ``y``,
    ``group1``, ``group2``, ``p_value``, ``label``, ``method``, ``statistic``)
    stacked vertically over the y_var range.
    """
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
                f"transform_pairwise_test: y_var must be numeric; "
                f"got {type(y).__name__} for group {g!r}."
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
        # DA §2 finding 4: scipy may return nan p-value silently.
        if math.isnan(p):
            raw_stats.append(None)
            raw_ps.append(None)
        else:
            raw_stats.append(stat)
            raw_ps.append(p)
    adj_ps = _adjust_p(raw_ps, p_adjust)

    all_y = [y for g in order for y in groups[g]]
    y_min = float(min(all_y))
    y_max = float(max(all_y))
    y_range = (y_max - y_min) or 1.0
    step = step_fraction * y_range

    pos = {g: i + 1 for i, g in enumerate(order)}
    order_idx = sorted(
        range(len(pairs)),
        key=lambda i: abs(pos[pairs[i][1]] - pos[pairs[i][0]]),
    )
    level_for = [0] * len(pairs)
    for k, i in enumerate(order_idx):
        level_for[i] = k
    out = []
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


# ---- registry --------------------------------------------------------------

REGISTRY: dict = {
    "identity": transform_identity,
    "cumulative": transform_cumulative,
    "mean": transform_mean,
    "summary": transform_summary,
    "lm": transform_lm,
    "polynomial": transform_polynomial,
    "residuals": transform_residuals,
    "quantiles": transform_quantiles,
    "median": transform_median,
    "outliers": transform_outliers,
    "ci": transform_ci,
    "mean_ci": transform_mean_ci,
    "qq": transform_qq,
    "loess": transform_loess,
    "smooth": transform_smooth,
    "density": transform_density,
    "survfit": transform_survfit,
    "fit_distribution": transform_fit_distribution,
    "pairwise_test": transform_pairwise_test,
}


def get_transform(name: str) -> Callable[..., TransformResult]:
    if name not in REGISTRY:
        raise ValueError(
            f"Unknown transform '{name}'. Available transforms: "
            f"{', '.join(REGISTRY)}."
        )
    return REGISTRY[name]


# ---- numeric helpers -------------------------------------------------------

def _polyfit(xs: List[float], ys: List[float], degree: int) -> List[float]:
    """Solve Vandermonde least squares without numpy: returns highest-degree-first."""
    n = degree + 1
    # Build normal equations A^T A c = A^T y where A_{ij} = xs[i]^j
    ata = [[0.0] * n for _ in range(n)]
    aty = [0.0] * n
    for x, y in zip(xs, ys):
        powers = [x ** j for j in range(n)]
        for i in range(n):
            aty[i] += powers[i] * y
            for j in range(n):
                ata[i][j] += powers[i] * powers[j]
    coeffs_low_first = _solve(ata, aty)
    return list(reversed(coeffs_low_first))


def _polyval(coeffs_high_first: List[float], x: float) -> float:
    """Horner-rule evaluation; coeffs are highest-degree first."""
    out = 0.0
    for c in coeffs_high_first:
        out = out * x + c
    return out


def _solve(a: List[List[float]], b: List[float]) -> List[float]:
    """Gauss-Jordan elimination on a small dense system."""
    n = len(b)
    m = [row[:] + [b[i]] for i, row in enumerate(a)]
    for i in range(n):
        pivot = max(range(i, n), key=lambda r: abs(m[r][i]))
        m[i], m[pivot] = m[pivot], m[i]
        if m[i][i] == 0:
            raise ValueError("Singular matrix in least-squares solve.")
        for r in range(n):
            if r == i:
                continue
            factor = m[r][i] / m[i][i]
            for c in range(i, n + 1):
                m[r][c] -= factor * m[i][c]
    return [m[i][n] / m[i][i] for i in range(n)]


def _normal_quantile(p: float) -> float:
    """Inverse standard-normal CDF via Acklam's rational approximation."""
    if not 0.0 < p < 1.0:
        raise ValueError("p must be in (0, 1)")
    a = [-3.969683028665376e+01,  2.209460984245205e+02, -2.759285104469687e+02,
          1.383577518672690e+02, -3.066479806614716e+01,  2.506628277459239e+00]
    b = [-5.447609879822406e+01,  1.615858368580409e+02, -1.556989798598866e+02,
          6.680131188771972e+01, -1.328068155288572e+01]
    c = [-7.784894002430293e-03, -3.223964580411365e-01, -2.400758277161838e+00,
         -2.549732539343734e+00,  4.374664141464968e+00,  2.938163982698783e+00]
    d = [ 7.784695709041462e-03,  3.224671290700398e-01,  2.445134137142996e+00,
          3.754408661907416e+00]
    plow, phigh = 0.02425, 1 - 0.02425
    if p < plow:
        q = math.sqrt(-2 * math.log(p))
        return (((((c[0]*q + c[1])*q + c[2])*q + c[3])*q + c[4])*q + c[5]) / \
               ((((d[0]*q + d[1])*q + d[2])*q + d[3])*q + 1)
    if p <= phigh:
        q = p - 0.5
        r = q * q
        return (((((a[0]*r + a[1])*r + a[2])*r + a[3])*r + a[4])*r + a[5]) * q / \
               (((((b[0]*r + b[1])*r + b[2])*r + b[3])*r + b[4])*r + 1)
    q = math.sqrt(-2 * math.log(1 - p))
    return -(((((c[0]*q + c[1])*q + c[2])*q + c[3])*q + c[4])*q + c[5]) / \
            ((((d[0]*q + d[1])*q + d[2])*q + d[3])*q + 1)

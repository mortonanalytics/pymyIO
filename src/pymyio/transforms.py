"""Layer-data transforms — Python ports of the R package's transform_registry.

Each transform takes ``(records, mapping, options)`` and returns a tuple of
``(records, meta)`` where ``records`` is the post-transform list of row dicts
and ``meta`` is the corresponding ``transformMeta`` block the JS engine reads.

A subset of the R registry is implemented natively here. The statistically
heavier transforms (loess, smooth, density, survfit, fit_distribution,
pairwise_test) raise :class:`NotImplementedError` with a pointer to the
roadmap entry tracking their port. Calling code should not catch and silently
ignore — that would create the kind of silent feature gap the R/Python parity
contract explicitly forbids.
"""

from __future__ import annotations

import math
from typing import Any, Callable, List, Mapping, Tuple

Records = List[dict]
TransformResult = Tuple[Records, dict]


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


transform_loess = _not_implemented(
    "loess",
    "Port of stats::loess() pending (needs local-polynomial smoother). "
    "Track in roadmap entry PYMYIO-T01.",
)
transform_smooth = _not_implemented(
    "smooth",
    "Equivalent to loess; tracked under PYMYIO-T01.",
)
transform_density = _not_implemented(
    "density",
    "Kernel density estimation port pending. Track in PYMYIO-T02.",
)
transform_survfit = _not_implemented(
    "survfit",
    "Kaplan-Meier estimator port pending; depends on a survival library. "
    "Track in PYMYIO-T03.",
)
transform_fit_distribution = _not_implemented(
    "fit_distribution",
    "Distribution-fitting port pending (needs MLE for normal/gamma/etc.). "
    "Track in PYMYIO-T04.",
)
transform_pairwise_test = _not_implemented(
    "pairwise_test",
    "Pairwise t-test/Wilcoxon port pending. Track in PYMYIO-T05.",
)


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

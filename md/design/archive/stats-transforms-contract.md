# Statistical Transforms — Layer Contract

Companion to [stats-transforms.md](./stats-transforms.md). Locks names, enums, and return-shape conventions. The design doc is the full spec; this file is the single-source grep target for names and enum values.

## Scope note

pymyIO is a Python library, not a db/api/ui web stack. The skill template's `DB column` / `Rust type` / `TS interface` columns are marked N/A. The real boundary is the Python callable surface of `pymyio.transforms`.

## Entities (transforms)

| Entity | Registry key | Python function | Design slice |
|---|---|---|---|
| loess | `"loess"` | `transform_loess` | §Slice 1 |
| smooth | `"smooth"` | `transform_smooth` | §Slice 2 |
| density | `"density"` | `transform_density` | §Slice 3 |
| pairwise_test | `"pairwise_test"` | `transform_pairwise_test` | §Slice 4 |
| survfit | `"survfit"` | `transform_survfit` | §Slice 5 |
| fit_distribution | `"fit_distribution"` | `transform_fit_distribution` | §Slice 6 |

The registry key matches the R-side name. The Python function name is `transform_<registry_key>` — this convention is already established by the stubs being replaced.

## Required mapping keys (by transform)

| Transform | Mapping keys | Notes |
|---|---|---|
| loess | `x_var`, `y_var` | Both resolved to input column names |
| smooth | `x_var`, `y_var` | Same |
| density | `y_var` | Univariate — the KDE grid provides the x axis |
| pairwise_test | `x_var`, `y_var` | `x_var` resolves to group labels (coerced to str); `y_var` to numeric |
| survfit | `time`, `status` | `time` numeric ≥ 0; `status` coerced bool or int in {0, 1} |
| fit_distribution | `value` | Numeric column |

## Option bags (defaults locked)

| Transform | Option | Type | Default | Enum values |
|---|---|---|---|---|
| loess | `span` | float | `0.75` | — |
| loess | `degree` | int | `2` | accepted but ignored (linear-only, per design OQ1) |
| loess | `n_grid` | int | `100` | — |
| smooth | `method` | str | `"sma"` | `{"sma", "ema"}` |
| smooth | `window` | int | `7` | — (SMA only) |
| smooth | `alpha` | float | `0.3` | — (EMA only; `0 < alpha <= 1`) |
| density | `bandwidth` | None \| float | `None` | numeric passes to scipy; `None` uses Scott's rule |
| density | `mirror` | bool | `False` | — |
| density | `n_grid` | int | `128` | — |
| pairwise_test | `method` | str | `"t.test"` | `{"t.test", "wilcox.test"}` |
| pairwise_test | `p_adjust` | str | `"none"` | `{"none", "bonferroni", "holm", "bh", "BH"}` (BH aliases bh) |
| pairwise_test | `paired` | bool | `False` | — |
| pairwise_test | `conf_level` | float | `0.95` | accepted but unused (forward-compat) |
| pairwise_test | `comparisons` | None \| list[(str, str)] | `None` | `None` means `itertools.combinations(groups, 2)` |
| pairwise_test | `step_fraction` | float | `0.08` | — |
| survfit | `conf_int` | None \| float | `0.95` | `None` disables CI columns; numeric must be in `(0, 1)` |
| fit_distribution | `distribution` | str | `"normal"` | `{"normal", "gamma", "lognormal", "exponential"}` |
| fit_distribution | `n_grid` | int | `128` | — |

## Enum-value cheat sheet

Canonical enum sources for grep + exhaustive-match tests:

| Enum | Values |
|---|---|
| `SMOOTH_METHODS` | `("sma", "ema")` |
| `TEST_METHODS` | `("t.test", "wilcox.test")` |
| `P_ADJUST_METHODS` | `("none", "bonferroni", "holm", "bh")` — plus alias `"BH" → "bh"` |
| `DISTRIBUTIONS` | `("normal", "gamma", "lognormal", "exponential")` |

Tests must exercise the full enum set for exhaustiveness.

## Return record keys (literal vs interpolated)

| Transform | Key source | Exact output keys |
|---|---|---|
| loess | **interpolated from mapping** | `mapping["x_var"]`, `mapping["y_var"]`, `"_source_key"` |
| smooth | **interpolated from mapping** | `mapping["x_var"]`, `mapping["y_var"]`, `"_source_key"` |
| density | **LITERAL** | `"x_var"`, `"low_y"`, `"high_y"` |
| pairwise_test | **LITERAL** | `"x1"`, `"x2"`, `"y"`, `"group1"`, `"group2"`, `"p_value"`, `"label"`, `"method"`, `"statistic"` |
| survfit (conf_int set) | **LITERAL** | `"time"`, `"survival"`, `"low_y"`, `"high_y"`, `"n_at_risk"`, `"n_event"` |
| survfit (conf_int=None) | **LITERAL** | `"time"`, `"survival"`, `"n_at_risk"`, `"n_event"` — `low_y`/`high_y` keys OMITTED (not null) |
| fit_distribution | **LITERAL** | `"x_var"`, `"y_var"` |

**This is the most common source of future drift.** density, pairwise_test, survfit, and fit_distribution emit LITERAL string keys that composite expansions and the JS engine read; they do NOT rename when the user passes a different `mapping`.

## Meta shape per transform

All transforms return meta with at least `{"name": <registry_key>, "sourceKeys": ..., "derivedFrom": "input_rows"}`. The `sourceKeys` sentinel follows a fixed convention:

| Transform | `sourceKeys` | Rationale |
|---|---|---|
| loess | `[<input _source_key values that survived NaN filter>]` | Row-derived via grid, but input provenance is trackable |
| smooth | `[<output row _source_key values in order>]` | Row-preserving |
| density | `null` | Aggregate |
| pairwise_test | `null` | Aggregate |
| survfit | `[<_source_key values of rows that survived data-quality filter>]` | Row-preserving |
| fit_distribution | `null` | Aggregate |

Empty passthrough (input fully filtered out) → `[]` for the row-derived transforms, not `null`.

Additional meta keys per transform:
- **fit_distribution** also emits `"distribution": <name>`, `"params": [float, ...]`.
- **survfit** also emits `"conf_int": <level or None>`.

## Error / warning contract

| Error / warning | Raised when | Raised by |
|---|---|---|
| `ValueError` | unknown `smooth.method` | `transform_smooth` |
| `ValueError` | unknown `pairwise_test.method` | `transform_pairwise_test` |
| `ValueError` | unknown `pairwise_test.p_adjust` | `transform_pairwise_test` |
| `ValueError` | fewer than 2 groups in `pairwise_test` | `transform_pairwise_test` |
| `TypeError` | non-numeric `y_var` for `pairwise_test` | `transform_pairwise_test` |
| `ValueError` | status value not coercible to bool/{0,1} | `transform_survfit` |
| `ValueError` | empty input for `fit_distribution` | `transform_fit_distribution` |
| `ValueError` | unknown `fit_distribution.distribution` | `transform_fit_distribution` |
| `ValueError` | domain violation (lognormal/gamma on non-positive, exponential on negative) | `transform_fit_distribution` |
| `ValueError` | zero-variance input for `fit_distribution` normal (scale==0 post-fit) | `transform_fit_distribution` |
| `warnings.warn` (UserWarning) | degenerate input (<4 points for loess, empty/constant/zero-var for density, all-censored for survfit, etc.) | applicable transform |
| `warnings.warn` | >15 pairwise comparisons | `transform_pairwise_test` |
| `warnings.warn` | SMA window > data length (clamped) | `transform_smooth` |

## Dependencies

Added to `[project].dependencies`:

| Package | Pin | Used by |
|---|---|---|
| `numpy` | `>=1.24` | all 6 |
| `scipy` | `>=1.11` | density, pairwise_test, survfit (norm.ppf only), fit_distribution |

Explicitly NOT added: `statsmodels`, `lifelines`, `pandas`. Design §Dependency decision.

## Cross-slice rules (summary)

From design §"Feature slices" front matter — restated as a mechanical checklist implementation must satisfy:

1. **JSON safety.** Every numeric field in records and meta is hard-cast to native Python `float`/`int`/`bool` before return. No `numpy.generic` subclass may leak. Enforced by `tests/test_transforms_json_safety.py`.
2. **Determinism.** Given identical inputs (and seeded RNG where applicable), two consecutive invocations of any transform produce byte-identical output.
3. **`_source_key` discipline.** Either forwarded from input (smooth, survfit) or synthesized as `"grid_{i}"` (loess, density, fit_distribution) — never omitted from row-derived transforms.
4. **Registry wiring.** Each new implementation replaces the existing `_not_implemented(...)` stub in `REGISTRY` at its existing key. No new keys added.

## File locations

| File | Action | Owner |
|---|---|---|
| `src/pymyio/transforms.py` | **edit** — replace 6 stubs, add numpy/scipy imports, add enum constants | implementation |
| `pyproject.toml` | **edit** — append `numpy` and `scipy` to `[project].dependencies` | implementation |
| `tests/test_transform_loess.py` | **new** | implementation |
| `tests/test_transform_smooth.py` | **new** | implementation |
| `tests/test_transform_density.py` | **new** | implementation |
| `tests/test_transform_pairwise_test.py` | **new** | implementation |
| `tests/test_transform_survfit.py` | **new** | implementation |
| `tests/test_transform_fit_distribution.py` | **new** | implementation |
| `tests/test_transforms_json_safety.py` | **new** — parametrized over `REGISTRY.keys()` | implementation |
| `tests/conftest.py` | **new** — shared fixtures (seeded RNG, sample data per transform) | implementation |
| `README.md` | **edit** — remove the "six of nineteen ... currently raise `NotImplementedError`" sentence | implementation |

## Naming authority

If the implementation produces any name not listed in this contract file, the contract wins. Update the implementation to match.

# Roadmap

## Transform ports

| ID | Item | Target | Disposition |
|----|------|--------|-------------|
| PYMYIO-T01 | `loess` / `smooth` transforms | 0.2.0 | Deferred — needs local-polynomial smoother. |
| PYMYIO-T02 | `density` transform | 0.2.0 | Deferred — needs KDE. |
| PYMYIO-T03 | `survfit` transform | 0.3.0 | Deferred — needs Kaplan-Meier. |
| PYMYIO-T04 | `fit_distribution` transform | 0.3.0 | Deferred — needs MLE for normal/gamma/etc. |
| PYMYIO-T05 | `pairwise_test` transform | 0.3.0 | Deferred — needs t/Wilcoxon. |

## Composite-expansion bugs (block boxplot / violin / ridgeline / qq)

| ID | Item | Target | Notes |
|----|------|--------|-------|
| PYMYIO-C01 | Port `composite_boxplot()` from R-myIO | 0.2.0 | R expands boxplot into primitive bar/line/point layers; pymyio still emits a single `type: "boxplot"` layer that the engine can't render ("Unknown renderer type: boxplot"). |
| PYMYIO-C02 | Port `composite_violin()` from R-myIO | 0.2.0 | Same shape as C01. |
| PYMYIO-C03 | Port `composite_ridgeline()` from R-myIO | 0.2.0 | Same shape as C01. |
| PYMYIO-C04 | Fix `qq` transform to write back to mapped column names | 0.2.0 | Transform produces records keyed by literal `x_var`/`y_var`; the point renderer reads via `mapping[x_var]`/`mapping[y_var]` (which point at the user's column names). |
| PYMYIO-C05 | Make required-mapping check transform-aware | 0.2.0 | Blocks `rangeBar` + `mean_ci` and `area` + band form (`{x_var, low_y, high_y}` without `y_var`). |

## What works today

All 13 numeric transforms below are implemented natively (no scipy required):

`identity`, `cumulative`, `mean`, `summary`, `lm`, `polynomial`, `residuals`,
`quantiles`, `median`, `outliers`, `ci`, `mean_ci`, `qq`.

All 34 chart types accept layer specs and emit correct JSON. The ones that
depend on deferred transforms (`survfit`, `histogram_fit`, `comparison`)
raise `NotImplementedError` at render time with a pointer back to this page.

## Why `NotImplementedError`, not silent fallbacks

The R/Python parity contract forbids silently degrading a chart — a
`NotImplementedError` makes the gap surface at call time so downstream code
doesn't accidentally ship a half-charted Shiny app to production. See
[`src/pymyio/transforms.py`](https://github.com/mortonanalytics/pymyIO/blob/main/src/pymyio/transforms.py)
for the exact messages each deferred transform produces.

## Getting from 0.1 to 1.0

1. **0.2.0** — smoothers (loess, smooth, density). Unblocks moving-average
   overlays and ridgeline-from-density.
2. **0.3.0** — survival, distribution fitting, pairwise tests. Unblocks
   survival and comparison charts.
3. **1.0.0** — parity declaration: every R myIO feature has a tested Python
   equivalent, the engine SHA is pinned, and the JSON snapshot tests pass
   across both wrappers.

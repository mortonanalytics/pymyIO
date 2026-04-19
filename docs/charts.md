# Chart types

pymyIO renders 34 chart types — the same set as R-myIO. Every `type` below
is a valid value for `MyIO.add_layer(type=...)`.

## Basic

| Type | Required mapping | Notes |
|---|---|---|
| `line` | `x_var`, `y_var` | Add `group` to stack per-series lines. |
| `point` | `x_var`, `y_var` | Pair with `transform="lm"` for a fitted line. |
| `bar` | `x_var`, `y_var` | Call `.define_categorical_axis(x_axis=True)` for categorical x. |
| `groupedBar` | `x_var`, `y_var`, `group` | One bar per group, dodged. |
| `area` | `x_var`, `low_y`, `high_y` | Shaded band between `low_y` and `high_y`. |
| `histogram` | `value` | Bin counts. |

## Statistical

| Type | Required mapping | Notes |
|---|---|---|
| `regression` | `x_var`, `y_var` | Composite: points + fit line. `options={"method": "lm" | "polynomial"}`. |
| `rangeBar` | `x_var`, `low_y`, `high_y` | With `transform="mean_ci"` for mean ± 95% CI. |
| `qq` | `y_var` | Composite; optional `group` for per-group Q-Q. |
| `boxplot` | `x_var`, `y_var` | Composite: box + outliers (1.5×IQR). |
| `violin` | `x_var`, `y_var` | Kernel-density silhouettes. |
| `ridgeline` | `x_var`, `y_var`, `group` | Stacked KDEs per group. |
| `comparison` | `x_var`, `y_var` | :material-alert: uses `pairwise_test` — see [Roadmap](roadmap.md). |

## Specialized

| Type | Required mapping | Notes |
|---|---|---|
| `donut` | `x_var`, `y_var` | Annular pie. |
| `gauge` | `value` | Single-value dial. |
| `treemap` | `level_1`, `level_2` | Hierarchical rectangles. |
| `heatmap` | `x_var`, `y_var`, `value` | Color-encoded matrix. |
| `hexbin` | `x_var`, `y_var`, `radius` | 2D density binning. |
| `calendarHeatmap` | `date`, `value` | GitHub-style contribution calendar. |

## Financial

| Type | Required mapping | Notes |
|---|---|---|
| `candlestick` | `x_var`, `open`, `high`, `low`, `close` | OHLC bars. |
| `waterfall` | `x_var`, `y_var` | Bridge chart; `total` column marks terminal bars. |

## Relational

| Type | Required mapping | Notes |
|---|---|---|
| `sankey` | `source`, `target`, `value` | Flow diagram. |
| `parallel` | `dimensions` | Parallel-coordinates plot. |

## "New" family

| Type | Required mapping | Notes |
|---|---|---|
| `lollipop` | `x_var`, `y_var` | Bar+dot hybrid. |
| `dumbbell` | `x_var`, `low_y`, `high_y` | Two-point range per category. |
| `waffle` | `category`, `value` | 10×10 square grid by share. |
| `beeswarm` | `x_var`, `y_var` | Jittered points with force-directed nudging. |
| `bump` | `x_var`, `y_var`, `group` | Rank transitions over time. |
| `radar` | `axis`, `value` | Polar plot across named axes. |
| `funnel` | `stage`, `value` | Sales / pipeline funnel. |

## Deferred (raise `NotImplementedError` in 0.1.0)

See [Roadmap](roadmap.md) for the landing schedule.

| Type | Reason |
|---|---|
| `survfit` | Needs Kaplan-Meier port. |
| `histogram_fit` | Needs distribution MLE. |

## Composite types

`regression`, `boxplot`, `violin`, `ridgeline`, `comparison`, `qq`, `survfit`,
and `histogram_fit` expand to multiple primitive layers under the hood (e.g.
`regression` = `point` + `line[lm]`). You do not need to stack them
manually — `MyIO.add_layer(type="regression", …)` handles it.

## Layer compatibility

myIO groups layer types by axis style. Compatible groups can coexist on the
same chart; incompatible ones raise at `add_layer()` time:

- `axes-continuous`: `line`, `point`, `area`, `candlestick`, `rangeBar`,
  `text`, `regression`, `bracket`, `comparison`, `qq`, `bump`, `survfit`
- `axes-categorical`: `bar`, `groupedBar`, `waterfall`, `boxplot`, `violin`,
  `lollipop`, `dumbbell`, `beeswarm`
- `axes-binned`: `histogram`, `ridgeline`, `histogram_fit`
- `axes-matrix`: `heatmap`, `calendarHeatmap`
- `axes-hex`: `hexbin`
- `standalone-flow`: `sankey`, `treemap`, `waffle`, `funnel`, `parallel`
- `standalone-radial`: `donut`, `gauge`, `radar`

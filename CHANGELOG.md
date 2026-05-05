# Changelog

All notable changes to pymyIO are documented here.
The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.0] — 2026-05-04

First public release. Python bindings for the
[myIO](https://github.com/mortonanalytics/myIO) d3.js chart library, with
feature parity to the R package's 1.2.0 surface.

### Chart types (34)

`line`, `point`, `bar`, `groupedBar`, `area`, `histogram`, `hexbin`,
`heatmap`, `candlestick`, `waterfall`, `sankey`, `donut`, `gauge`, `treemap`,
`boxplot`, `violin`, `ridgeline`, `regression`, `qq`, `comparison`,
`rangeBar`, `bracket`, `text`, `lollipop`, `dumbbell`, `waffle`, `beeswarm`,
`bump`, `radar`, `funnel`, `parallel`, `survfit`, `histogram_fit`,
`calendarHeatmap`.

### Statistical transforms (19)

`identity`, `lm`, `polynomial`, `loess`, `smooth`, `density`, `mean`,
`mean_ci`, `summary`, `quantiles`, `outliers`, `residuals`, `cumulative`,
`ci`, `pairwise_test`, `qq`, `survfit`, `fit_distribution`, `median`.
All scipy-backed where applicable.

### Composite expansions

`boxplot`, `violin`, `ridgeline`, `qq`, `regression`, `comparison`,
`survfit`, `histogram_fit` — composite chart types decompose into primitive
layers the engine renders directly.

### Interactivity

- `set_brush()` — rectangle selection with reactive output
- `set_annotation()` — click-to-label data points with category colors
- `set_slider()` — parameter sliders with debounced re-render
- `link_charts()` / `set_linked_cursor()` — cross-chart brushing and synced
  crosshair without crosstalk
- `drag_points()` — drag-to-edit point coordinates

### Theming and layout

- `set_theme()` with 12 named presets (`midnight`, `ocean`, `forest`,
  `sunset`, `monochrome`, `neon`, `corporate`, `academic`, `nature`,
  `minimal`, `retro`, `warm`) plus light/dark/auto modes
- `set_facet()` — small-multiples faceting with fixed/free scale modes
- `set_layer_opacity()` — per-layer opacity control
- `set_export_options()` — toggle PNG / SVG / PDF / clipboard / CSV export
  buttons
- Sparkline mode via `MyIO(sparkline=True)`

### Hosts

Tier-1 (CI-tested): JupyterLab, VSCode notebooks, Shiny for Python.
Tier-2 (manual smoke): Colab, marimo, Panel, Solara, Quarto, classic
Notebook.
Static HTML export via `pymyio.to_standalone_html()`.

### Engine

Vendored myIO 1.2.0 (`vendor/myIO` git submodule, materialized into the
wheel via hatchling `force-include`). Single canonical source of truth
shared with the R package.

### Known issues

- `mean_ci` transform on `rangeBar` fails the required-mapping check.
  Workaround: pre-aggregate and pass `low_y`/`high_y` directly. Tracked
  as PYMYIO-C05.

[0.1.0]: https://github.com/mortonanalytics/pymyIO/releases/tag/v0.1.0

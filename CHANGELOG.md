# Changelog

All notable changes to pymyIO are documented here.
The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.2.0] — 2026-05-28

### Changed

- **Engine bump to myIO 1.1.0** (mirrors
  [myIO#53](https://github.com/mortonanalytics/myIO/pull/53)): the vendored d3
  engine is re-pinned to the #53 merge commit, bringing the bundled engine
  current (accessibility work, latest renderers) alongside the validator fix
  below. pymyIO ships the engine and the generated `myio-schema.json`
  byte-exact from this pin.

### Fixed

- **Schema #52 fix** — every single-element list field in `myio-schema.json`
  (`required_mappings`, `numeric_fields`, `valid_transforms`, and
  `function_signatures` values) is now a JSON array instead of a scalar string.
  Previously a single-mapping chart type (e.g. `histogram` → `"value"`) could
  cause a schema-reading validator to iterate the string character-by-character
  and emit one bogus `MISSING_MAPPING` per letter. pymyIO's validators were
  already defended via `_as_list`; the array-normalized schema removes the
  hazard at the source.

### Internal

- New parity tests mirroring upstream: a per-type minimal-spec regression
  (every chart type validates `valid=true` from its schema `required_mappings`),
  an array-normalization lock, and a schema-drift gate asserting the loaded
  schema byte-matches the canonical upstream `inst`/`mcp` contract.
- Added a `tests` GitHub Actions workflow that runs the pytest suite (with the
  myIO engine submodule checked out) on pull requests and `main` — the repo
  previously had no test-running CI.

## [0.1.2] — 2026-05-21

### Added

- **Uncertainty visualizations** (mirrors [myIO#50](https://github.com/mortonanalytics/myIO/pull/50)):
  `quantile_dots` — dotplot of a predictive distribution
  (`transform="quantile_dots"`, `source` one of
  `bootstrap`/`posterior`/`ensemble`/`empirical`) — and `fan`, a composite
  forecast fan of nested prediction-interval bands.
- **LLM tool-calling surface** in `pymyio.tools` (mirrors myIO `R/llm_tools.R`):
  `load_schema`, `list_chart_types`, `get_chart_schema`, `validate_spec`,
  `list_functions`, `get_function_signature`, `validate_call` — plus the
  `myio_*` R-parity aliases and `ERROR_CODES`. Backed by the generated
  `myio-schema.json` (force-included into the wheel at
  `pymyio/myio-schema.json`); the validators are checked against myIO's
  shared cross-language conformance corpus.

### Fixed

- **PYMYIO-C05** — the required-mapping check now runs against the
  transform-injected mapping, so `rangeBar` + `mean_ci` builds without
  pre-aggregation. `area` also accepts an explicit band (`low_y`/`high_y`)
  with no center `y_var`; simple `area` (`x_var`/`y_var`) is unchanged.

### Engine (vendored bundle bump to myIO `d54d6c5` on `main`)

- [myIO#49](https://github.com/mortonanalytics/myIO/pull/49)
  (`[engine-additive]`): distribution charts (boxplot/violin/comparison)
  render categorical group labels via the new `config.axes.xTickLabels`
  map, axis tick formats default to the engine default (empty) instead of
  SI (`"s"`), and comparison significance brackets are no longer dropped.
  `set_axis_format` arguments default to `None` so a label-only call
  preserves previously set formats.
- [myIO#50](https://github.com/mortonanalytics/myIO/pull/50)
  (`[engine-additive]`): uncertainty-visualization renderers
  (`quantile_dots`, `fan`), the LLM tool-calling JSON schema
  (`myio-schema.json`), and an `AreaRenderer` `boundaryStroke` default fix.
  Config `specVersion` is now `2`, matching R `myIO()`.

### CI

- Bumped GitHub Actions off the deprecated Node 20 runtime ahead of the
  2026-06-02 cutover: `checkout@v6`, `setup-python@v6`,
  `upload-artifact@v7`, `download-artifact@v8`, `upload-pages-artifact@v5`,
  `deploy-pages@v5`; dropped the now-redundant `FORCE_JAVASCRIPT_ACTIONS_TO_NODE24`
  stopgap in the Pages workflow.

## [0.1.1] — 2026-05-16

### Added

- `MyIO(title=...)` constructor kwarg and `MyIO.set_title(title)` builder for
  the new in-SVG chart title surface. `set_title(None)` clears. Mirrors R
  `myIO(title=...)` / `setTitle()` from upstream
  [myIO#48](https://github.com/mortonanalytics/myIO/pull/48). Payload writes
  `config.title` (string or `None`).

### Engine (vendored bundle bump to myIO PR #48 tip @ e2fd534)

PR #48 (`[engine-additive]` — additive payload, no breaking changes):

- **Title / axis label / legend rendering.** Titles, `xAxisLabel`,
  `yAxisLabel`, and a compact inline legend now render inside the SVG.
  `set_axis_format(x_label=..., y_label=...)` already passed labels through;
  no Python change required for axis labels.
- **rangeBar errorbar style.** New `options.style = "errorbar"` mode renders
  mean ± CI charts. Layer config:
  `type="rangeBar"`, `options={"style": "errorbar"}`,
  `mapping={"x_var", "low_y", "high_y", "y_var"}`. `y_var` (the mean
  position) is **required** when `style="errorbar"`; omitting it warns to
  the console and skips render. Default style (no `options.style`) keeps
  the existing filled-bar behavior.
- **Horizontal bar charts** render correctly (previously empty + ~186
  console errors).
- **Gauge** charts get traffic-light threshold zones by default.
- **Treemap** labels show full words instead of first-letter abbreviations.
- **Waterfall** draws connector lines between bars.
- **Candlestick / moving-average** x-axis can format as dates via
  `xAxisFormat = "yearMon"` (accepts R-style days-since-1970 or JS
  milliseconds-since-epoch).
- **Multi-series** charts render a compact inline legend in addition to the
  action-sheet legend.

### Fixed

- **flipAxis behavior when `categorical_x=True`.** When a chart had
  `categoricalScale.xAxis = True` AND `flipAxis(True)` with no explicit
  scale hints, the band scale previously stayed on x (the flip was silently
  cancelled). It now correctly moves to y as the flip intends. Users who
  relied on the broken behavior for horizontal categorical charts will see
  their charts render differently. No pymyIO API change.
- `OKABE_ITO_PALETTE[7]` corrected from `#000000` to `#999999` to match R
  upstream and the original Okabe-Ito colorblind-safe palette.
- `to_standalone_html()` inline-asset escape no longer corrupts JS regex
  literals containing `</`. The previous blanket `</` → `<\/` rewrite broke
  patterns like `/</g` (introduced into the engine bundle by PR #48). The
  escape is now narrowed to `</script` and `</style` (the only sequences
  the HTML spec treats as terminators).

### Changed

- `to_standalone_html()` inline-HTML soft-ceiling warning raised from 2 MB
  to 4 MB to absorb the larger engine bundle (now ~2.26 MB) without warning
  on the empty-chart baseline. Oversized-payload warnings still fire as
  intended.

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

[0.1.2]: https://github.com/mortonanalytics/pymyIO/compare/v0.1.1...v0.1.2
[0.1.1]: https://github.com/mortonanalytics/pymyIO/releases/tag/v0.1.1
[0.1.0]: https://github.com/mortonanalytics/pymyIO/releases/tag/v0.1.0

# pymyIO

Python bindings for [myIO](https://github.com/mortonanalytics/myIO) — the
d3.js-based interactive chart library originally shipped as an R package.

`pymyIO` is feature-equivalent to the R package: every R export is reachable
from Python, every chart type renders identically, and the JSON config the
Python builder produces matches what R emits, byte for byte where possible.
Both packages drive the **same** d3 engine (`myIOapi.js`), wired in via a git
submodule so there is one canonical source of truth — no duplicated JS to
drift.

> Status: alpha (0.1.0). API is settled and matches R's `setMargin`/`setBrush`/
> etc. surface; six of nineteen R-side numeric transforms (`loess`, `smooth`,
> `density`, `survfit`, `fit_distribution`, `pairwise_test`) currently raise
> `NotImplementedError` with a roadmap pointer (PYMYIO-T01..T05) — they will
> land before 1.0.

## Installation

```bash
pip install pymyio          # once published to PyPI
```

For development:

```bash
git clone --recurse-submodules https://github.com/mortonanalytics/pymyIO
cd pymyIO
pip install -e ".[dev]"
pytest
```

If you cloned without `--recurse-submodules`, fetch the engine afterwards:

```bash
git submodule update --init --recursive
```

## Quickstart

```python
import pandas as pd
from pymyio import MyIO

mtcars = pd.DataFrame({
    "wt":  [2.62, 2.875, 2.32, 3.215, 3.44, 3.46],
    "mpg": [21.0, 21.0, 22.8, 21.4, 18.7, 18.1],
})

(
    MyIO(data=mtcars)
    .add_layer(type="point", label="points",
               mapping={"x_var": "wt", "y_var": "mpg"}, color="#E69F00")
    .add_layer(type="line", label="trend", transform="lm",
               mapping={"x_var": "wt", "y_var": "mpg"}, color="red")
    .set_axis_format(x_label="Weight (1000 lbs)", y_label="MPG")
)
```

In a Jupyter cell, the trailing expression renders as an interactive widget.
Outside notebooks, call `.render()` to get a `MyIOWidget`, or `.to_config()`
for the underlying JSON spec.

## Supported chart types (34 total)

`line`, `point`, `bar`, `groupedBar`, `area`, `histogram`, `heatmap`,
`hexbin`, `treemap`, `gauge`, `donut`, `candlestick`, `waterfall`, `sankey`,
`boxplot`, `violin`, `ridgeline`, `rangeBar`, `text`, `regression`,
`bracket`, `comparison`, `qq`, `lollipop`, `dumbbell`, `waffle`, `beeswarm`,
`bump`, `radar`, `funnel`, `parallel`, `survfit`, `histogram_fit`,
`calendarHeatmap`.

## R → Python function map

| R export | Python equivalent |
|---|---|
| `myIO()` | `MyIO()` |
| `addIoLayer()` | `MyIO.add_layer()` |
| `setMargin()` | `MyIO.set_margin()` |
| `setAxisFormat()` | `MyIO.set_axis_format()` |
| `setAxisLimits()` | `MyIO.set_axis_limits()` |
| `setColorScheme()` | `MyIO.set_color_scheme()` |
| `setReferenceLines()` | `MyIO.set_reference_lines()` |
| `setTheme()` | `MyIO.set_theme()` |
| `setTransitionSpeed()` | `MyIO.set_transition_speed()` |
| `setToolTipOptions()` | `MyIO.set_tooltip_options()` |
| `defineCategoricalAxis()` | `MyIO.define_categorical_axis()` |
| `flipAxis()` | `MyIO.flip_axis()` |
| `suppressLegend()` | `MyIO.suppress_legend()` |
| `suppressAxis()` | `MyIO.suppress_axis()` |
| `setBrush()` | `MyIO.set_brush()` |
| `setAnnotation()` | `MyIO.set_annotation()` |
| `setExportOptions()` | `MyIO.set_export_options()` |
| `setFacet()` | `MyIO.set_facet()` |
| `setLayerOpacity()` | `MyIO.set_layer_opacity()` |
| `setSlider()` | `MyIO.set_slider()` |
| `setToggle()` | `MyIO.set_toggle()` |
| `setLinkedCursor()` | `MyIO.set_linked_cursor()` |
| `dragPoints()` | `MyIO.drag_points()` |
| `linkCharts()` | `pymyio.link_charts()` (module-level) |
| `setLinked()` | n/a — Crosstalk-specific; use `link_charts()` |
| `myIO_last_error()` | `MyIOWidget.last_error` traitlet |
| `myIOOutput`/`renderMyIO` | n/a — Shiny-specific |

## Reading interactions back into Python

```python
chart = MyIO(data=mtcars).add_layer(...).set_brush().render()
chart                            # display in a cell
chart.brushed                    # last brush selection (dict, syncs from JS)
chart.annotated                  # last annotation event
chart.last_error                 # most recent JS render error, if any
chart.observe(handler, names=["brushed"])  # react to selections
```

## Architecture: one engine, two wrappers

```
mortonanalytics/myIO          (R package)
  └── inst/htmlwidgets/myIO/  ← canonical engine source
        ├── myIOapi.js
        ├── style.css
        └── lib/d3*.js

mortonanalytics/pymyIO        (this repo)
  ├── vendor/myIO/            ← git submodule pinned to a myIO commit
  └── src/pymyio/static/      ← symlinks pointing into vendor/myIO/
```

Wheels built by `python -m build` follow the symlinks and ship real files,
so end-users pip-install a self-contained package. Developers and CI work
against the submodule directly. To pull in upstream chart fixes:

```bash
git submodule update --remote vendor/myIO
git add vendor/myIO && git commit -m "bump myIO engine to <sha>"
```

## Roadmap

| ID | Item | Disposition |
|----|------|-------------|
| PYMYIO-T01 | `loess` / `smooth` transforms | Deferred — needs local-polynomial smoother. Targets 0.2.0 |
| PYMYIO-T02 | `density` transform | Deferred — needs KDE. Targets 0.2.0 |
| PYMYIO-T03 | `survfit` transform | Deferred — needs Kaplan-Meier. Targets 0.3.0 |
| PYMYIO-T04 | `fit_distribution` transform | Deferred — needs MLE for normal/gamma/etc. Targets 0.3.0 |
| PYMYIO-T05 | `pairwise_test` transform | Deferred — needs t/Wilcoxon. Targets 0.3.0 |
| PYMYIO-DOC | Sphinx docs site | Out of scope for 0.1.0 |

## License

MIT. See [LICENSE](LICENSE). The vendored myIO engine is also MIT-licensed
(see `vendor/myIO/LICENSE`).

# pymyIO

Python bindings for [myIO](https://github.com/mortonanalytics/myIO) — the
d3.js-based interactive chart library originally shipped as an R package.

`pymyIO` reuses the exact same JavaScript engine (`myIOapi.js`) the R package
uses, so any chart you can build in R can also be built in Python and renders
identically. The Python side just constructs the JSON config; an
[anywidget](https://anywidget.dev/) wrapper feeds it to the engine inside
Jupyter, JupyterLab, VSCode, Marimo, Colab, etc.

> Status: alpha (0.1.0). Core builder API is stable; not all R chart options
> are surfaced as named Python kwargs yet — anything missing can still be set
> by mutating `chart.config` directly.

## Installation

```bash
pip install pymyio          # once published
# or for local dev:
pip install -e .[dev]
```

## Usage

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

## Supported chart types

`point`, `line`, `bar`, `groupedBar`, `area`, `histogram`, `heatmap`,
`candlestick`, `waterfall`, `sankey`, `boxplot`, `violin`, `ridgeline`,
`donut`, `gauge`, `hexbin`, `treemap`.

## Reading interactions back into Python

```python
chart = MyIO(data=mtcars).add_layer(...).render()
chart                       # display in a cell
chart.brushed               # last brush selection (dict, syncs from JS)
chart.annotated             # last annotation event
chart.last_error            # most recent JS render error, if any
chart.observe(handler, names=["brushed"])  # react to selections
```

## How it relates to the R package

The d3 engine lives in [mortonanalytics/myIO](https://github.com/mortonanalytics/myIO)
under `inst/htmlwidgets/myIO/`. `pymyIO` vendors a copy of `myIOapi.js`,
`d3.min.js`, `d3-hexbin.js`, `d3-sankey.min.js`, and `style.css` into
`src/pymyio/static/`. To pick up upstream chart fixes, re-run
`scripts/sync_engine.sh` (TBD) or copy the files over manually and bump the
package version.

## License

MIT. See `LICENSE`.

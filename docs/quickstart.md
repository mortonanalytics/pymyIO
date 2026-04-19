# Quickstart

## Your first chart

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

## Reading interactions back into Python

```python
chart = (
    MyIO(data=mtcars)
    .add_layer(type="point", label="cars",
               mapping={"x_var": "wt", "y_var": "mpg"})
    .set_brush()
    .render()
)
chart                              # display in a cell
chart.brushed                      # last brush selection (dict, syncs from JS)
chart.annotated                    # last annotation event
chart.last_error                   # most recent JS render error, if any
chart.observe(handler, names=["brushed"])  # react to selections
```

## Static HTML export

```python
from pymyio import to_standalone_html

html = to_standalone_html(MyIO(data=df).add_layer(...))
open("chart.html", "w").write(html)
```

`include_assets="inline"` (default) produces one self-contained HTML string;
`include_assets="bundled"` returns `(html_str, assets_dict)` for publishing
pipelines that prefer sidecar assets.

## Linking charts

```python
from pymyio import MyIO, link_charts

a = MyIO(data=df).add_layer(type="point", label="A",
                            mapping={"x_var": "wt", "y_var": "mpg"}).set_brush()
b = MyIO(data=df).add_layer(type="point", label="B",
                            mapping={"x_var": "hp", "y_var": "mpg"})
link_charts(a, b, on="car_id")
```

Brush selection in `a` highlights matching rows in `b` — no Crosstalk required.

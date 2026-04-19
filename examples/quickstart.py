"""Quickstart: build a scatter + trend overlay and dump the JSON config."""

import json

from pymyio import MyIO

mtcars = [
    {"wt": 2.620, "mpg": 21.0, "cyl": 6},
    {"wt": 2.875, "mpg": 21.0, "cyl": 6},
    {"wt": 2.320, "mpg": 22.8, "cyl": 4},
    {"wt": 3.215, "mpg": 21.4, "cyl": 6},
    {"wt": 3.440, "mpg": 18.7, "cyl": 8},
    {"wt": 3.460, "mpg": 18.1, "cyl": 6},
]

chart = (
    MyIO(data=mtcars)
    .add_layer(type="point", label="points",
               mapping={"x_var": "wt", "y_var": "mpg"}, color="#E69F00")
    .add_layer(type="line", label="trend", transform="lm",
               mapping={"x_var": "wt", "y_var": "mpg"}, color="red")
    .set_axis_format(x_label="Weight", y_label="MPG")
)

print(json.dumps(chart.to_config(), indent=2)[:600], "...")

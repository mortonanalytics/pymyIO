"""Shiny-for-Python integration. Not imported by pymyio/__init__.py.

shinywidgets installs a process-wide Widget._widget_construction_callback
on import that raises RuntimeError("... active Shiny session") for every
subsequent widget construction. Users must opt into this submodule.

Contract: md/design/shiny-jupyter-integration-contract.md §"Critical import rule".
"""

from __future__ import annotations

from importlib import metadata as _md

_MIN_SW = "0.8.0"


def _ver_ge(actual: str, minimum: str) -> bool:
    """Compare dotted version strings as integer tuples (local, no packaging dep)."""

    def tup(s: str) -> tuple:
        return tuple(int(x) for x in s.split(".")[:3] if x.isdigit())

    return tup(actual) >= tup(minimum)


try:
    _sw_ver = _md.version("shinywidgets")
except _md.PackageNotFoundError as e:
    raise ImportError(
        "pymyio.shiny requires the 'shiny' extra. "
        "Install with: pip install 'pymyio[shiny]'"
    ) from e

if not _ver_ge(_sw_ver, _MIN_SW):
    raise ImportError(
        f"pymyio.shiny requires shinywidgets>={_MIN_SW}; found {_sw_ver}. "
        "Upgrade with: pip install -U 'shinywidgets>=0.8.0'"
    )

import shinywidgets as _sw

render_myio = _sw.render_widget
"""Thin alias for :func:`shinywidgets.render_widget`.

Kept as an alias rather than a wrapper so that docstring lookup, IDE
completion, and type-checking all delegate to the original. Mirrors R
myIO's ``renderMyIO`` naming.
"""

output_myio = _sw.output_widget
"""Thin alias for :func:`shinywidgets.output_widget`. Mirrors R myIO's ``myIOOutput``."""


def reactive_brush(widget):
    """Return the widget's current ``brushed`` payload reactively.

    Equivalent to ``shinywidgets.reactive_read(widget, "brushed")``; wraps
    the traitlet name to eliminate the common "did I typo the trait?" bug.
    """

    return _sw.reactive_read(widget, "brushed")


def reactive_annotated(widget):
    """Return the widget's current ``annotated`` payload reactively."""
    return _sw.reactive_read(widget, "annotated")


def reactive_rollover(widget):
    """Return the widget's current ``rollover`` payload reactively."""
    return _sw.reactive_read(widget, "rollover")


def example_app():
    """Return a runnable ``shiny.App`` demonstrating render_myio + reactive_brush.

    Uses a six-row slice of the public-domain ``mtcars`` dataset (R built-in).
    Serves as the canonical parity example alongside the R myIO Shiny demo.
    """

    from shiny import App, ui, render
    import pandas as pd
    from pymyio import MyIO

    mtcars = pd.DataFrame([
        {"wt": 2.620, "mpg": 21.0, "cyl": 6},
        {"wt": 2.875, "mpg": 21.0, "cyl": 6},
        {"wt": 2.320, "mpg": 22.8, "cyl": 4},
        {"wt": 3.215, "mpg": 21.4, "cyl": 6},
        {"wt": 3.440, "mpg": 18.7, "cyl": 8},
        {"wt": 3.460, "mpg": 18.1, "cyl": 4},
    ])

    app_ui = ui.page_fluid(
        ui.h2("pymyIO + Shiny"),
        output_myio("chart"),
        ui.h3("Brushed:"),
        ui.output_text("brushed_out"),
    )

    def server(input, output, session):
        @render_myio
        def chart():
            return (
                MyIO(data=mtcars)
                .add_layer(
                    type="point",
                    label="cars",
                    mapping={"x_var": "wt", "y_var": "mpg"},
                )
                .set_brush()
                .render()
            )

        @render.text
        def brushed_out():
            # shinywidgets 0.6+ attaches .widget onto the @render_widget-
            # decorated function after first render.
            b = reactive_brush(chart.widget)
            return "none" if not b else str(b)

    return App(app_ui, server)

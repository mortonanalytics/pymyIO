"""pymyIO chart gallery — Shiny for Python.

Mirrors the R-myIO Shiny demo at app/app.R, ported to py-shiny + shinywidgets.
Tabs whose transforms are deferred (loess, smooth, survfit, fit_distribution,
pairwise_test) live under "Coming in 0.2+" with their roadmap pointer.
"""

from __future__ import annotations

import math
import random
from datetime import date, timedelta
from pathlib import Path

import pandas as pd
import pymyio
from shiny import App, reactive, render, ui

from pymyio import MyIO, link_charts
from pymyio.shiny import output_myio, reactive_brush, render_myio

# shinywidgets serves the anywidget _esm as an inline blob, so widget.js's
# `import.meta.url` is a `blob:` URL — `new URL(".", import.meta.url)` then
# throws "Invalid URL" and no engine assets load. Mount pymyio's static dir
# as a Shiny route and pin every widget's `_base_url` to that route so the
# in-engine asset loader (line 60 of widget.js) takes the override path.
PYMYIO_STATIC_DIR = Path(pymyio.__file__).parent / "static"
PYMYIO_STATIC_URL = "/pymyio-static/"

_orig_render = MyIO.render

def _render_with_assets(self):
    widget = _orig_render(self)
    widget._base_url = PYMYIO_STATIC_URL
    return widget

MyIO.render = _render_with_assets

# ---- shared datasets -------------------------------------------------------

mtcars = pd.DataFrame([
    {"name": "Mazda RX4",          "wt": 2.620, "mpg": 21.0, "hp": 110, "cyl": 6, "qsec": 16.46},
    {"name": "Mazda RX4 Wag",      "wt": 2.875, "mpg": 21.0, "hp": 110, "cyl": 6, "qsec": 17.02},
    {"name": "Datsun 710",         "wt": 2.320, "mpg": 22.8, "hp":  93, "cyl": 4, "qsec": 18.61},
    {"name": "Hornet 4 Drive",     "wt": 3.215, "mpg": 21.4, "hp": 110, "cyl": 6, "qsec": 19.44},
    {"name": "Hornet Sportabout",  "wt": 3.440, "mpg": 18.7, "hp": 175, "cyl": 8, "qsec": 17.02},
    {"name": "Valiant",            "wt": 3.460, "mpg": 18.1, "hp": 105, "cyl": 6, "qsec": 20.22},
    {"name": "Duster 360",         "wt": 3.570, "mpg": 14.3, "hp": 245, "cyl": 8, "qsec": 15.84},
    {"name": "Merc 240D",          "wt": 3.190, "mpg": 24.4, "hp":  62, "cyl": 4, "qsec": 20.00},
    {"name": "Merc 230",           "wt": 3.150, "mpg": 22.8, "hp":  95, "cyl": 4, "qsec": 22.90},
    {"name": "Merc 280",           "wt": 3.440, "mpg": 19.2, "hp": 123, "cyl": 6, "qsec": 18.30},
    {"name": "Merc 280C",          "wt": 3.440, "mpg": 17.8, "hp": 123, "cyl": 6, "qsec": 18.90},
    {"name": "Merc 450SE",         "wt": 4.070, "mpg": 16.4, "hp": 180, "cyl": 8, "qsec": 17.40},
    {"name": "Merc 450SL",         "wt": 3.730, "mpg": 17.3, "hp": 180, "cyl": 8, "qsec": 17.60},
    {"name": "Merc 450SLC",        "wt": 3.780, "mpg": 15.2, "hp": 180, "cyl": 8, "qsec": 18.00},
    {"name": "Cadillac Fleetwood", "wt": 5.250, "mpg": 10.4, "hp": 205, "cyl": 8, "qsec": 17.98},
    {"name": "Lincoln Continental","wt": 5.424, "mpg": 10.4, "hp": 215, "cyl": 8, "qsec": 17.82},
    {"name": "Chrysler Imperial",  "wt": 5.345, "mpg": 14.7, "hp": 230, "cyl": 8, "qsec": 17.42},
    {"name": "Fiat 128",           "wt": 2.200, "mpg": 32.4, "hp":  66, "cyl": 4, "qsec": 19.47},
    {"name": "Honda Civic",        "wt": 1.615, "mpg": 30.4, "hp":  52, "cyl": 4, "qsec": 18.52},
    {"name": "Toyota Corolla",     "wt": 1.835, "mpg": 33.9, "hp":  65, "cyl": 4, "qsec": 19.90},
    {"name": "Toyota Corona",      "wt": 2.465, "mpg": 21.5, "hp":  97, "cyl": 4, "qsec": 20.01},
    {"name": "Dodge Challenger",   "wt": 3.520, "mpg": 15.5, "hp": 150, "cyl": 8, "qsec": 16.87},
    {"name": "AMC Javelin",        "wt": 3.435, "mpg": 15.2, "hp": 150, "cyl": 8, "qsec": 17.30},
    {"name": "Camaro Z28",         "wt": 3.840, "mpg": 13.3, "hp": 245, "cyl": 8, "qsec": 15.41},
    {"name": "Pontiac Firebird",   "wt": 3.845, "mpg": 19.2, "hp": 175, "cyl": 8, "qsec": 17.05},
    {"name": "Fiat X1-9",          "wt": 1.935, "mpg": 27.3, "hp":  66, "cyl": 4, "qsec": 18.90},
    {"name": "Porsche 914-2",      "wt": 2.140, "mpg": 26.0, "hp":  91, "cyl": 4, "qsec": 16.70},
    {"name": "Lotus Europa",       "wt": 1.513, "mpg": 30.4, "hp": 113, "cyl": 4, "qsec": 16.90},
    {"name": "Ford Pantera L",     "wt": 3.170, "mpg": 15.8, "hp": 264, "cyl": 8, "qsec": 14.50},
    {"name": "Ferrari Dino",       "wt": 2.770, "mpg": 19.7, "hp": 175, "cyl": 6, "qsec": 15.50},
    {"name": "Maserati Bora",      "wt": 3.570, "mpg": 15.0, "hp": 335, "cyl": 8, "qsec": 14.60},
    {"name": "Volvo 142E",         "wt": 2.780, "mpg": 21.4, "hp": 109, "cyl": 4, "qsec": 18.60},
])

iris = pd.DataFrame([
    {"Species": s, "Sepal.Length": sl, "Sepal.Width": sw,
     "Petal.Length": pl, "Petal.Width": pw}
    for s, sl, sw, pl, pw in [
        ("setosa", 5.1, 3.5, 1.4, 0.2), ("setosa", 4.9, 3.0, 1.4, 0.2),
        ("setosa", 4.7, 3.2, 1.3, 0.2), ("setosa", 4.6, 3.1, 1.5, 0.2),
        ("setosa", 5.0, 3.6, 1.4, 0.2), ("setosa", 5.4, 3.9, 1.7, 0.4),
        ("setosa", 4.6, 3.4, 1.4, 0.3), ("setosa", 5.0, 3.4, 1.5, 0.2),
        ("setosa", 4.4, 2.9, 1.4, 0.2), ("setosa", 4.9, 3.1, 1.5, 0.1),
        ("versicolor", 7.0, 3.2, 4.7, 1.4), ("versicolor", 6.4, 3.2, 4.5, 1.5),
        ("versicolor", 6.9, 3.1, 4.9, 1.5), ("versicolor", 5.5, 2.3, 4.0, 1.3),
        ("versicolor", 6.5, 2.8, 4.6, 1.5), ("versicolor", 5.7, 2.8, 4.5, 1.3),
        ("versicolor", 6.3, 3.3, 4.7, 1.6), ("versicolor", 4.9, 2.4, 3.3, 1.0),
        ("versicolor", 6.6, 2.9, 4.6, 1.3), ("versicolor", 5.2, 2.7, 3.9, 1.4),
        ("virginica", 6.3, 3.3, 6.0, 2.5), ("virginica", 5.8, 2.7, 5.1, 1.9),
        ("virginica", 7.1, 3.0, 5.9, 2.1), ("virginica", 6.3, 2.9, 5.6, 1.8),
        ("virginica", 6.5, 3.0, 5.8, 2.2), ("virginica", 7.6, 3.0, 6.6, 2.1),
        ("virginica", 4.9, 2.5, 4.5, 1.7), ("virginica", 7.3, 2.9, 6.3, 1.8),
        ("virginica", 6.7, 2.5, 5.8, 1.8), ("virginica", 7.2, 3.6, 6.1, 2.5),
    ]
])

airquality = pd.DataFrame([
    {"Day": d, "Month": m, "Temp": t}
    for m, day_temps in [
        (5, [67, 72, 74, 62, 56, 66, 65, 59, 61, 69, 74, 69, 66, 68, 58]),
        (6, [76, 80, 79, 84, 85, 83, 78, 78, 81, 80, 80, 81, 82, 83, 82]),
        (7, [86, 88, 86, 83, 81, 81, 81, 82, 86, 85, 87, 89, 90, 84, 88]),
        (8, [86, 86, 86, 84, 84, 83, 82, 82, 79, 76, 74, 75, 80, 84, 86]),
        (9, [76, 73, 76, 78, 78, 77, 72, 75, 79, 81, 82, 79, 78, 76, 74]),
    ]
    for d, t in enumerate(day_temps, start=1)
])

OKABE_ITO = ["#4E79A7", "#F28E2B", "#E15759", "#76B7B2", "#59A14F",
             "#EDC948", "#B07AA1", "#FF9DA7", "#9C755F", "#BAB0AC"]


def _seeded_uniform(seed: int, n: int, low: float, high: float) -> list[float]:
    r = random.Random(seed)
    return [r.uniform(low, high) for _ in range(n)]


def _seeded_normal(seed: int, n: int, mu: float, sd: float) -> list[float]:
    r = random.Random(seed)
    return [r.gauss(mu, sd) for _ in range(n)]


# ---- UI --------------------------------------------------------------------

NAVBAR_CSS = """
.navbar { background-color: #1a1a2e !important; }
.navbar .navbar-brand, .navbar .nav-link { color: rgba(255,255,255,0.85) !important; }
.navbar .nav-link:hover, .navbar .nav-link.active { color: #fff !important; }
.feature-card {
  border: 1px solid #dee2e6; border-radius: 8px; padding: 1.5rem;
  text-align: center; margin-bottom: 1rem; height: 100%;
}
.feature-card h4 { color: #4A5ACB; margin-top: 0.75rem; }
.chart-container { padding: 1rem; }
.lead { color: #6c757d; }
.deferred-card {
  border-left: 4px solid #F28E2B; background: #fff8f0;
  padding: 1rem; border-radius: 4px; margin-bottom: 1rem;
}
"""


def _home_panel() -> ui.Tag:
    return ui.nav_panel(
        "Home",
        ui.div(
            {"class": "container", "style": "max-width: 900px; margin: 0 auto; padding-top: 2rem;"},
            ui.div(
                {"style": "text-align: center; margin-bottom: 2rem;"},
                ui.h1("pymyIO Chart Gallery", style="margin-top: 1rem; font-weight: 700;"),
                ui.p(
                    {"class": "lead"},
                    "Interactive D3.js visualizations from Python. ",
                    "Same engine as ", ui.tags.a("R-myIO", href="https://mortonanalytics.github.io/myIO/", target="_blank"), ".",
                ),
            ),
            ui.layout_columns(
                ui.div(
                    {"class": "feature-card"},
                    ui.h4("34 Chart Types"),
                    ui.p("Scatter, line, bar, area, histogram, donut, gauge, treemap, hexbin, "
                         "heatmap, candlestick, waterfall, sankey, boxplot, violin, ridgeline, "
                         "regression, Q-Q, lollipop, dumbbell, waffle, beeswarm, bump, radar, "
                         "funnel, calendar heatmap, sparklines, small multiples."),
                ),
                ui.div(
                    {"class": "feature-card"},
                    ui.h4("Statistical Transforms"),
                    ui.p("Built-in CI bands, mean ± CI error bars, OLS / polynomial regression, "
                         "residuals, Q-Q quantiles. Pure Python — no scipy required."),
                ),
                ui.div(
                    {"class": "feature-card"},
                    ui.h4("Bidirectional I/O"),
                    ui.p("Brush to select, click to annotate, link charts with link_charts(), "
                         "and add parameter sliders. Events flow back to Python via traitlets."),
                ),
                ui.div(
                    {"class": "feature-card"},
                    ui.h4("Engine parity with R"),
                    ui.p("Same vendored myIOapi.js as R-myIO. Same JSON config. Same renders. "
                         "One source of truth, two language wrappers."),
                ),
                col_widths=[3, 3, 3, 3],
            ),
            ui.div(
                {"style": "text-align: center; margin: 2rem 0;"},
                ui.p("Use the tabs above to explore each chart type."),
                ui.tags.a(
                    "Documentation", href="https://mortonanalytics.github.io/pymyIO/",
                    class_="btn btn-outline-primary", target="_blank",
                ),
                " ",
                ui.tags.a(
                    "Source", href="https://github.com/mortonanalytics/pymyIO",
                    class_="btn btn-outline-secondary", target="_blank",
                ),
            ),
        ),
        icon=None,
    )


app_ui = ui.page_navbar(
    _home_panel(),
    ui.nav_menu(
        "Basic",
        ui.nav_panel("Bar", ui.div({"class": "chart-container"}, output_myio("bar_plot"))),
        ui.nav_panel("Grouped Bar",
            ui.layout_sidebar(
                ui.sidebar(
                    ui.input_slider("gb_noise", "Noise", min=0, max=50, value=0, step=5),
                    ui.input_checkbox_group("gb_months", "Months",
                        choices=["5", "6", "7", "8", "9"],
                        selected=["5", "6", "7", "8", "9"], inline=True),
                ),
                output_myio("grouped_bar"),
            ),
        ),
        ui.nav_panel("Horizontal Bar", ui.div({"class": "chart-container"}, output_myio("hbar_plot"))),
        ui.nav_panel("Line",
            ui.layout_sidebar(
                ui.sidebar(ui.input_slider("line_noise", "Noise", min=0, max=50, value=0, step=5)),
                output_myio("line_plot"),
            ),
        ),
        ui.nav_panel("Area", ui.div({"class": "chart-container"}, output_myio("area_plot"))),
    ),
    ui.nav_menu(
        "Statistical",
        ui.nav_panel("Scatter + Trend",
            ui.div({"class": "chart-container"}, output_myio("point_plot"))),
        ui.nav_panel("Regression + CI",
            ui.layout_sidebar(
                ui.sidebar(
                    ui.input_select("reg_method", "Method",
                        choices={"lm": "Linear", "polynomial": "Polynomial"}),
                    ui.input_slider("reg_level", "Confidence Level",
                        min=0.80, max=0.99, value=0.95, step=0.01),
                ),
                output_myio("regression_plot"),
            ),
        ),
        ui.nav_panel("Residuals", ui.div({"class": "chart-container"}, output_myio("residual_plot"))),
        ui.nav_panel("Histogram",
            ui.layout_sidebar(
                ui.sidebar(ui.input_slider("hist_n", "Sample size",
                    min=50, max=500, value=200, step=50)),
                output_myio("hist_plot"),
            ),
        ),
        ui.nav_panel("Hexbin Density",
            ui.div({"class": "chart-container"}, output_myio("hexbin_plot"))),
    ),
    ui.nav_menu(
        "Specialized",
        ui.nav_panel("Donut",
            ui.layout_sidebar(
                ui.sidebar(ui.input_slider("donut_noise", "Noise",
                    min=0, max=30, value=0, step=5)),
                output_myio("donut_plot"),
            ),
        ),
        ui.nav_panel("Gauge",
            ui.layout_sidebar(
                ui.sidebar(ui.input_slider("gauge_val", "Value",
                    min=0, max=1, value=0.65, step=0.05)),
                output_myio("gauge_plot"),
            ),
        ),
        ui.nav_panel("Treemap", ui.div({"class": "chart-container"}, output_myio("treemap_plot"))),
    ),
    ui.nav_menu(
        "Financial",
        ui.nav_panel("Candlestick", ui.div({"class": "chart-container"}, output_myio("candlestick_plot"))),
        ui.nav_panel("Waterfall", ui.div({"class": "chart-container"}, output_myio("waterfall_plot"))),
    ),
    ui.nav_menu(
        "Relational",
        ui.nav_panel("Heatmap", ui.div({"class": "chart-container"}, output_myio("heatmap_plot"))),
        ui.nav_panel("Sankey", ui.div({"class": "chart-container"}, output_myio("sankey_plot"))),
    ),
    ui.nav_menu(
        "Interactions",
        ui.nav_panel("Brush Selection",
            ui.layout_columns(
                output_myio("brush_plot"),
                ui.div(
                    ui.h4("Selected Points"),
                    ui.output_text_verbatim("brush_info"),
                    ui.input_select("brush_dir", "Brush Direction",
                        choices={"xy": "Both axes", "x": "X only", "y": "Y only"}),
                ),
                col_widths=[8, 4],
            ),
        ),
        ui.nav_panel("Click-to-Annotate",
            ui.layout_columns(
                output_myio("annotate_plot"),
                ui.div(
                    ui.h4("Annotations"),
                    ui.output_table("annotation_table"),
                    ui.p({"class": "text-muted", "style": "font-size: 12px;"},
                         "Click a point to add a label."),
                ),
                col_widths=[8, 4],
            ),
        ),
        ui.nav_panel("Linked Brushing",
            ui.p({"class": "text-muted", "style": "padding: 0 1rem;"},
                 "Brush points in the left chart to highlight matching rows in the right."),
            ui.layout_columns(
                output_myio("linked_a"),
                output_myio("linked_b"),
                col_widths=[6, 6],
            ),
        ),
        ui.nav_panel("Parameter Slider",
            ui.layout_sidebar(
                ui.sidebar(ui.input_slider("slider_ci", "Confidence Level",
                    min=0.80, max=0.99, value=0.95, step=0.01)),
                output_myio("slider_plot"),
            ),
        ),
    ),
    ui.nav_menu(
        "More Charts",
        ui.nav_panel("Lollipop", ui.div({"class": "chart-container"}, output_myio("lollipop_plot"))),
        ui.nav_panel("Dumbbell", ui.div({"class": "chart-container"}, output_myio("dumbbell_plot"))),
        ui.nav_panel("Waffle", ui.div({"class": "chart-container"}, output_myio("waffle_plot"))),
        ui.nav_panel("Beeswarm", ui.div({"class": "chart-container"}, output_myio("beeswarm_plot"))),
        ui.nav_panel("Bump", ui.div({"class": "chart-container"}, output_myio("bump_plot"))),
        ui.nav_panel("Radar", ui.div({"class": "chart-container"}, output_myio("radar_plot"))),
        ui.nav_panel("Funnel", ui.div({"class": "chart-container"}, output_myio("funnel_plot"))),
        ui.nav_panel("Calendar Heatmap",
            ui.div({"class": "chart-container"}, output_myio("calendar_plot"))),
    ),
    ui.nav_menu(
        "Advanced",
        ui.nav_panel("Sparklines",
            ui.div(
                {"class": "chart-container"},
                ui.h4("Inline Sparklines"),
                ui.layout_columns(
                    ui.div(ui.h5("Revenue Trend"), output_myio("sparkline1")),
                    ui.div(ui.h5("User Growth"),   output_myio("sparkline2")),
                    ui.div(ui.h5("Error Rate"),    output_myio("sparkline3")),
                    col_widths=[4, 4, 4],
                ),
            ),
        ),
        ui.nav_panel("Small Multiples",
            ui.div({"class": "chart-container"}, output_myio("facet_plot"))),
    ),
    ui.nav_panel("Theme Demo",
        ui.layout_sidebar(
            ui.sidebar(
                ui.input_select("theme_preset", "Theme Preset",
                    choices=["light", "dark", "midnight", "ocean", "forest",
                             "sunset", "monochrome", "neon", "corporate", "academic"]),
            ),
            output_myio("theme_plot"),
        ),
    ),
    ui.nav_panel("Export Demo",
        ui.layout_sidebar(
            ui.sidebar(
                ui.h5("Export Options"),
                ui.input_checkbox("exp_png", "PNG", True),
                ui.input_checkbox("exp_svg", "SVG", True),
                ui.input_checkbox("exp_pdf", "PDF", True),
                ui.input_checkbox("exp_csv", "CSV", True),
                ui.input_checkbox("exp_clipboard", "Clipboard", True),
                ui.hr(),
                ui.input_select("exp_theme", "Theme",
                    choices=["light", "dark", "midnight", "ocean"], selected="light"),
            ),
            output_myio("export_plot"),
        ),
    ),
    ui.nav_panel("Known gaps",
        ui.div(
            {"class": "container", "style": "max-width: 800px; padding-top: 2rem;"},
            ui.h2("Charts not yet rendering on 0.1.x"),
            ui.p("Two categories: (a) statistical transforms not yet ported, "
                 "(b) composite chart types whose Python expansion sends a layer "
                 "type the d3 engine has no renderer for. Both unblock once "
                 "pymyio's composite-expansion + transform layer reaches R parity."),
            ui.h3("Composite expansions (engine has no renderer for these layer types)"),
            ui.div({"class": "deferred-card"},
                ui.tags.b("Boxplot, Violin, Ridgeline"),
                ui.tags.span(" — pymyio composite-expansion bug"),
                ui.p("R-myIO expands these into primitive bar/line/point layers "
                     "via composite_boxplot()/composite_violin()/composite_ridgeline() "
                     "before sending to the engine. pymyio's _expand_composite() "
                     "still emits a layer with type='boxplot'/'violin'/'ridgeline', "
                     "and the engine throws \"Unknown renderer type.\" Fix is to "
                     "port the R composite_*() functions to Python.")),
            ui.div({"class": "deferred-card"},
                ui.tags.b("Q-Q Plot"),
                ui.tags.span(" — pymyio transform/mapping mismatch"),
                ui.p("The qq transform produces records with literal x_var/y_var "
                     "keys, but the layer's mapping doesn't reference them, so "
                     "the point renderer can't find the columns. Same root cause "
                     "as the rangeBar mean_ci bug.")),
            ui.h3("Deferred statistical transforms"),
            ui.div({"class": "deferred-card"},
                ui.tags.b("LOESS / smooth / density"),
                ui.tags.span(" — PYMYIO-T01, T02, target 0.2.0"),
                ui.p("Local-polynomial smoother + KDE. Unblocks LOESS overlays, "
                     "moving-average lines, and density-based ridgelines.")),
            ui.div({"class": "deferred-card"},
                ui.tags.b("Survival (Kaplan-Meier)"),
                ui.tags.span(" — PYMYIO-T03, target 0.3.0")),
            ui.div({"class": "deferred-card"},
                ui.tags.b("Distribution fit"),
                ui.tags.span(" — PYMYIO-T04, target 0.3.0"),
                ui.p("MLE for normal / log-normal / exponential.")),
            ui.div({"class": "deferred-card"},
                ui.tags.b("Pairwise tests (comparison brackets)"),
                ui.tags.span(" — PYMYIO-T05, target 0.3.0")),
            ui.div({"class": "deferred-card"},
                ui.tags.b("Mean ± CI on rangeBar"),
                ui.tags.span(" — pymyio required-mapping bug"),
                ui.p("rangeBar requires low_y/high_y at validation time, but the "
                     "R-parity {x_var, y_var} call relies on the mean_ci transform "
                     "to synthesize the band. Required-mapping check needs to be "
                     "transform-aware.")),
            ui.tags.a("Full roadmap →",
                href="https://mortonanalytics.github.io/pymyIO/roadmap/",
                target="_blank"),
        ),
    ),
    title=ui.span("pymyIO"),
    id="nav",
    header=ui.tags.head(ui.tags.style(NAVBAR_CSS)),
)


# ---- server ----------------------------------------------------------------

def server(input, output, session):

    # -- Basic --
    @render_myio
    def bar_plot():
        df = pd.DataFrame({
            "language": ["Python", "JavaScript", "Java", "R", "Go"],
            "postings": [87, 63, 55, 42, 29],
        })
        return (
            MyIO()
            .add_layer(type="bar", color="#59A14F", label="Job Postings",
                       data=df, mapping={"x_var": "language", "y_var": "postings"})
            .define_categorical_axis(x_axis=True)
            .set_axis_format(y_format=".0f", x_label="Language", y_label="Job Postings (K)")
            .render()
        )

    @render_myio
    def grouped_bar():
        months = [int(m) for m in input.gb_months()] or [5, 6, 7, 8, 9]
        df = airquality[airquality["Month"].isin(months)].copy()
        df["Month"] = df["Month"].astype(str)
        noise = input.gb_noise()
        if noise > 0:
            jitter = _seeded_uniform(42, len(df), -noise, noise)
            df["Temp"] = [t + j for t, j in zip(df["Temp"], jitter)]
        return (
            MyIO()
            .add_layer(type="groupedBar", color=OKABE_ITO[:5],
                       label="Temperature by Month", data=df,
                       mapping={"x_var": "Day", "y_var": "Temp", "group": "Month"})
            .set_axis_limits(ylim=[0, 100])
            .set_axis_format(x_format=".0f", y_format=".0f",
                             x_label="Day", y_label="Temperature (F)")
            .render()
        )

    @render_myio
    def hbar_plot():
        df = pd.DataFrame({
            "region": ["North", "South", "East", "West", "Central"],
            "sales":  [320, 475, 290, 510, 380],
        })
        return (
            MyIO()
            .add_layer(type="bar", color="#F28E2B", label="Sales", data=df,
                       mapping={"x_var": "region", "y_var": "sales"})
            .define_categorical_axis(x_axis=False, y_axis=True)
            .flip_axis()
            .set_axis_format(x_format=".0f", x_label="Sales ($K)", y_label="Region")
            .render()
        )

    @render_myio
    def line_plot():
        df = airquality.copy()
        df["Month"] = df["Month"].astype(str)
        noise = input.line_noise()
        if noise > 0:
            jitter = _seeded_uniform(7, len(df), -noise, noise)
            df["Temp"] = [t + j for t, j in zip(df["Temp"], jitter)]
        return (
            MyIO()
            .add_layer(type="line", color=OKABE_ITO[:5], label="Temp", data=df,
                       mapping={"x_var": "Day", "y_var": "Temp", "group": "Month"})
            .set_axis_format(x_format=".0f", y_format=".0f",
                             x_label="Day", y_label="Temperature (F)")
            .render()
        )

    @render_myio
    def area_plot():
        running = 0.0
        revenue = []
        for v in _seeded_uniform(1, 12, 10, 30):
            running += v
            revenue.append(running)
        df = pd.DataFrame({"month": list(range(1, 13)), "revenue": revenue})
        return (
            MyIO()
            .add_layer(type="area", color="#4E79A7", label="Cumulative Revenue",
                       data=df, mapping={"x_var": "month", "y_var": "revenue"})
            .set_axis_format(x_format=".0f", y_format="$,.0f",
                             x_label="Month", y_label="Revenue")
            .render()
        )

    # -- Statistical --
    @render_myio
    def point_plot():
        return (
            MyIO()
            .add_layer(type="point", color="#4E79A7", label="Cars", data=mtcars,
                       mapping={"x_var": "wt", "y_var": "mpg"})
            .add_layer(type="line", transform="lm", color="#E15759", label="Linear Fit",
                       data=mtcars, mapping={"x_var": "wt", "y_var": "mpg"})
            .set_axis_format(x_label="Weight (1000 lbs)", y_label="Miles per Gallon")
            .render()
        )

    @render_myio
    def regression_plot():
        xs = list(range(1, 41))
        noise = _seeded_normal(42, 40, 0, 3)
        df = pd.DataFrame({
            "day": xs,
            "yield": [0.8 * x + math.sin(x) * 5 + n for x, n in zip(xs, noise)],
        })
        return (
            MyIO(data=df)
            .add_layer(type="regression", label="Yield Model",
                       mapping={"x_var": "day", "y_var": "yield"},
                       options={"method": input.reg_method(),
                                "showCI": True,
                                "level": input.reg_level(),
                                "showStats": True,
                                "degree": 3})
            .set_axis_format(x_label="Day of Experiment", y_label="Yield (mg)")
            .render()
        )

    @render_myio
    def residual_plot():
        xs = list(range(1, 41))
        noise = _seeded_normal(42, 40, 0, 3)
        df = pd.DataFrame({"x": xs, "y": [0.05 * x ** 2 + n for x, n in zip(xs, noise)]})
        return (
            MyIO(data=df)
            .add_layer(type="point", color="#4E79A7",
                       label="Residuals (lm on quadratic data)",
                       transform="residuals", mapping={"x_var": "x", "y_var": "y"})
            .set_reference_lines(y=[0])
            .set_axis_format(x_label="Fitted Values", y_label="Residuals")
            .render()
        )

    @render_myio
    def hist_plot():
        n = input.hist_n()
        half = n // 2
        vals = (_seeded_normal(42, half, 35, 8)
                + _seeded_normal(43, n - half, 65, 10))
        df = pd.DataFrame({"value": vals})
        return (
            MyIO()
            .add_layer(type="histogram", color="#76B7B2", label="Distribution",
                       data=df, mapping={"value": "value"})
            .set_axis_format(x_format=".0f", y_format=".0f",
                             x_label="Response Time (ms)", y_label="Frequency")
            .render()
        )

    @render_myio
    def hexbin_plot():
        xs = _seeded_normal(42, 200, 3, 1) + _seeded_normal(43, 200, 7, 1.5)
        ys = _seeded_normal(44, 200, 5, 1) + _seeded_normal(45, 200, 8, 1.2)
        df = pd.DataFrame({"x": xs, "y": ys})
        return (
            MyIO()
            .add_layer(type="hexbin", color="#4E79A7", label="Density", data=df,
                       mapping={"x_var": "x", "y_var": "y", "radius": 20})
            .set_axis_format(x_label="Height (in)", y_label="Weight (lbs)")
            .render()
        )

    # -- Specialized --
    @render_myio
    def donut_plot():
        noise = input.donut_noise()
        jitter = _seeded_uniform(8, 4, -noise, noise)
        df = pd.DataFrame({
            "segment": ["Desktop", "Mobile", "Tablet", "Other"],
            "traffic": [max(1, v + j) for v, j in zip([45, 35, 15, 5], jitter)],
        })
        return (
            MyIO()
            .add_layer(type="donut", color=OKABE_ITO[:4], label="Traffic", data=df,
                       mapping={"x_var": "segment", "y_var": "traffic"})
            .render()
        )

    @render_myio
    def gauge_plot():
        return (
            MyIO()
            .add_layer(type="gauge", color="#E15759", label="Completion",
                       data=pd.DataFrame({"value": [input.gauge_val()]}),
                       mapping={"value": "value"})
            .suppress_axis(x_axis=True, y_axis=True)
            .suppress_legend()
            .render()
        )

    @render_myio
    def treemap_plot():
        df = pd.DataFrame({
            "department": ["Engineering"] * 3 + ["Sales"] * 2 + ["Marketing"] * 3,
            "team": ["Frontend", "Backend", "Infra", "Enterprise", "SMB",
                     "Content", "Paid", "Brand"],
            "headcount": [25, 30, 15, 20, 18, 12, 10, 8],
        })
        return (
            MyIO()
            .add_layer(type="treemap", color=OKABE_ITO[:3],
                       label="Headcount by Department", data=df,
                       mapping={"level_1": "department", "level_2": "team",
                                "y_var": "headcount", "x_var": "team"})
            .render()
        )

    # -- Financial --
    @render_myio
    def candlestick_plot():
        n = 30
        prices = [100.0]
        for delta in _seeded_normal(42, n - 1, 0.3, 2):
            prices.append(prices[-1] + delta)
        opens = [p + j for p, j in zip(prices, _seeded_uniform(2, n, -1, 1))]
        closes = [p + j for p, j in zip(prices, _seeded_uniform(3, n, -1, 1))]
        highs = [max(o, c) + abs(j) for o, c, j in zip(opens, closes, _seeded_normal(4, n, 0, 1.5))]
        lows = [min(o, c) - abs(j) for o, c, j in zip(opens, closes, _seeded_normal(5, n, 0, 1.5))]
        df = pd.DataFrame({"day": list(range(1, n + 1)),
                           "open": opens, "close": closes, "high": highs, "low": lows})
        return (
            MyIO()
            .add_layer(type="candlestick", color="#59A14F", label="ACME Corp", data=df,
                       mapping={"x_var": "day", "open": "open", "high": "high",
                                "low": "low", "close": "close"})
            .set_axis_format(x_format=".0f", y_format="$,.0f",
                             x_label="Trading Day", y_label="Price")
            .render()
        )

    @render_myio
    def waterfall_plot():
        df = pd.DataFrame({
            "step":  ["Start", "Add Sales", "Discount", "Tax", "End"],
            "value": [100, 35, -15, -10, None],
            "total": [False, False, False, False, True],
        })
        return (
            MyIO()
            .add_layer(type="waterfall", color="#F28E2B", label="Revenue Bridge",
                       data=df, mapping={"x_var": "step", "y_var": "value",
                                          "total": "total"})
            .define_categorical_axis(x_axis=True)
            .set_axis_format(y_format="$,.0f", x_label="Step", y_label="Running Total")
            .render()
        )

    # -- Relational --
    @render_myio
    def heatmap_plot():
        rows = []
        values = [12, 15, 22, 30, 5, 8, 14, 25, 2, 3, 6, 18]
        for tier, qs in zip(["Basic", "Pro", "Enterprise"],
                             [values[0:4], values[4:8], values[8:12]]):
            for q, v in zip(["Q1", "Q2", "Q3", "Q4"], qs):
                rows.append({"x": q, "y": tier, "value": v})
        df = pd.DataFrame(rows)
        return (
            MyIO()
            .add_layer(type="heatmap", color="#4E79A7", label="Signups", data=df,
                       mapping={"x_var": "x", "y_var": "y", "value": "value"})
            .define_categorical_axis(x_axis=True, y_axis=True)
            .set_axis_format(x_label="Quarter", y_label="Tier")
            .render()
        )

    @render_myio
    def sankey_plot():
        df = pd.DataFrame({
            "source": ["Organic", "Organic", "Paid", "Paid", "Referral",
                       "Trial", "Trial", "Trial", "Demo", "Demo",
                       "Converted", "Converted"],
            "target": ["Trial", "Bounce", "Trial", "Demo", "Trial",
                       "Converted", "Churned", "Demo", "Converted", "Lost",
                       "Annual", "Monthly"],
            "value":  [40, 15, 25, 10, 20, 30, 25, 30, 25, 15, 35, 20],
        })
        return (
            MyIO()
            .add_layer(type="sankey", color=OKABE_ITO + OKABE_ITO[:2],
                       label="Acquisition Funnel", data=df,
                       mapping={"source": "source", "target": "target", "value": "value"})
            .render()
        )

    # -- Interactions --
    @render_myio
    def brush_plot():
        return (
            MyIO()
            .add_layer(type="point", color="#4E79A7", label="Cars", data=mtcars,
                       mapping={"x_var": "wt", "y_var": "mpg"})
            .set_brush(direction=input.brush_dir())
            .set_axis_format(x_label="Weight (1000 lbs)", y_label="Miles per Gallon")
            .set_margin(top=20, bottom=70, left=60, right=10)
            .render()
        )

    @render.text
    def brush_info():
        b = reactive_brush(brush_plot.widget)
        if not b:
            return "Drag on the chart to select points."
        keys = b.get("keys") or []
        extent = b.get("extent") or {}
        lines = [f"{len(keys)} of {len(mtcars)} points selected", ""]
        if "x" in extent:
            lines.append(f"X range: {extent['x'][0]:.2f} – {extent['x'][1]:.2f}")
        if "y" in extent:
            lines.append(f"Y range: {extent['y'][0]:.2f} – {extent['y'][1]:.2f}")
        return "\n".join(lines)

    @render_myio
    def annotate_plot():
        return (
            MyIO()
            .add_layer(type="point", color="#4E79A7", label="Iris", data=iris,
                       mapping={"x_var": "Sepal.Length", "y_var": "Petal.Length"})
            .set_annotation(
                labels=["outlier", "cluster edge", "typical"],
                colors={"outlier": "#E63946", "cluster edge": "#F4A261",
                        "typical": "#2A9D8F"},
            )
            .set_axis_format(x_label="Sepal Length", y_label="Petal Length")
            .render()
        )

    @render.table
    def annotation_table():
        from pymyio.shiny import reactive_annotated
        a = reactive_annotated(annotate_plot.widget)
        if not a:
            return pd.DataFrame({"Label": [], "X": [], "Y": []})
        anns = a.get("annotations") or []
        if not anns:
            return pd.DataFrame({"Label": [], "X": [], "Y": []})
        return pd.DataFrame({
            "Label": [r.get("label") for r in anns],
            "X": [round(float(r.get("x", 0)), 2) for r in anns],
            "Y": [round(float(r.get("y", 0)), 2) for r in anns],
        })

    @render_myio
    def linked_a():
        df = mtcars.copy()
        df["car_id"] = df["name"]
        a = (MyIO()
             .add_layer(type="point", color="#4E79A7", label="wt vs mpg", data=df,
                        mapping={"x_var": "wt", "y_var": "mpg"})
             .set_brush()
             .set_axis_format(x_label="Weight", y_label="MPG"))
        b = (MyIO()
             .add_layer(type="point", color="#E15759", label="hp vs mpg", data=df,
                        mapping={"x_var": "hp", "y_var": "mpg"})
             .set_axis_format(x_label="Horsepower", y_label="MPG"))
        link_charts(a, b, on="car_id", group="gallery_link")
        return a.render()

    @render_myio
    def linked_b():
        df = mtcars.copy()
        df["car_id"] = df["name"]
        b = (MyIO()
             .add_layer(type="point", color="#E15759", label="hp vs mpg", data=df,
                        mapping={"x_var": "hp", "y_var": "mpg"})
             .set_axis_format(x_label="Horsepower", y_label="MPG"))
        # Re-link so this side has matching group; brushing in linked_a propagates.
        a = (MyIO()
             .add_layer(type="point", color="#4E79A7", label="wt vs mpg", data=df,
                        mapping={"x_var": "wt", "y_var": "mpg"})
             .set_brush())
        link_charts(a, b, on="car_id", group="gallery_link")
        return b.render()

    @render_myio
    def slider_plot():
        xs = list(range(1, 41))
        noise = _seeded_normal(42, 40, 0, 3)
        df = pd.DataFrame({
            "day": xs,
            "yield": [0.8 * x + math.sin(x) * 5 + n for x, n in zip(xs, noise)],
        })
        return (
            MyIO(data=df)
            .add_layer(type="regression", label="Yield Model",
                       mapping={"x_var": "day", "y_var": "yield"},
                       options={"method": "lm", "showCI": True,
                                "level": input.slider_ci(), "showStats": True})
            .set_axis_format(x_label="Day of Experiment", y_label="Yield (mg)")
            .render()
        )

    # -- More Charts --
    @render_myio
    def lollipop_plot():
        agg = mtcars.groupby("cyl", as_index=False)["mpg"].mean()
        agg["cyl"] = agg["cyl"].astype(str)
        return (
            MyIO()
            .add_layer(type="lollipop", label="Avg MPG", color="#4E79A7", data=agg,
                       mapping={"x_var": "cyl", "y_var": "mpg"})
            .define_categorical_axis(x_axis=True)
            .set_axis_format(y_format=".1f", x_label="Cylinders", y_label="Average MPG")
            .render()
        )

    @render_myio
    def dumbbell_plot():
        df = pd.DataFrame({
            "dept": ["Engineering", "Marketing", "Sales", "Support", "Design"],
            "q1":   [3.2, 3.5, 3.8, 3.1, 4.0],
            "q4":   [4.5, 4.2, 3.6, 4.1, 4.3],
        })
        return (
            MyIO()
            .add_layer(type="dumbbell", label="Satisfaction", color="#E15759", data=df,
                       mapping={"x_var": "dept", "low_y": "q1", "high_y": "q4"})
            .define_categorical_axis(x_axis=True)
            .set_axis_format(y_format=".1f", x_label="Department", y_label="Satisfaction Score")
            .render()
        )

    @render_myio
    def waffle_plot():
        df = pd.DataFrame({
            "cat": ["Renewable", "Natural Gas", "Coal", "Nuclear", "Other"],
            "val": [22, 38, 20, 12, 8],
        })
        return (
            MyIO()
            .add_layer(type="waffle", label="Energy Mix", data=df,
                       mapping={"category": "cat", "value": "val"})
            .render()
        )

    @render_myio
    def beeswarm_plot():
        return (
            MyIO()
            .add_layer(type="beeswarm", label="Iris", color="#76B7B2", data=iris,
                       mapping={"x_var": "Sepal.Length", "y_var": "Sepal.Width"},
                       options={"radius": 3})
            .render()
        )

    @render_myio
    def bump_plot():
        df = pd.DataFrame({
            "quarter": ["Q1"] * 4 + ["Q2"] * 4 + ["Q3"] * 4 + ["Q4"] * 4,
            "rank":    [1, 2, 3, 4, 2, 1, 4, 3, 1, 3, 2, 4, 3, 1, 4, 2],
            "team":    ["Alpha", "Beta", "Gamma", "Delta"] * 4,
        })
        return (
            MyIO()
            .add_layer(type="bump", label="Rankings", data=df,
                       mapping={"x_var": "quarter", "y_var": "rank", "group": "team"})
            .define_categorical_axis(x_axis=True)
            .set_axis_format(x_label="Quarter", y_label="Rank")
            .render()
        )

    @render_myio
    def radar_plot():
        df = pd.DataFrame({
            "axis":  ["Speed", "Power", "Range", "Armor", "Stealth"],
            "value": [85, 70, 90, 45, 75],
        })
        return (
            MyIO()
            .add_layer(type="radar", label="Fighter Stats", color="#4E79A7", data=df,
                       mapping={"axis": "axis", "value": "value"})
            .render()
        )

    @render_myio
    def funnel_plot():
        df = pd.DataFrame({
            "stage": ["Visitors", "Leads", "Qualified", "Proposals", "Closed"],
            "value": [10000, 5200, 2800, 1100, 450],
        })
        return (
            MyIO()
            .add_layer(type="funnel", label="Sales Pipeline", data=df,
                       mapping={"stage": "stage", "value": "value"})
            .render()
        )

    @render_myio
    def calendar_plot():
        start = date(2026, 1, 1)
        days = [start + timedelta(days=i) for i in range(365)]
        r = random.Random(1)
        df = pd.DataFrame({
            "day": [d.isoformat() for d in days],
            "activity": [r.randint(0, 12) for _ in days],
        })
        return (
            MyIO()
            .add_layer(type="calendarHeatmap", color="#4E79A7", label="Daily activity",
                       data=df, mapping={"date": "day", "value": "activity"})
            .render()
        )

    # -- Advanced --
    @render_myio
    def sparkline1():
        ys = []
        running = 0.0
        for v in _seeded_normal(1, 20, 0.5, 1):
            running += v
            ys.append(running)
        df = pd.DataFrame({"x": list(range(1, 21)), "y": ys})
        return (
            MyIO(data=df, sparkline=True)
            .add_layer(type="line", label="Revenue", color="#59A14F",
                       mapping={"x_var": "x", "y_var": "y"})
            .render()
        )

    @render_myio
    def sparkline2():
        ys = []
        running = 0.0
        for v in _seeded_normal(2, 20, 0.3, 0.8):
            running += v
            ys.append(running)
        df = pd.DataFrame({"x": list(range(1, 21)), "y": ys})
        return (
            MyIO(data=df, sparkline=True)
            .add_layer(type="line", label="Users", color="#4E79A7",
                       mapping={"x_var": "x", "y_var": "y"})
            .render()
        )

    @render_myio
    def sparkline3():
        ys = []
        running = 5.0
        for v in _seeded_normal(3, 20, -0.1, 0.5):
            running = max(0.0, running + v)
            ys.append(running)
        df = pd.DataFrame({"x": list(range(1, 21)), "y": ys})
        return (
            MyIO(data=df, sparkline=True)
            .add_layer(type="line", label="Errors", color="#E15759",
                       mapping={"x_var": "x", "y_var": "y"})
            .render()
        )

    @render_myio
    def facet_plot():
        return (
            MyIO(iris)
            .add_layer(type="point", label="Iris",
                       mapping={"x_var": "Sepal.Length", "y_var": "Sepal.Width"})
            .set_facet("Species", ncol=3)
            .set_axis_format(x_label="Sepal Length", y_label="Sepal Width")
            .render()
        )

    @render_myio
    def theme_plot():
        df = mtcars.copy()
        df["cyl"] = df["cyl"].astype(str)
        return (
            MyIO()
            .add_layer(type="point", color=["#FF6B6B", "#4ECDC4", "#45B7D1"],
                       label="MPG by HP", data=df,
                       mapping={"x_var": "hp", "y_var": "mpg", "group": "cyl"})
            .set_theme(preset=input.theme_preset())
            .set_axis_format(x_label="Horsepower", y_label="MPG")
            .set_reference_lines(y=[df["mpg"].mean()])
            .render()
        )

    @render_myio
    def export_plot():
        df = mtcars.copy()
        df["cyl"] = df["cyl"].astype(str)
        return (
            MyIO()
            .add_layer(type="point", color=OKABE_ITO[:3], label="MPG by Weight",
                       data=df, mapping={"x_var": "wt", "y_var": "mpg", "group": "cyl"})
            .add_layer(type="line", transform="lm", color="#999999", label="Trend",
                       data=df, mapping={"x_var": "wt", "y_var": "mpg"})
            .set_theme(preset=input.exp_theme())
            .set_axis_format(x_format=".1f", y_format=".0f",
                             x_label="Weight (1000 lbs)", y_label="Miles per Gallon")
            .set_export_options(
                png=input.exp_png(), svg=input.exp_svg(), pdf=input.exp_pdf(),
                csv=input.exp_csv(), clipboard=input.exp_clipboard(),
                title="MPG by Weight — pymyIO Export Demo",
            )
            .render()
        )


app = App(app_ui, server, static_assets={PYMYIO_STATIC_URL: PYMYIO_STATIC_DIR})

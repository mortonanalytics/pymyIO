# pymyIO

Python bindings for [myIO](https://github.com/mortonanalytics/myIO) — the
d3.js-based interactive chart library originally shipped as an R package.

`pymyIO` is feature-equivalent to the R package: every R export is reachable
from Python, every chart type renders identically, and the JSON config the
Python builder produces matches what R emits, byte for byte where possible.
Both packages drive the **same** d3 engine (`myIOapi.js`), wired in via a git
submodule so there is one canonical source of truth — no duplicated JS to
drift.

!!! info "Status — 0.1.0 alpha"
    API is settled and matches R's `setMargin`/`setBrush`/etc. surface. The
    JS engine is pinned to a recent R-myIO commit, so the legend, export
    panel, and all 26 primitive renderers (bar/line/area/point/histogram/
    hexbin/treemap/donut/gauge/heatmap/calendarHeatmap/candlestick/waterfall/
    sankey/rangeBar/lollipop/dumbbell/waffle/beeswarm/bump/radar/funnel/
    parallel/text/bracket) match the R Shiny demo. **Currently not rendering
    in 0.1.x:** `boxplot`, `violin`, `ridgeline`, `qq`, `comparison`,
    `survfit`, `histogram_fit` — see [Roadmap](roadmap.md).

## Get started

<div class="grid cards" markdown>

- :material-download: **[Install](installation.md)** — one line, `pip install pymyio`.
- :material-rocket-launch: **[Quickstart](quickstart.md)** — render your first chart in Jupyter.
- :material-chart-box: **[Chart types](charts.md)** — 34 chart types with short examples.
- :material-swap-horizontal: **[R → Python API map](api.md)** — muscle-memory lookup for R-myIO users.
- :material-server: **[Hosts](hosts/index.md)** — where pymyIO runs (Jupyter, Shiny, marimo, …).
- :material-road: **[Roadmap](roadmap.md)** — what's landing between 0.1 and 1.0.

</div>

## Try the live demo

A Shiny-for-Python gallery showcasing every working chart type is deployed at
[https://pymyio.morton-analytics.com/](https://pymyio.morton-analytics.com/)
(alongside the R-myIO gallery at
[https://www.morton-analytics.com/myio/](https://www.morton-analytics.com/myio/)).
Source lives in [`app/app.py`](https://github.com/mortonanalytics/pymyIO/blob/main/app/app.py).

## Architecture: one engine, two wrappers

```text
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
against the submodule directly.

## License

MIT. The vendored myIO engine is also MIT-licensed.

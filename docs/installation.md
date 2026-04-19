# Installation

## From PyPI

```bash
pip install pymyio
```

Optional extras:

```bash
pip install 'pymyio[pandas]'   # if you haven't already installed pandas
pip install 'pymyio[polars]'   # polars DataFrame support
pip install 'pymyio[shiny]'    # Shiny-for-Python integration
```

## From source (development)

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

## Python version

`pymyIO` requires Python 3.9+. Verified on 3.9, 3.10, 3.11, 3.12, and 3.13.

## Core dependencies

- [`anywidget`](https://github.com/manzt/anywidget) — widget runtime that works
  in Jupyter, VS Code, marimo, Panel, and Solara with no host-specific shims.
- [`traitlets`](https://traitlets.readthedocs.io/) — reactive state between
  Python and the browser (brush/annotation callbacks).
- [`ipywidgets`](https://ipywidgets.readthedocs.io/) — widget message
  protocol (peer dependency of `anywidget`).

No scientific-Python stack is required by default — the core package works
with `list[dict]` and any DataFrame with a `.to_dict(orient="records")` or
`.to_dicts()` method.

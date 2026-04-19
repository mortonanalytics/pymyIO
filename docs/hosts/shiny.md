# Shiny for Python

**Tier 1** — covered by CI, releases block on regressions.

## Install

- `pip install 'pymyio[shiny]'`
- Pulls in `shinywidgets >= 0.8.0` and `shiny >= 1.0`.

## Minimal example

```python
from shiny import App, ui
from pymyio.shiny import render_myio, output_myio, reactive_brush
from pymyio import MyIO
# ... (point at example_app() for the full pattern)
```

## Reference

- Use `pymyio.shiny.example_app()` for a copy-pasteable runnable app.

## Known gotcha

- Importing `shinywidgets` anywhere in the process installs a global widget-construction callback.
- `pymyio` does NOT transitively import `shinywidgets`.
- Users must explicitly `from pymyio.shiny import ...` to opt in.
- This protects vanilla Jupyter users who happen to have `shinywidgets` installed.

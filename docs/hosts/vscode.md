# VS Code (Jupyter extension)

**Tier 1** — covered by CI, releases block on regressions.

## Install

- `pip install pymyio`
- VS Code Jupyter extension
- `python >= 3.9`

## Render idiom

- Same as JupyterLab:
  `MyIO(data=df).add_layer(...)`
- Renders inline via `_repr_mimebundle_`.

## Known gotchas

- VS Code's notebook webview enforces a Content-Security-Policy.
- anywidget asset rewriting handles `_esm` and `_css` correctly.
- If brush/rollover fails silently, check the VS Code DevTools console for CSP errors.

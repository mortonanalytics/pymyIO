# JupyterLab

**Tier 1** — covered by CI, releases block on regressions.

## Install

- `pip install pymyio`
- `jupyterlab >= 4.0`

## Render idiom

- Last expression in a cell:
  `MyIO(data=df).add_layer(...)`
- Renders inline via `_repr_mimebundle_`.

## Known gotchas

- None currently.
- Works on JupyterLab 4.x out of the box.

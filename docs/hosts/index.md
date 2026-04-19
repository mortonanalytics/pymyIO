# Hosts

`pymyio` renders in every Python notebook / dashboard runtime that can host
an `anywidget`. Tier 1 hosts are covered by CI and release-block on
regressions. Tier 2 hosts are documented best-effort and verified on the
pre-release smoke checklist.

| Host | Tier | Render idiom |
|---|---|---|
| [JupyterLab](jupyterlab.md) | 1 | trailing expression in a cell |
| [VS Code (Jupyter extension)](vscode.md) | 1 | trailing expression in a cell |
| [Shiny for Python](shiny.md) | 1 | `from pymyio.shiny import render_myio, output_myio` |
| [Classic Notebook 7.x](classic-notebook.md) | 2 | trailing expression |
| [Google Colab](colab.md) | 2 | trailing expression |
| [marimo](marimo.md) | 2 | `mo.ui.anywidget(MyIO(...).render())` |
| [Panel](panel.md) | 2 | `pn.pane.IPyWidget(MyIO(...).render())` |
| [Solara](solara.md) | 2 | `solara.display(MyIO(...).render())` |
| [Quarto (HTML)](quarto.md) | 2 | interactive HTML only; PDF/docx not supported |
| static HTML / email / Quarto PDF workaround | — | `pymyio.to_standalone_html(chart)` |

## Picking a host

- **Exploring data interactively** → JupyterLab or VS Code.
- **Building a dashboard users click through** → Shiny for Python.
- **Reproducible reports** → Quarto (HTML output) + `to_standalone_html` for
  anything else.
- **Reactive apps with fine-grained state** → marimo.
- **Classic dashboarding libraries you already use** → Panel or Solara.

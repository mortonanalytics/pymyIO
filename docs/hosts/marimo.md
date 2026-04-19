# marimo

**Tier 2** — documented best-effort, verified manually before each release.

## Render idiom

- `mo.ui.anywidget(MyIO(...).add_layer(...).render())`

## Reactive surface

- `widget.value` returns a dict of all synced traitlets.
- `widget.brushed` and related fields are reactive.

## Known gotchas

- marimo's static HTML export preserves client-side interactivity for anywidgets.

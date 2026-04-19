# Solara

**Tier 2** — documented best-effort, verified manually before each release.

## Render idiom

- `solara.display(MyIO(...).render())`

## Known gotcha

- Solara may render widgets inside a shadow DOM on some hosts.
- anywidget globals land on the outer realm, which is usually fine.
- CSS overrides on `.pymyio-chart` may need to live in the outer stylesheet.

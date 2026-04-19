# Shiny + Jupyter Integration — Layer Contract

All architect agents must read and conform to this contract. Python symbols use snake_case; JS identifiers use camelCase; traitlet names are authoritative and must not drift.

## Scope note

pymyIO is a Python library with a vendored JavaScript engine — not a db/api/ui web stack. The contract layers are:

- **core** — Python top-level package (`pymyio`): new module-level function `to_standalone_html`, new warning class `MyIOStaticWarning`, unchanged `MyIO` / `MyIOWidget` surface
- **engine** — JavaScript (`src/pymyio/static/widget.js`): two targeted hardenings, one new data-attribute contract
- **integrations** — optional Python submodule (`pymyio.shiny`) activated by the `shiny` extra
- **packaging** — `pyproject.toml` dependency pins, extras, and build inclusion
- **tests** — `tests/` directory

No DB, no HTTP API, no React UI. `Rust type` and `TS interface` columns from the skill's template are marked N/A.

## Python symbols (public surface, new in 0.2.0)

| Symbol | Module | Kind | Signature / type |
|---|---|---|---|
| `to_standalone_html` | `pymyio` | function | `(chart_or_config, *, width="100%", height="400px", include_assets="inline", title=None) -> str \| tuple[str, dict[str, bytes]]` |
| `MyIOStaticWarning` | `pymyio` | class | `class MyIOStaticWarning(UserWarning)` |
| `render_myio` | `pymyio.shiny` | re-export | alias for `shinywidgets.render_widget` |
| `output_myio` | `pymyio.shiny` | re-export | alias for `shinywidgets.output_widget` |
| `reactive_brush` | `pymyio.shiny` | function | `(widget: MyIOWidget) -> dict \| None` |
| `reactive_annotated` | `pymyio.shiny` | function | `(widget: MyIOWidget) -> dict \| None` |
| `reactive_rollover` | `pymyio.shiny` | function | `(widget: MyIOWidget) -> dict \| None` |
| `example_app` | `pymyio.shiny` | function | `() -> shiny.App` |

Additions to `pymyio.__all__`: `to_standalone_html`, `MyIOStaticWarning`. `pymyio.shiny` is NOT imported from `pymyio/__init__.py` (see §"Critical import rule").

## MyIOWidget traitlets (authoritative names)

Frozen from 0.1.0 (must not rename, retype, or change sync direction):

| Trait name | Type | Sync | Allow none | Default | Direction |
|---|---|---|---|---|---|
| `config` | `Dict` | `True` | no | `Undefined` (populated in `__init__`) | Python → JS |
| `width` | `Union[Int, Unicode]` | `True` | no | `"100%"` | Python → JS |
| `height` | `Union[Int, Unicode]` | `True` | no | `"400px"` | Python → JS |
| `brushed` | `Dict` | `True` | yes | `None` | JS → Python |
| `annotated` | `Dict` | `True` | yes | `None` | JS → Python |
| `rollover` | `Dict` | `True` | yes | `None` | JS → Python |
| `last_error` | `Dict` | `True` | yes | `None` | JS → Python |

New in 0.2.0:

| Trait name | Type | Sync | Allow none | Default | Direction |
|---|---|---|---|---|---|
| `_base_url` | `Unicode` | `True` | no | `""` | Python → JS |

The underscore prefix signals "private" — may change before 0.2.0 GA without a deprecation cycle.

## Enums

### `include_assets` (to_standalone_html parameter)

| Value | Return shape | Size ceiling |
|---|---|---|
| `"inline"` | `str` (full HTML, all assets inlined) | Emit `MyIOStaticWarning` at 2 MB |
| `"bundled"` | `tuple[str, dict[str, bytes]]` — (html, assets_by_relative_path) | None |

Any other value → `ValueError` naming the allowed set.

### `bundled` asset dict keys (exact set, in order)

```
"myIOapi.js"
"style.css"
"lib/d3.min.js"
"lib/d3-hexbin.js"
"lib/d3-sankey.min.js"
```

Exactly five entries; `widget.js` is NOT included (see §"Standalone vs widget path").

## Warnings and errors

| Class | Raised when | Raised by |
|---|---|---|
| `ValueError` | `include_assets` not in {"inline", "bundled"} | `to_standalone_html` |
| `RuntimeError` | Packaged asset missing from wheel | `to_standalone_html` |
| `ImportError` | `pymyio.shiny` imported without `shinywidgets>=0.8.0` | `pymyio.shiny.__init__` |
| `ImportError` | `pymyio.shiny` imported without `shiny` extra installed | `pymyio.shiny.__init__` |
| `MyIOStaticWarning` | `set_brush`/`set_annotation`/`drag_points` present in chart config | `to_standalone_html` |
| `MyIOStaticWarning` | Inline mode output would exceed 2 MB | `to_standalone_html` |

## JS engine contract (window globals + DOM attributes)

| Name | Location | Type | Set by | Read by |
|---|---|---|---|---|
| `window.myIOchart` | global | constructor function | `myIOapi.js` on load | `widget.js` + standalone HTML |
| `window.__pymyioEngineVersion` | global | string | `widget.js` after load | `widget.js` double-load guard |
| `data-pymyio` | `<script>` attribute | string (asset URL) | `widget.js` `injectScript` | `widget.js` dedup query |
| `data-pymyio-role` | `<script>` attribute | enum: `"d3-core"` \| `"d3-hexbin"` \| `"d3-sankey"` \| `"engine"` | `widget.js` `injectScript` | `widget.js` diagnostics |

The expected script count after one or more widgets render on the same page is **exactly 4** (one per role).

## `myIOchart` constructor contract (consumed by both paths)

| Name | Shape | Frozen |
|---|---|---|
| Constructor call | `new window.myIOchart({ element, config, width, height })` | yes |
| `.destroy()` method | idempotent, no args | yes |
| `.on(event, handler)` | events: `"brushed" \| "annotated" \| "rollover" \| "error"` | yes |

This is the shared contract of the anywidget render path AND the standalone HTML render path. Changing it breaks both.

## Module relationships

- `pymyio/__init__.py` imports from: `pymyio.chart`, `pymyio.widget`, `pymyio.standalone` (new). Does **not** import `pymyio.shiny`.
- `pymyio.standalone` (new module, backs `to_standalone_html`) imports from: `pymyio.chart` (for the `MyIO` type check only), `pymyio.widget` (for the wheel-asset path resolution only — not the widget class itself).
- `pymyio.shiny.__init__` imports from: `shinywidgets` (mandatory at import time, version-gated); `shiny` (for `example_app` only, lazy-imported).
- `pymyio.shiny.example_app` imports `pandas` lazily (already a `dev` extra; guard at call time).

## Critical import rule

**`pymyio/__init__.py` must not import `pymyio.shiny` directly or transitively.** Rationale: importing `shinywidgets` installs a global `Widget._widget_construction_callback` that raises `RuntimeError("shinywidgets requires that all ipywidgets be constructed within an active Shiny session")` on every subsequent widget construction. If `pymyio` top-level pulled in `pymyio.shiny`, every vanilla Jupyter notebook with pymyio imported and shinywidgets installed would break.

Enforcement: acceptance criterion 14b in the design doc + an explicit regression test (Phase 1 in the plan).

## Standalone vs widget path (what each emits)

| Asset | Inline mode | Bundled mode | Widget (anywidget) mode |
|---|---|---|---|
| `myIOapi.js` contents | embedded as `<script>…contents…</script>` | written to sidecar dir, referenced by relative URL | `<script src>` injected at runtime by widget.js |
| `lib/d3.min.js` | embedded inline | sidecar | runtime injection |
| `lib/d3-hexbin.js` | embedded inline | sidecar | runtime injection |
| `lib/d3-sankey.min.js` | embedded inline | sidecar | runtime injection |
| `style.css` | embedded inline as `<style>` | sidecar, `<link rel=stylesheet>` | injected by anywidget `_css` |
| `widget.js` | **not included** (no anywidget runtime) | **not included** | ESM module loaded by anywidget |
| `config` dict | inlined as `<script type="application/json">` + JS init | same | passed via traitlet |

## Packaging contract

### `pyproject.toml` changes

```toml
[project]
dependencies = [
  "anywidget>=0.10.0,<0.11",
  "traitlets>=5.9,<6",
  "ipywidgets>=8.0",
]

[project.optional-dependencies]
shiny = [
  "shinywidgets>=0.8.0",
  "shiny>=1.0",
]
pandas = ["pandas>=1.5"]
polars = ["polars>=0.20"]
dev = [
  "pytest>=7",
  "pytest-playwright>=0.5",
  "pandas>=1.5",
  "shinywidgets>=0.8.0",
  "shiny>=1.0",
  "ruff>=0.4",
]
```

### `force-include` block (frozen + one addition)

The existing 5-file block in `[tool.hatch.build.targets.wheel.force-include]` must remain byte-identical. The wheel must contain `pymyio/static/{myIOapi.js, style.css, widget.js, lib/d3.min.js, lib/d3-hexbin.js, lib/d3-sankey.min.js}`.

## Test artifacts (canonical file paths)

| File | New / existing | Purpose |
|---|---|---|
| `tests/test_chart_config.py` | existing — must pass unchanged | Backward-compat regression |
| `tests/test_parity.py` | existing — must pass unchanged | R parity regression |
| `tests/test_standalone_html.py` | new | Slice 3 acceptance criteria |
| `tests/test_shiny_integration.py` | new | Slice 1 acceptance criteria (unit-level; import-guard + signature) |
| `tests/test_shiny_app.py` | new | Slice 1 Playwright-driven app smoke test (skipped unless `shiny` extra installed + playwright browsers) |
| `tests/test_widget_js_contract.py` | new | Slice 2 static JS contract (regex assertions over widget.js) |
| `tests/test_regression_shinywidgets_footgun.py` | new | Criterion 14b — shinywidgets installed but not imported does not break render |

## Gate commands (per slice)

| Slice | Gate command |
|---|---|
| 1 (Shiny) | `pytest tests/test_shiny_integration.py tests/test_regression_shinywidgets_footgun.py -q` |
| 2 (widget.js hardening) | `pytest tests/test_widget_js_contract.py -q` |
| 3 (standalone HTML) | `pytest tests/test_standalone_html.py -q` |
| 4 (version pins / failure posture) | `pip install -e .` with `anywidget==0.9.0` preinstalled → resolves to conflict |
| 5 (backward compat) | `pytest tests/test_chart_config.py tests/test_parity.py -q` |
| Full | `pytest -q` |

## Naming authority

If any architect agent proposes a name that conflicts with this contract (e.g., `pymyio.to_html` instead of `pymyio.to_standalone_html`), the contract wins. Update the agent's output to match before Phase B.

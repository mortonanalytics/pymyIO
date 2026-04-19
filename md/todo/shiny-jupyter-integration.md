# pymyIO 0.2.0 — Shiny + Jupyter Integration (Python-side Implementation Plan)

Source-of-truth: [design](../design/shiny-jupyter-integration.md) and [contract](../design/shiny-jupyter-integration-contract.md). This plan owns Slices 1, 3, 4, 5 (Python-side trait only). Widget.js internals are a separate agent.

Vertical slices, red-green-refactor within each. Do not advance to the next phase until its gate passes.

---

## Phase 1 — Regression guard + `_base_url` trait (Slice 5)

**Why first.** Criterion 14b is the only change that can silently break every existing 0.1.0 user. Must exist and pass before anything else is touched.

### Files

| File | Action | Change |
|---|---|---|
| `tests/test_regression_shinywidgets_footgun.py` | create | Asserts `import pymyio` followed by `MyIO(...).render()` works when `shinywidgets` is installed but `pymyio.shiny` is **not** imported. Asserts `pymyio.__init__` does not transitively import `pymyio.shiny`. |
| `src/pymyio/widget.py` | edit | Add `_base_url = traitlets.Unicode("").tag(sync=True)` directly under the `rollover` trait. No other edits. |

### `tests/test_regression_shinywidgets_footgun.py` skeleton

```python
import importlib, subprocess, sys, textwrap, pytest

def test_pymyio_init_does_not_import_shiny_submodule():
    for name in [k for k in sys.modules if k.startswith("pymyio")]:
        del sys.modules[name]
    import pymyio  # noqa: F401
    assert "pymyio.shiny" not in sys.modules

@pytest.mark.skipif(
    importlib.util.find_spec("shinywidgets") is None,
    reason="regression only meaningful when shinywidgets is installed",
)
def test_render_works_with_shinywidgets_installed_but_not_imported():
    # CRITICAL: the shinywidgets Widget._widget_construction_callback side-
    # effect is process-wide. Run in a subprocess so no prior import in the
    # test session has already armed the callback.
    script = textwrap.dedent('''
        import sys
        assert "shinywidgets" not in sys.modules
        import pymyio
        assert "pymyio.shiny" not in sys.modules
        w = (pymyio.MyIO(data=[{"x":1,"y":2}])
                .add_layer(type="point", label="p",
                           mapping={"x_var":"x","y_var":"y"})
                .render())
        assert w.config["layers"][0]["type"] == "point"
    ''')
    r = subprocess.run([sys.executable, "-c", script], capture_output=True, text=True)
    assert r.returncode == 0, f"stderr:\n{r.stderr}"

def test_base_url_trait_present_and_empty_by_default():
    import pymyio
    w = pymyio.MyIO(data=[{"x":1,"y":2}]).add_layer(
        type="point", label="p", mapping={"x_var":"x","y_var":"y"},
    ).render()
    assert w._base_url == ""
    assert w.traits()["_base_url"].metadata.get("sync") is True
```

### Wiring verification

```bash
grep -n "_base_url" src/pymyio/widget.py                  # one match
grep -rn "pymyio.shiny" src/pymyio/__init__.py            # zero matches
grep -rn "import shinywidgets" src/pymyio/__init__.py src/pymyio/chart.py src/pymyio/widget.py  # zero matches
```

### Gate

```bash
pytest tests/test_regression_shinywidgets_footgun.py tests/test_chart_config.py tests/test_parity.py -q
```

---

## Phase 2 — widget.js hardening (Slice 2)

Pairs with Phase 1. The `_base_url` trait added in Phase 1 has no consumer until this phase lands. Do not leave an inter-phase gap.

### Files

| File | Action | Change |
|---|---|---|
| `src/pymyio/static/widget.js` | edit | Three edits below; all other lines untouched. |
| `tests/test_widget_js_contract.py` | create | Static regex assertions over widget.js (not a runtime test). |

### Edits (line ranges against the current 112-line file)

**A. `injectScript` gains `role` param (widget.js:7, :19)**

```js
// before
function injectScript(url) {
  ...
  tag.dataset.pymyio = url;
// after
function injectScript(url, role) {
  ...
  tag.dataset.pymyio = url;
  tag.dataset.pymyioRole = role;
```

**B. `loadEngine` guard + role args + version stamp (widget.js:26–35)**

```js
async function loadEngine(baseUrl) {
  if (typeof window.myIOchart === "function") {
    window.__pymyioEngineVersion ||= "unknown";
    return Promise.resolve();
  }
  if (enginePromise) return enginePromise;
  enginePromise = (async () => {
    await injectScript(`${baseUrl}lib/d3.min.js`, "d3-core");
    await injectScript(`${baseUrl}lib/d3-hexbin.js`, "d3-hexbin");
    await injectScript(`${baseUrl}lib/d3-sankey.min.js`, "d3-sankey");
    await injectScript(`${baseUrl}myIOapi.js`, "engine");
    window.__pymyioEngineVersion = (window.myIOchart?.version) || "unknown";
  })();
  return enginePromise;
}
```

**C. Three-tier `baseUrl` (widget.js:50–52)**

```js
const override = model.get("_base_url");
const baseUrl = (typeof override === "string" && override.length > 0)
  ? (override.endsWith("/") ? override : override + "/")
  : ((typeof import.meta !== "undefined" && import.meta.url)
      ? new URL(".", import.meta.url).href
      : "./");
```

### `tests/test_widget_js_contract.py` assertions

| # | Pattern | Expectation |
|---|---|---|
| 1 | `"d3-core"` string literal | match ≥ 1 |
| 2 | `"d3-hexbin"` string literal | match ≥ 1 |
| 3 | `"d3-sankey"` string literal | match ≥ 1 |
| 4 | `"engine"` string literal | match ≥ 1 |
| 5 | `__pymyioEngineVersion` | match ≥ 1 |
| 6 | `model\.get\("_base_url"\)` | match ≥ 1 |
| 7 | `injectScript\(` call sites | exactly 4 |
| 8 | `cdn\.jsdelivr` | zero matches |
| 9 | `new window\.myIOchart` (regression guard — constructor contract frozen) | exactly 1 |
| 10 | `chart\.on\?\.\(` (total event-handler wire-ups: error + brushed + annotated + rollover) | exactly 4 |
| 11 | each of `"brushed"`, `"annotated"`, `"rollover"`, `"error"` appearing as an `.on?.(...)` first arg | each match ≥ 1 |

### Backward-compat freeze (widget.js)

- Lines 79–84 — `new window.myIOchart({ element, config, width, height })` call identical.
- Lines 85–95 — `.on?.("error"|"brushed"|"annotated"|"rollover", …)` wiring identical.
- Lines 37–40 (`applySize`), 98–104 (`model.on(...)`), 106–108 (cleanup) — untouched.

### Wiring verification

```bash
node --check src/pymyio/static/widget.js
grep -c 'injectScript(' src/pymyio/static/widget.js           # exactly 5 (1 definition + 4 calls)
grep -c 'data-pymyio-role\|pymyioRole' src/pymyio/static/widget.js  # >= 1
grep 'cdn.jsdelivr' src/pymyio/static/widget.js              # ZERO matches (exit 1)
```

### Gate

```bash
node --check src/pymyio/static/widget.js
pytest tests/test_widget_js_contract.py tests/test_regression_shinywidgets_footgun.py tests/test_chart_config.py tests/test_parity.py -q
```

---

## Phase 3 — Standalone HTML (`pymyio.to_standalone_html`) (Slice 3)

### Files

| File | Action | Change |
|---|---|---|
| `src/pymyio/standalone.py` | create | Module backing `to_standalone_html`; asset loader, inline + bundled modes, warnings. |
| `src/pymyio/__init__.py` | edit | Add `from .standalone import to_standalone_html, MyIOStaticWarning`; add both to `__all__`. |
| `tests/test_standalone_html.py` | create | Criteria 9–13. |

### Asset loader (frozen `importlib.resources` form — required; `__file__` math breaks in zipped wheels)

```python
from importlib.resources import files
_ASSET_KEYS = ("myIOapi.js", "style.css",
               "lib/d3.min.js", "lib/d3-hexbin.js", "lib/d3-sankey.min.js")

def _load_assets() -> dict[str, bytes]:
    root = files("pymyio") / "static"
    out = {}
    for key in _ASSET_KEYS:
        ref = root.joinpath(*key.split("/"))
        if not ref.is_file():
            raise RuntimeError(
                f"pymyIO packaging error: required asset '{key}' missing from wheel "
                f"(expected at pymyio/static/{key})."
            )
        out[key] = ref.read_bytes()
    return out
```

### Warning class + interactive check

```python
class MyIOStaticWarning(UserWarning):
    """Emitted when to_standalone_html() degrades chart capabilities."""

_INTERACTIVE_KEYS = ("brush", "annotation")  # interactions.<k>.enabled
def _has_interactive_only_features(cfg: dict) -> list[str]:
    inter = cfg.get("interactions") or {}
    found = []
    for k in _INTERACTIVE_KEYS:
        node = inter.get(k) or {}
        if isinstance(node, dict) and node.get("enabled"):
            found.append(k)
    if inter.get("dragPoints"):
        found.append("dragPoints")
    return found
```

### `to_standalone_html` structure

```python
def to_standalone_html(chart_or_config, *, width="100%", height="400px",
                       include_assets="inline", title=None):
    if include_assets not in ("inline", "bundled"):
        raise ValueError(
            f"include_assets must be 'inline' or 'bundled', got {include_assets!r}."
        )
    from .chart import MyIO
    cfg = chart_or_config.to_config() if isinstance(chart_or_config, MyIO) else dict(chart_or_config)

    interactive = _has_interactive_only_features(cfg)
    if interactive:
        warnings.warn(
            f"Chart uses interactive-only features {interactive}; "
            "static HTML renders the UI but callbacks no-op without a Python kernel.",
            MyIOStaticWarning, stacklevel=2,
        )

    assets = _load_assets()                          # RuntimeError if wheel broken
    uid = uuid.uuid4().hex[:12]
    cfg_json = _safe_json(cfg)                       # escapes </ for inline script island
    page_title = html.escape(title or "pymyIO chart")
    width_js, height_js = _js_dims(width, height)    # numeric if int-like, else "'...'"

    if include_assets == "inline":
        html_str = _render_inline(uid, cfg_json, page_title, width, height,
                                  width_js, height_js, assets)
        if len(html_str.encode("utf-8")) > 2 * 1024 * 1024:
            warnings.warn(
                "Inline HTML exceeds 2 MB; pass include_assets='bundled' to "
                "emit sidecar assets instead.",
                MyIOStaticWarning, stacklevel=2,
            )
        return html_str

    html_str = _render_bundled(uid, cfg_json, page_title, width, height,
                                width_js, height_js)
    return html_str, dict(assets)
```

### Safe helpers

```python
def _safe_json(cfg: dict) -> str:
    # Closes the </script> escape hole when the JSON is inlined into a
    # <script type="application/json"> island. ensure_ascii keeps Unicode
    # values safe; the </ → <\/ pass handles any string value containing
    # the closing script token.
    return json.dumps(cfg, default=str, ensure_ascii=True).replace("</", "<\\/")

def _js_dims(width, height) -> tuple[str, str]:
    def one(v):
        if isinstance(v, (int, float)):
            return str(int(v))
        return json.dumps(str(v))   # quotes + escapes a CSS value like "100%"
    return one(width), one(height)
```

### Inline HTML template (explicit concatenation — NOT str.format)

The vendored JS/CSS contains `{` literals (function bodies, CSS rules). Using `str.format` or f-strings over the bytes would throw `KeyError`. Build the HTML by concatenation with seven string chunks. Asset bytes are decoded with `errors="strict"` — any non-UTF-8 byte in the vendored files is a packaging bug that should surface as `UnicodeDecodeError`.

```python
def _render_inline(uid, cfg_json, page_title, width, height,
                   width_js, height_js, assets):
    def decoded(key): return assets[key].decode("utf-8")
    css      = decoded("style.css")
    d3       = decoded("lib/d3.min.js")
    d3hex    = decoded("lib/d3-hexbin.js")
    d3sank   = decoded("lib/d3-sankey.min.js")
    engine   = decoded("myIOapi.js")
    esc_css  = _escape_script_body(css)          # CSS embedded inline is raw text
    init = (
      "(function(){"
      f" var el=document.getElementById('pymyio-chart-{uid}');"
      f" var cfg=JSON.parse(document.getElementById('pymyio-config-{uid}').textContent);"
      f" new window.myIOchart({{element:el,config:cfg,width:{width_js},height:{height_js}}});"
      "})();"
    )
    parts = [
      "<!doctype html><html><head><meta charset=\"utf-8\">",
      f"<title>{page_title}</title>",
      f"<style>{esc_css}</style></head><body>",
      f'<div id="pymyio-chart-{uid}" class="pymyio-chart" '
      f'style="width:{html.escape(str(width))};height:{html.escape(str(height))}"></div>',
      f'<script type="application/json" id="pymyio-config-{uid}">{cfg_json}</script>',
      f"<script>{_escape_script_body(d3)}</script>",
      f"<script>{_escape_script_body(d3hex)}</script>",
      f"<script>{_escape_script_body(d3sank)}</script>",
      f"<script>{_escape_script_body(engine)}</script>",
      f"<script>{init}</script>",
      "</body></html>",
    ]
    return "".join(parts)

def _escape_script_body(s: str) -> str:
    # Any literal </script> (or </style>) inside the body would terminate the
    # enclosing tag. Replace </ with <\/ which is inert in JS strings and CSS.
    return s.replace("</", "<\\/")
```

`_render_bundled` emits the same skeleton with `<link rel="stylesheet" href="style.css">` and `<script src="lib/d3.min.js"></script>` etc. in place of inline content. The assets dict returned contains the five keys in `_ASSET_KEYS` verbatim.

### Test skeleton (`tests/test_standalone_html.py`)

Covers:
- criterion 9 — Playwright on `file://`, marked `skipif` when `playwright` browsers absent
- criterion 10 — brush warning asserted via `pytest.warns(MyIOStaticWarning, match="interactive-only")`
- criterion 11 — bundled mode returns tuple; `set(assets.keys()) == set(_ASSET_KEYS)` exact match
- criterion 12 — `pytest.raises(ValueError, match="inline.*bundled")` for `include_assets="banana"`
- criterion 13 — simulated missing asset via `monkeypatch.setattr("pymyio.standalone._ASSET_KEYS", ("missing.js", *_ASSET_KEYS))` (monkeypatching `_ASSET_KEYS` is version-stable; avoid monkeypatching `importlib.resources.files()`)
- security guard — assert `</script>` inside a config string value appears as `<\/script>` in the rendered HTML

`test_packaging.py` is owned by Phase 5 (companion to criterion 14), not Phase 3.

Playwright-backed criterion 9 test structure: write `html_str` to `tmp_path/"chart.html"`, launch Playwright, `page.goto(f"file://{path}")`, assert `page.locator(".pymyio-chart svg").count() >= 1` within 10s, assert at least one rendered SVG mark.

### Wiring verification

```bash
grep -n "to_standalone_html" src/pymyio/__init__.py            # imported + in __all__
grep -n "MyIOStaticWarning"  src/pymyio/__init__.py            # imported + in __all__
grep -n "importlib.resources" src/pymyio/standalone.py         # one match
grep -n "pathlib.Path(__file__)" src/pymyio/standalone.py      # ZERO matches (forbidden)
grep -n "widget.js" src/pymyio/standalone.py                   # ZERO matches (excluded by contract)
```

### Gate

```bash
pytest tests/test_standalone_html.py -q
pytest tests/test_chart_config.py tests/test_parity.py tests/test_regression_shinywidgets_footgun.py -q
```

---

## Phase 4 — Shiny integration (`pymyio.shiny`) (Slice 1)

### Files

| File | Action | Change |
|---|---|---|
| `src/pymyio/shiny/__init__.py` | create | Version gate, aliases, reactive_* helpers, `example_app`. |
| `tests/test_shiny_integration.py` | create | Unit tests for import-guard, aliasing, signatures (criteria 3, 4). |
| `tests/test_shiny_app.py` | create | Playwright-driven smoke test (criteria 1, 2); skipif missing extras/browsers. |

### `pymyio/shiny/__init__.py` skeleton

```python
"""Shiny-for-Python integration. Not imported by pymyio/__init__.py — see
contract §'Critical import rule' (shinywidgets registers a global Widget
construction callback on import)."""
from __future__ import annotations

from importlib import metadata as _md

_MIN_SW = "0.8.0"
try:
    _sw_ver = _md.version("shinywidgets")
except _md.PackageNotFoundError as e:
    raise ImportError(
        "pymyio.shiny requires the 'shiny' extra. "
        "Install with: pip install 'pymyio[shiny]'"
    ) from e

def _ver_ge(actual: str, minimum: str) -> bool:
    def tup(s): return tuple(int(x) for x in s.split(".")[:3] if x.isdigit())
    return tup(actual) >= tup(minimum)

if not _ver_ge(_sw_ver, _MIN_SW):
    raise ImportError(
        f"pymyio.shiny requires shinywidgets>={_MIN_SW}; found {_sw_ver}. "
        "Upgrade with: pip install -U 'shinywidgets>=0.8.0'"
    )

import shinywidgets as _sw

render_myio = _sw.render_widget
"""Alias for :func:`shinywidgets.render_widget`. Muscle-memory parity with R myIO's `renderMyIO`."""

output_myio = _sw.output_widget
"""Alias for :func:`shinywidgets.output_widget`. Muscle-memory parity with R myIO's `myIOOutput`."""

def reactive_brush(widget):
    """Return the `brushed` traitlet reactively via shinywidgets.reactive_read."""
    return _sw.reactive_read(widget, "brushed")

def reactive_annotated(widget):
    return _sw.reactive_read(widget, "annotated")

def reactive_rollover(widget):
    return _sw.reactive_read(widget, "rollover")

def example_app():
    """Return a runnable shiny.App demonstrating render_myio + reactive_brush."""
    from shiny import App, ui, reactive, render
    import pandas as pd
    from pymyio import MyIO
    mtcars = pd.DataFrame([
        {"wt":2.620,"mpg":21.0,"cyl":6},{"wt":2.875,"mpg":21.0,"cyl":6},
        {"wt":2.320,"mpg":22.8,"cyl":4},{"wt":3.215,"mpg":21.4,"cyl":6},
        {"wt":3.440,"mpg":18.7,"cyl":8},{"wt":3.460,"mpg":18.1,"cyl":4},
    ])
    app_ui = ui.page_fluid(
        ui.h2("pymyio + Shiny"),
        output_myio("chart"),
        ui.h3("Brushed:"), ui.output_text("brushed_out"),
    )
    def server(input, output, session):
        @render_myio
        def chart():
            return (MyIO(data=mtcars)
                    .add_layer(type="point", label="cars",
                               mapping={"x_var":"wt","y_var":"mpg"})
                    .set_brush()
                    .render())
        @render.text
        def brushed_out():
            # shinywidgets 0.6+ attaches `.widget` onto the @render_widget-
            # decorated function after first render. If this pattern drifts
            # in a future shinywidgets release, fall back to polling the
            # widget instance captured via session state.
            b = reactive_brush(chart.widget)
            return "none" if not b else str(b)
    return App(app_ui, server)
```

`mtcars` is a public-domain R built-in dataset (Henderson & Velleman, 1981); no licensing concern from vendoring the six rows inline.

The version check above uses a local `_ver_ge` tuple helper rather than `packaging.version.Version` — `packaging` is not a declared dependency of `pymyio`, and introducing it here would expand the import surface of `pymyio.shiny`.

### `tests/test_shiny_integration.py` skeleton

```python
import importlib, sys, pytest

shinywidgets = pytest.importorskip("shinywidgets")

def _reimport_pymyio_shiny():
    for k in [m for m in sys.modules if m.startswith("pymyio.shiny")]:
        del sys.modules[k]
    return importlib.import_module("pymyio.shiny")

def test_aliases_point_at_shinywidgets():
    mod = _reimport_pymyio_shiny()
    assert mod.render_myio is shinywidgets.render_widget
    assert mod.output_myio is shinywidgets.output_widget

def test_reactive_helpers_are_callable():
    mod = _reimport_pymyio_shiny()
    for name in ("reactive_brush","reactive_annotated","reactive_rollover"):
        assert callable(getattr(mod, name))

def test_too_old_shinywidgets_raises(monkeypatch):
    from importlib import metadata as md
    orig = md.version
    def fake(name):
        return "0.5.0" if name == "shinywidgets" else orig(name)
    monkeypatch.setattr(md, "version", fake)
    for k in [m for m in sys.modules if m.startswith("pymyio.shiny")]:
        del sys.modules[k]
    with pytest.raises(ImportError, match=r"0\.8\.0.*pip install"):
        importlib.import_module("pymyio.shiny")

def test_missing_shinywidgets_raises(monkeypatch):
    from importlib import metadata as md
    def fake(name):
        if name == "shinywidgets": raise md.PackageNotFoundError(name)
        return md.version(name)
    monkeypatch.setattr(md, "version", fake)
    for k in [m for m in sys.modules if m.startswith("pymyio.shiny")]:
        del sys.modules[k]
    with pytest.raises(ImportError, match=r"pymyio\[shiny\]"):
        importlib.import_module("pymyio.shiny")
```

### `tests/test_shiny_app.py` skeleton

One Playwright test: launches `example_app()` with `shiny run` via subprocess, waits for `svg circle` in `#chart`, programmatically dispatches a brush drag on the SVG, asserts the text readout becomes non-`none` within 2s. Marked `skipif` when `shiny`/`playwright` browsers are missing.

### Wiring verification

```bash
grep -rn "pymyio.shiny" src/pymyio/__init__.py                 # ZERO matches
grep -rn "import shinywidgets" src/pymyio/__init__.py          # ZERO matches
grep -n "shinywidgets" src/pymyio/shiny/__init__.py            # present
grep -n "reactive_read" src/pymyio/shiny/__init__.py           # 3 helper matches
```

### Gate

```bash
pytest tests/test_shiny_integration.py tests/test_shiny_app.py tests/test_regression_shinywidgets_footgun.py -q
```

(Criteria 1 and 2 live in `test_shiny_app.py`; they will `skip` when `shiny` binary or Playwright browsers are absent but must be in the gate.)

---

## Phase 5 — Packaging + polish (Slice 4)

### Files

| File | Action | Change |
|---|---|---|
| `pyproject.toml` | edit | Bump `version = "0.2.0"`. Replace `[project].dependencies` and `[project.optional-dependencies]` per contract §"pyproject.toml changes". |
| `src/pymyio/__init__.py` | edit | `__version__ = "0.2.0"`. Confirm `to_standalone_html`, `MyIOStaticWarning` in `__all__` (done in Phase 3). |
| `tests/test_public_api_freeze.py` | create | Asserts `pymyio.__all__` set equals the 0.1.0 baseline ∪ `{to_standalone_html, MyIOStaticWarning}`. Guards the 0.1.0 backward-compat contract from accidental removal. |
| `tests/test_wheel_contents.py` | create | Parses `pyproject.toml` via `tomllib`; asserts `[tool.hatch.build.targets.wheel.force-include]` maps the 6 frozen asset paths (5 pre-0.2.0 + `widget.js` already in the tree). |
| `tests/test_packaging.py` | create | Companion to criterion 14. Asserts `importlib.metadata.version("anywidget")` tuple-compares `>= (0,10,0)` and `< (0,11,0)`. |

### `pyproject.toml` patch (literal per contract)

```toml
[project]
version = "0.2.0"
dependencies = [
  "anywidget>=0.10.0,<0.11",
  "traitlets>=5.9,<6",
  "ipywidgets>=8.0",
]

[project.optional-dependencies]
shiny   = ["shinywidgets>=0.8.0", "shiny>=1.0"]
pandas  = ["pandas>=1.5"]
polars  = ["polars>=0.20"]
dev     = [
  "pytest>=7",
  "pytest-playwright>=0.5",
  "pandas>=1.5",
  "shinywidgets>=0.8.0",
  "shiny>=1.0",
  "ruff>=0.4",
]
```

`[tool.hatch.build.targets.wheel.force-include]` block is frozen — do not touch.

### Wiring verification

```bash
grep -n 'version = "0.2.0"' pyproject.toml src/pymyio/__init__.py
grep -n 'anywidget>=0.10.0,<0.11' pyproject.toml
grep -n '^shiny\s*=' pyproject.toml
python -c "import pymyio; assert pymyio.__version__ == '0.2.0'; pymyio.MyIOStaticWarning; pymyio.to_standalone_html"
```

### Gate

```bash
pip install -e ".[dev,shiny]"
pytest -q
python -c "import pymyio; pymyio.MyIOStaticWarning; print(pymyio.__version__)"
pytest tests/test_public_api_freeze.py tests/test_wheel_contents.py tests/test_packaging.py -q
```

---

## Phase 6 — Tier-1 integration smokes + Tier-2 host docs (Slice 2 completion)

Slice 2's tiered coverage (design §Slice 2 "Host contract (tiered)") is only partly closed by widget.js static regex tests. This phase adds the runtime verification for Tier-1 hosts and the documentation artifacts for Tier-2.

### Files

| File | Action | Change |
|---|---|---|
| `tests/test_jupyter_smoke.py` | create | Playwright-driven JupyterLab 4.x smoke: `jupyter lab --no-browser --port=…` in a subprocess, open a notebook with a pymyIO cell, assert `.pymyio-chart svg` renders within 10 s. Covers criteria 5 and (by extension, same host family) 6. `skipif` when `jupyterlab` or Playwright browsers missing. |
| `tests/test_widget_runtime_script_count.py` | create | Companion to criterion 8 runtime check. Exercises the **anywidget (widget.js)** render path, not `to_standalone_html()` — only widget.js performs `injectScript`. Test renders two `MyIO(...).render()` widgets in the same JupyterLab notebook via Playwright and asserts `document.querySelectorAll('script[data-pymyio]').length === 4` plus `typeof window.__pymyioEngineVersion === 'string'`. Skipif JupyterLab or Playwright browsers absent. |
| `docs/hosts/jupyterlab.md` | create | Tier-1 host page: install, one-line example, known gotchas. |
| `docs/hosts/vscode.md` | create | Tier-1 host page. |
| `docs/hosts/shiny.md` | create | Tier-1 host page: `pip install pymyio[shiny]` + `example_app()` pointer. |
| `docs/hosts/colab.md` | create | Tier-2 host page: known-issues for sandboxed iframe; `_base_url` override hint. |
| `docs/hosts/marimo.md` | create | Tier-2: `mo.ui.anywidget(MyIO(...).render())`. |
| `docs/hosts/panel.md` | create | Tier-2: `pn.pane.IPyWidget(...)`. |
| `docs/hosts/solara.md` | create | Tier-2: `solara.display(...)`. |
| `docs/hosts/quarto.md` | create | Tier-2: interactive HTML works; PDF/docx not supported (design OQ4 decision (a)). |
| `docs/hosts/classic-notebook.md` | create | Tier-2: Notebook 7 works; classic <7 requires anywidget ESM shim. |
| `README.md` | edit | Append "Where pymyIO runs" table — host, one-line snippet, tier, link to `docs/hosts/*.md`. |

### Wiring verification

```bash
ls docs/hosts/ | wc -l          # >= 8 (the eight host pages)
grep -c "Where pymyIO runs" README.md  # exactly 1
```

### Gate

```bash
pytest tests/test_jupyter_smoke.py tests/test_widget_runtime_script_count.py -q
# Tier-2 manual smoke checklist is release-tag gated, not CI-gated — document
# the pre-release procedure in docs/hosts/_release-checklist.md.
```

---

## Cross-phase freeze list

Must not drift. Touching any of these in 0.2.0 is a review-blocker.

- `MyIOWidget` traits other than the new `_base_url`.
- `pymyio.__all__` 0.1.0 symbols.
- `[tool.hatch.build.targets.wheel.force-include]` block.
- `pymyio/__init__.py` must not import `pymyio.shiny`.
- Standalone HTML must NOT embed `widget.js` (anywidget-only artifact).

---

## Task Manifest

Tasks are grouped by phase; gates reference commands inside the phase's "Gate" section. `claude-code` owns multi-file or load-bearing edits; `codex` owns self-contained files from clear specs. Independent tasks within a phase may run in parallel during `/co-code`.

| Task | Agent | Files | Depends On | Gate | Status |
|------|-------|-------|------------|------|--------|
| T1: Create regression-guard test for shinywidgets footgun + `_base_url` trait | codex | `tests/test_regression_shinywidgets_footgun.py` | — | `pytest tests/test_regression_shinywidgets_footgun.py -q` (will fail until T2 lands) | pending |
| T2: Add `_base_url = traitlets.Unicode("").tag(sync=True)` to MyIOWidget | claude-code | `src/pymyio/widget.py` | T1 | `pytest tests/test_regression_shinywidgets_footgun.py tests/test_chart_config.py tests/test_parity.py -q` | pending |
| T3: Harden widget.js (3 edits: `injectScript(url, role)`, `loadEngine` guard + version stamp, three-tier `baseUrl`) | claude-code | `src/pymyio/static/widget.js` | T2 | `node --check src/pymyio/static/widget.js` | pending |
| T4: Create widget.js static-contract regex tests | codex | `tests/test_widget_js_contract.py` | T3 | `pytest tests/test_widget_js_contract.py -q` | pending |
| T5: Create standalone module (asset loader, safe-JSON, interactive check, render_inline, render_bundled, MyIOStaticWarning) | claude-code | `src/pymyio/standalone.py` | T2 | `python -c "import pymyio.standalone; pymyio.standalone._load_assets()"` | pending |
| T6: Wire `to_standalone_html` and `MyIOStaticWarning` into package root (imports + `__all__`) | claude-code | `src/pymyio/__init__.py` | T5 | `python -c "import pymyio; pymyio.to_standalone_html; pymyio.MyIOStaticWarning"` | pending |
| T7: Create standalone HTML tests (criteria 9–13 + security guard) | codex | `tests/test_standalone_html.py` | T6 | `pytest tests/test_standalone_html.py -q` | pending |
| T8: Create `pymyio.shiny` submodule (version gate, aliases, reactive_* helpers, `example_app`) | claude-code | `src/pymyio/shiny/__init__.py` | T7 | `python -c "import pymyio.shiny; pymyio.shiny.render_myio; pymyio.shiny.reactive_brush"` | pending |
| T9: Create Shiny integration unit tests (aliases + version-gate behavior) | codex | `tests/test_shiny_integration.py` | T8 | `pytest tests/test_shiny_integration.py -q` | pending |
| T10: Create Shiny Playwright app smoke test (criteria 1, 2) | claude-code | `tests/test_shiny_app.py` | T8 | `pytest tests/test_shiny_app.py -q` (skips if browsers missing) | pending |
| T11: Update `pyproject.toml` (version 0.2.0, dependency pins, `shiny` extra, dev extra additions) | codex | `pyproject.toml` | T10 | `pip install -e ".[dev,shiny]"` resolves; `python -c "import pymyio; assert pymyio.__version__ == '0.2.0'"` | pending |
| T12: Bump `__version__` to 0.2.0 | codex | `src/pymyio/__init__.py` | T11 | `python -c "import pymyio; print(pymyio.__version__)"` equals `0.2.0` | pending |
| T13: Create public-API freeze test | codex | `tests/test_public_api_freeze.py` | T12 | `pytest tests/test_public_api_freeze.py -q` | pending |
| T14: Create wheel-contents freeze test | codex | `tests/test_wheel_contents.py` | T12 | `pytest tests/test_wheel_contents.py -q` | pending |
| T15: Create packaging version-floor test | codex | `tests/test_packaging.py` | T12 | `pytest tests/test_packaging.py -q` | pending |
| T16: Create JupyterLab smoke Playwright test (criteria 5–6) | claude-code | `tests/test_jupyter_smoke.py` | T12 | `pytest tests/test_jupyter_smoke.py -q` | pending |
| T17: Create anywidget runtime script-count test (criterion 8) | claude-code | `tests/test_widget_runtime_script_count.py` | T12 | `pytest tests/test_widget_runtime_script_count.py -q` | pending |
| T18: Create Tier-1 host docs (JupyterLab, VS Code, Shiny) | codex | `docs/hosts/jupyterlab.md`, `docs/hosts/vscode.md`, `docs/hosts/shiny.md` | — | `ls docs/hosts/{jupyterlab,vscode,shiny}.md` | pending |
| T19: Create Tier-2 host docs (Colab, marimo, Panel, Solara, Quarto, classic Notebook) | codex | `docs/hosts/colab.md`, `docs/hosts/marimo.md`, `docs/hosts/panel.md`, `docs/hosts/solara.md`, `docs/hosts/quarto.md`, `docs/hosts/classic-notebook.md` | — | `ls docs/hosts/` shows 9 files including `_release-checklist.md` from T20 | pending |
| T20: Create Tier-2 release checklist doc | codex | `docs/hosts/_release-checklist.md` | — | file exists, names each Tier-2 host | pending |
| T21: Append "Where pymyIO runs" section to README | codex | `README.md` | T18, T19 | `grep -c "Where pymyIO runs" README.md` equals 1 | pending |
| T22: Full-suite gate (all phases green) | claude-code | — | T13, T14, T15, T16, T17, T21 | `pytest -q` | pending |

**Parallel groups** (same phase, no inter-dependency — `/co-code` may dispatch simultaneously):

- Group A (after T12): **T13, T14, T15** — three independent test files; all `codex`.
- Group B (after T12): **T16, T17** — two independent Playwright tests; both `claude-code`.
- Group C (independent of runtime code, may start anytime): **T18, T19, T20** — docs files; all `codex`.

**Serial spine:** T1 → T2 → T3 → T4 → T5 → T6 → T7 → T8 → (T9 ∥ T10) → T11 → T12 → (groups A, B, C) → T21 → T22.

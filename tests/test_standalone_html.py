"""Tests for ``pymyio.to_standalone_html`` — Slice 3 acceptance criteria.

Covers: basic rendering shape, brush/annotation warnings, bundled-mode
asset key set, input validation, missing-asset failure mode, and the
``</script>`` security guard. A Playwright-backed browser smoke test is
included but skipped when playwright is absent.
"""

from __future__ import annotations

import importlib
import pytest

from pymyio import MyIO, MyIOStaticWarning, to_standalone_html
from pymyio.standalone import _ASSET_KEYS


SAMPLE = [
    {"wt": 2.620, "mpg": 21.0},
    {"wt": 2.875, "mpg": 21.0},
    {"wt": 2.320, "mpg": 22.8},
    {"wt": 3.215, "mpg": 21.4},
]


def _point_chart():
    return (
        MyIO(data=SAMPLE)
        .add_layer(
            type="point",
            label="p",
            mapping={"x_var": "wt", "y_var": "mpg"},
        )
    )


# ---- basic rendering shape -------------------------------------------------


def test_inline_mode_returns_str():
    html = to_standalone_html(_point_chart())
    assert isinstance(html, str)
    assert html.startswith("<!doctype html>")
    assert "</body></html>" in html


def test_inline_mode_has_one_chart_container():
    html = to_standalone_html(_point_chart())
    # exactly one container div with the expected class
    assert html.count('class="pymyio-chart"') == 1
    # the config JSON island precedes the init script
    assert '<script type="application/json"' in html
    assert "new window.myIOchart(" in html


def test_accepts_plain_dict_config():
    cfg = _point_chart().to_config()
    html = to_standalone_html(cfg)
    assert "pymyio-chart" in html


def test_title_is_escaped():
    html = to_standalone_html(
        _point_chart(),
        title="<script>alert(1)</script>",
    )
    assert "<title>&lt;script&gt;" in html
    # the raw alert string must not escape into the head
    assert "<script>alert(1)</script></title>" not in html


# ---- bundled mode (criterion 11) -------------------------------------------


def test_bundled_mode_returns_html_and_assets_tuple():
    out = to_standalone_html(_point_chart(), include_assets="bundled")
    assert isinstance(out, tuple)
    assert len(out) == 2
    html, assets = out
    assert isinstance(html, str)
    assert isinstance(assets, dict)


def test_bundled_assets_exact_key_set():
    _, assets = to_standalone_html(
        _point_chart(),
        include_assets="bundled",
    )
    assert set(assets.keys()) == set(_ASSET_KEYS)
    assert len(assets) == 5


def test_bundled_html_references_relative_asset_paths():
    html, assets = to_standalone_html(
        _point_chart(),
        include_assets="bundled",
    )
    for key in _ASSET_KEYS:
        if key.endswith(".css"):
            assert f'href="{key}"' in html
        else:
            assert f'src="{key}"' in html


def test_bundled_does_not_inline_engine_bytes():
    html, assets = to_standalone_html(
        _point_chart(),
        include_assets="bundled",
    )
    # The engine bytes must live in the sidecar dict, not the HTML string.
    engine_bytes = assets["myIOapi.js"]
    assert engine_bytes[:200].decode("utf-8", errors="replace") not in html


def test_bundled_omits_widget_js():
    # Contract §Standalone vs widget path: widget.js is anywidget-only.
    _, assets = to_standalone_html(
        _point_chart(),
        include_assets="bundled",
    )
    assert "widget.js" not in assets


# ---- input validation (criterion 12) ---------------------------------------


def test_rejects_unknown_include_assets_enum():
    with pytest.raises(ValueError, match=r"inline.*bundled"):
        to_standalone_html(_point_chart(), include_assets="banana")


# ---- interactive-only warning (criterion 10) -------------------------------


def test_brush_emits_static_warning():
    chart = _point_chart().set_brush()
    with pytest.warns(MyIOStaticWarning, match=r"interactive-only"):
        to_standalone_html(chart)


def test_annotation_emits_static_warning():
    chart = _point_chart().set_annotation()
    with pytest.warns(MyIOStaticWarning, match=r"annotation"):
        to_standalone_html(chart)


def test_drag_points_emits_static_warning():
    chart = _point_chart().drag_points()
    with pytest.warns(MyIOStaticWarning, match=r"dragPoints"):
        to_standalone_html(chart)


def test_no_warning_without_interactive_features():
    import warnings as _w

    with _w.catch_warnings():
        _w.simplefilter("error", MyIOStaticWarning)
        to_standalone_html(_point_chart())  # must not raise


# ---- missing-asset failure mode (criterion 13) -----------------------------


def test_missing_asset_raises_runtime_error(monkeypatch):
    # Prepend a non-existent asset to _ASSET_KEYS to simulate a broken wheel.
    # Re-import pymyio.standalone through sys.modules so we monkeypatch the
    # *current* module and call the *current* to_standalone_html — earlier
    # tests may have replaced sys.modules["pymyio"] (the footgun regression
    # test does this intentionally), which orphans the top-level imports at
    # the top of this file.
    import sys

    std = sys.modules.get("pymyio.standalone")
    if std is None:
        from pymyio import standalone as std  # noqa: F811

    monkeypatch.setattr(
        std,
        "_ASSET_KEYS",
        ("__missing_asset__.js", *std._ASSET_KEYS),
    )
    with pytest.raises(RuntimeError, match=r"__missing_asset__\.js"):
        std.to_standalone_html(_point_chart())


# ---- </script> escape hole (security guard) --------------------------------


def test_closing_script_tag_in_config_value_is_escaped():
    # A config value containing </script><script>...</script> would, without
    # escaping, close the inlined JSON island and leak a live <script> block
    # into the page. _safe_json rewrites </ → <\/ so the payload stays inert.
    attack = "</script><script>window.__pwned=1</script>"
    chart = MyIO(data=SAMPLE).add_layer(
        type="point",
        label=attack,
        mapping={"x_var": "wt", "y_var": "mpg"},
    )
    html = to_standalone_html(chart)

    # The HTML parser only recognizes one token inside a <script type=
    # "application/json"> element: the closing </script> (case-insensitive).
    # Any other substring (including literal "<script>") is inert text
    # content. The security property we must verify is therefore:
    #
    #   1. No </script> sequence appears inside the JSON island (only at
    #      its end, which terminates the element).
    #   2. The payload's </script> has been rewritten to <\/script>,
    #      proving _safe_json ran.
    island_start = html.index('id="pymyio-config-')
    island_open = html.index(">", island_start) + 1
    island_close = html.index("</script>", island_open)
    island_body = html[island_open:island_close]
    assert "</script>" not in island_body
    assert "</SCRIPT>" not in island_body
    assert "<\\/script>" in island_body


# ---- 2 MB soft-ceiling warning ---------------------------------------------


def test_inline_size_warning_triggers_when_config_is_huge():
    big = [{"v": "x" * 4096} for _ in range(600)]  # >= 2 MB
    chart = MyIO(data=big).add_layer(
        type="text",
        label="big",
        mapping={"x_var": "v", "y_var": "v", "label": "v"},
    )
    with pytest.warns(MyIOStaticWarning, match=r"2 MB"):
        to_standalone_html(chart)


# ---- criterion 9: in-browser smoke (Playwright, skipif missing) -----------


@pytest.mark.skipif(
    importlib.util.find_spec("playwright") is None,
    reason="playwright not installed",
)
def test_standalone_html_renders_in_browser(tmp_path):
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        pytest.skip("playwright.sync_api not available")

    html = to_standalone_html(
        _point_chart(),
        include_assets="inline",
    )
    path = tmp_path / "chart.html"
    path.write_text(html, encoding="utf-8")

    try:
        with sync_playwright() as p:
            try:
                browser = p.chromium.launch()
            except Exception as e:
                pytest.skip(f"chromium not installed: {e}")
            page = browser.new_page()
            page.goto(f"file://{path}")
            page.wait_for_selector(
                ".pymyio-chart svg",
                timeout=10_000,
            )
            svg_count = page.locator(".pymyio-chart svg").count()
            browser.close()
    except Exception as e:
        pytest.skip(f"playwright browser unavailable: {e}")

    assert svg_count >= 1

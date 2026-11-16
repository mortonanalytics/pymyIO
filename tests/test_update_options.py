"""MyIOWidget.update_options(): Python counterpart of R updateMyIOOptions() (#45).

Mirrors myIO's tests for #193: the message payload, the validation errors, and
a browser check that an overlay toggle keeps the field chart's playback time.
"""

from __future__ import annotations

import functools
import http.server
import importlib.util
import json
import re
import shutil
import threading
from pathlib import Path
from types import SimpleNamespace

import pytest

from pymyio import MyIO, MyIOWidget

ROOT = Path(__file__).resolve().parent.parent
STATIC = ROOT / "src" / "pymyio" / "static"
FIELD_CLIP = ROOT / "vendor" / "myIO" / "app" / "data" / "field-tracking-data.json"


def _stub():
    # A stand-in with only `send`: constructing a real widget fails once another
    # test in the session has imported pymyio.shiny (shinywidgets arms a
    # process-wide construction callback; see test_regression_shinywidgets_footgun).
    messages: list = []
    return SimpleNamespace(send=lambda msg, buffers=None: messages.append(msg)), messages


def test_update_options_sends_merged_label_updates():
    w, sent = _stub()
    out = MyIOWidget.update_options(w, {"Point cloud": {"profile": [[0, 0], [10, 5]]}},
                           match={"overlays": {"shape": True}, "minPlayers": 4.0})
    assert out is w
    assert sent == [{
        "type": "myio:proxy-options",
        "layers": [
            {"label": "Point cloud", "options": {"profile": [[0, 0], [10, 5]]}},
            {"label": "match", "options": {"overlays": {"shape": True}, "minPlayers": 4}},
        ],
    }]
    assert isinstance(sent[0]["layers"][1]["options"]["minPlayers"], int)


@pytest.mark.parametrize("args, kwargs, message", [
    ((), {}, "supply one or more named"),
    (([("a", {"x": 1})],), {}, "must be a dict of label -> options"),
    (({"a": {}},), {}, "update for layer 'a' must be a named dict"),
    ((), {"a": [1, 2]}, "update for layer 'a' must be a named dict"),
    ((), {"a": {"overlays": {"shape": "yes"}}}, "update_options(): field option overlays"),
    ((), {"a": {"metricWindow": [5, 1]}}, "update_options(): field option metricWindow"),
])
def test_update_options_validates_like_r(args, kwargs, message):
    w, sent = _stub()
    with pytest.raises(ValueError, match=re.escape(message)):
        MyIOWidget.update_options(w, *args, **kwargs)
    assert sent == []


def test_widget_js_applies_proxy_options_without_redrawing():
    source = (STATIC / "widget.js").read_text(encoding="utf-8")
    assert 'model.on("msg:custom"' in source
    assert '"myio:proxy-options"' in source
    assert "chart.updateOptions(updates)" in source
    assert "if (!syncingOptions) draw()" in source


PAGE = """<!doctype html><meta charset="utf-8"><body><div id="root" style="width:900px;height:700px"></div>
<script type="module">
import widget from "./static/widget.js";
const config = await (await fetch("./config.json")).json();
const handlers = {}, state = { config, width: "900px", height: "700px", _base_url: "./static/" };
window.saved = 0;
const model = {
  get: (k) => state[k],
  set: (k, v) => { state[k] = v; (handlers["change:" + k] || []).forEach((f) => f()); },
  save_changes: () => { window.saved += 1; },
  on: (names, f) => names.split(" ").forEach((n) => (handlers[n] ||= []).push(f)),
};
window.model = model;
window.send = (msg) => (handlers["msg:custom"] || []).forEach((f) => f(msg));
widget.render({ model, el: document.getElementById("root") });
</script>"""


@pytest.mark.skipif(importlib.util.find_spec("playwright") is None, reason="playwright not installed")
def test_overlay_toggle_keeps_playback_time_in_a_browser(tmp_path):
    from playwright.sync_api import sync_playwright

    clip = json.loads(FIELD_CLIP.read_text(encoding="utf-8"))
    label = "Match view"
    config = (
        MyIO(clip["tracking"])
        .add_layer(type="field", label=label,
                   mapping={"x_var": "x", "y_var": "y", "time": "time", "entity": "entity_id",
                            "team": "team", "label": "label", "kind": "kind"},
                   options={"pitchLength": clip["pitch"]["length"],
                            "pitchWidth": clip["pitch"]["width"], "maxGap": 0.5,
                            "events": clip["events"]})
        .to_config()
    )
    shutil.copytree(STATIC, tmp_path / "static", symlinks=False)
    (tmp_path / "config.json").write_text(json.dumps(config), encoding="utf-8")
    (tmp_path / "index.html").write_text(PAGE, encoding="utf-8")

    handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(tmp_path))
    handler.log_message = lambda *a, **k: None
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    try:
        with sync_playwright() as p:
            try:
                browser = p.chromium.launch()
            except Exception as e:  # pragma: no cover - environment-dependent
                pytest.skip(f"chromium unavailable: {e}")
            page = browser.new_page()
            page.goto(f"http://127.0.0.1:{server.server_address[1]}/index.html")
            timeline = page.get_by_label("Timeline", exact=True)
            timeline.wait_for(timeout=15_000)
            timeline.evaluate('(el) => { el.value = "7.64"; el.dispatchEvent(new Event("input", { bubbles: true })); }')
            field_time = page.locator(".field-time")
            assert field_time.inner_text() == "7.64 / 20.04 s"
            svg = page.locator("#root svg").first.element_handle()

            page.evaluate("(label) => window.send({ type: 'myio:proxy-options', layers: [{ label, options: { overlays: { shape: true, separation: true } } }] })", label)

            assert field_time.inner_text() == "7.64 / 20.04 s"
            assert page.evaluate("(el) => el.isConnected", svg), "chart was redrawn"
            synced = page.evaluate("() => window.model.get('config').layers[0].options.overlays")
            assert synced == {"shape": True, "separation": True}
            assert page.evaluate("() => window.saved") == 1
            browser.close()
    finally:
        server.shutdown()

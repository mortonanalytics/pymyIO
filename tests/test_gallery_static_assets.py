"""Issue #55: the gallery app (app/app.py) run from a checkout must serve the
engine assets under /pymyio-static/. In a checkout, static/myIOapi.js,
style.css and lib/*.js are symlinks into vendor/myIO, outside the mounted
directory.

The app is imported in a subprocess: importing it pulls in shinywidgets,
which installs a process-wide widget-construction callback that would break
later tests in this session (see test_regression_shinywidgets_footgun.py).
"""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
ASSETS = ["myIOapi.js", "style.css", "lib/d3.min.js", "lib/d3-hexbin.js",
          "lib/d3-sankey.min.js", "widget.js"]


@pytest.mark.skipif(
    importlib.util.find_spec("shiny") is None
    or importlib.util.find_spec("shinywidgets") is None,
    reason="gallery app requires shiny + shinywidgets",
)
def test_gallery_serves_symlinked_engine_assets():
    static = ROOT / "src" / "pymyio" / "static"
    if not (static / "lib" / "d3.min.js").resolve().is_file():
        pytest.skip("vendor/myIO submodule not initialized")

    script = textwrap.dedent(
        f"""
        import asyncio, importlib.util, json, sys

        spec = importlib.util.spec_from_file_location("gallery", {str(ROOT / "app" / "app.py")!r})
        gallery = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(gallery)

        async def get(path):
            sent = []
            async def receive():
                return {{"type": "http.request", "body": b"", "more_body": False}}
            async def send(message):
                sent.append(message)
            scope = {{
                "type": "http", "asgi": {{"version": "3.0"}}, "http_version": "1.1",
                "method": "GET", "scheme": "http", "path": path,
                "raw_path": path.encode(), "root_path": "", "query_string": b"",
                "headers": [], "server": ("testserver", 80), "client": ("test", 1),
            }}
            await gallery.app(scope, receive, send)
            start = next(m for m in sent if m["type"] == "http.response.start")
            body = b"".join(m.get("body", b"") for m in sent if m["type"] == "http.response.body")
            return start["status"], len(body)

        async def main():
            out = {{}}
            for asset in {ASSETS!r}:
                out[asset] = await get(gallery.PYMYIO_STATIC_URL + asset)
            out["../../../pyproject.toml"] = await get(gallery.PYMYIO_STATIC_URL + "../../../pyproject.toml")
            print(json.dumps(out))

        asyncio.run(main())
        """
    )
    proc = subprocess.run(
        [sys.executable, "-c", script],
        capture_output=True, text=True, cwd=ROOT, timeout=120,
    )
    assert proc.returncode == 0, proc.stderr
    results = json.loads(proc.stdout.strip().splitlines()[-1])

    for asset in ASSETS:
        status, size = results[asset]
        assert status == 200, f"/pymyio-static/{asset} returned {status}"
        assert size == (static / asset).resolve().stat().st_size, asset

    # Following symlinks must not open path traversal out of static/.
    assert results["../../../pyproject.toml"][0] == 404

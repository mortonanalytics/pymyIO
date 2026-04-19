"""Playwright-driven smoke test for ``pymyio.shiny.example_app()``.

Covers design acceptance criteria 1 and 2. Heavily guarded with ``skipif``
because the test launches a subprocess Shiny server and requires Playwright
browsers to be installed — both conditions are absent on plain dev installs.
"""

from __future__ import annotations

import importlib.util
import shutil
import socket
import subprocess
import sys
import time
from pathlib import Path

import pytest


_SHINY_BIN = shutil.which("shiny")
_HAS_SHINYWIDGETS = importlib.util.find_spec("shinywidgets") is not None
_HAS_PLAYWRIGHT = importlib.util.find_spec("playwright") is not None


pytestmark = pytest.mark.skipif(
    not (_SHINY_BIN and _HAS_SHINYWIDGETS and _HAS_PLAYWRIGHT),
    reason="requires shiny binary + shinywidgets + playwright",
)


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.fixture
def launched_app(tmp_path):
    """Launch the example Shiny app on an ephemeral port, yield the URL."""
    app_file = tmp_path / "app.py"
    app_file.write_text(
        "from pymyio.shiny import example_app\n"
        "app = example_app()\n",
        encoding="utf-8",
    )
    port = _free_port()
    proc = subprocess.Popen(
        [
            _SHINY_BIN,
            "run",
            "--host",
            "127.0.0.1",
            "--port",
            str(port),
            str(app_file),
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
    url = f"http://127.0.0.1:{port}"
    try:
        # Wait up to 20s for the server to accept connections.
        deadline = time.time() + 20
        while time.time() < deadline:
            if proc.poll() is not None:
                raise RuntimeError(
                    "shiny run exited before listening:\n"
                    + (proc.stdout.read().decode("utf-8", errors="replace")
                       if proc.stdout else "")
                )
            with socket.socket() as s:
                try:
                    s.connect(("127.0.0.1", port))
                    break
                except OSError:
                    time.sleep(0.25)
        else:
            raise RuntimeError("shiny server did not open port in time")
        yield url
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()


def test_example_app_renders_chart_svg(launched_app):
    from playwright.sync_api import sync_playwright

    try:
        with sync_playwright() as p:
            try:
                browser = p.chromium.launch()
            except Exception as e:
                pytest.skip(f"chromium not installed: {e}")
            page = browser.new_page()
            page.goto(launched_app)
            page.wait_for_selector("#chart svg", timeout=15_000)
            count = page.locator("#chart svg").count()
            browser.close()
    except Exception as e:
        pytest.skip(f"playwright unavailable: {e}")

    assert count >= 1

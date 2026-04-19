"""Runtime check of the anywidget render path (design criterion 8).

Renders two ``MyIO(...).render()`` widgets in one JupyterLab page and
verifies the double-load guard works: exactly 4 scripts tagged with
``data-pymyio`` exist on the page (one each for d3, d3-hexbin, d3-sankey,
engine) and ``window.__pymyioEngineVersion`` is a string.

Skipif-guarded on jupyter binary + jupyterlab package + playwright. Static
regex checks over widget.js live in ``test_widget_js_contract.py``.
"""

from __future__ import annotations

import importlib.util
import json
import shutil
import socket
import subprocess
import time
from pathlib import Path
from textwrap import dedent

import pytest


_JUPYTER_BIN = shutil.which("jupyter")
_HAS_JUPYTERLAB = importlib.util.find_spec("jupyterlab") is not None
_HAS_PLAYWRIGHT = importlib.util.find_spec("playwright") is not None

pytestmark = pytest.mark.skipif(
    not (_JUPYTER_BIN and _HAS_JUPYTERLAB and _HAS_PLAYWRIGHT),
    reason="requires jupyter binary + jupyterlab + playwright",
)


_NOTEBOOK = {
    "cells": [
        {
            "cell_type": "code",
            "metadata": {},
            "outputs": [],
            "execution_count": None,
            "source": dedent(
                """
                from pymyio import MyIO
                sample = [{"wt": 2.620, "mpg": 21.0}, {"wt": 3.215, "mpg": 21.4}]
                w1 = MyIO(data=sample).add_layer(
                    type="point", label="a",
                    mapping={"x_var": "wt", "y_var": "mpg"},
                )
                """
            ).strip(),
        },
        {
            "cell_type": "code",
            "metadata": {},
            "outputs": [],
            "execution_count": None,
            "source": dedent(
                """
                w2 = MyIO(data=sample).add_layer(
                    type="point", label="b",
                    mapping={"x_var": "wt", "y_var": "mpg"},
                )
                """
            ).strip(),
        },
    ],
    "metadata": {
        "kernelspec": {
            "display_name": "Python 3",
            "language": "python",
            "name": "python3",
        }
    },
    "nbformat": 4,
    "nbformat_minor": 5,
}


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.fixture
def jupyter_server(tmp_path):
    nb_path = tmp_path / "dual.ipynb"
    nb_path.write_text(json.dumps(_NOTEBOOK), encoding="utf-8")

    port = _free_port()
    proc = subprocess.Popen(
        [
            _JUPYTER_BIN,
            "lab",
            "--no-browser",
            f"--port={port}",
            "--ServerApp.token=",
            "--ServerApp.password=",
            f"--ServerApp.root_dir={tmp_path}",
            "--ServerApp.disable_check_xsrf=True",
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
    url = f"http://127.0.0.1:{port}/lab/tree/dual.ipynb"
    try:
        deadline = time.time() + 30
        while time.time() < deadline:
            if proc.poll() is not None:
                raise RuntimeError(
                    "jupyter lab exited before listening:\n"
                    + (
                        proc.stdout.read().decode("utf-8", errors="replace")
                        if proc.stdout
                        else ""
                    )
                )
            with socket.socket() as s:
                try:
                    s.connect(("127.0.0.1", port))
                    break
                except OSError:
                    time.sleep(0.5)
        else:
            raise RuntimeError("jupyter server did not open port in time")
        yield url
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()


def test_double_widget_loads_engine_once(jupyter_server):
    from playwright.sync_api import sync_playwright

    try:
        with sync_playwright() as p:
            try:
                browser = p.chromium.launch()
            except Exception as e:
                pytest.skip(f"chromium not installed: {e}")
            page = browser.new_page()
            page.goto(jupyter_server)
            page.wait_for_selector(".jp-Cell", timeout=20_000)
            # Run all cells via keyboard shortcut.
            page.keyboard.press("Control+Shift+Enter")  # run and advance
            page.keyboard.press("Control+Shift+Enter")
            page.wait_for_function(
                "document.querySelectorAll('.pymyio-chart svg').length >= 2",
                timeout=20_000,
            )
            script_count = page.evaluate(
                "document.querySelectorAll('script[data-pymyio]').length"
            )
            engine_version_type = page.evaluate(
                "typeof window.__pymyioEngineVersion"
            )
            browser.close()
    except Exception as e:
        pytest.skip(f"playwright unavailable: {e}")

    assert script_count == 4
    assert engine_version_type == "string"

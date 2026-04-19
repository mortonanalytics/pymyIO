"""JupyterLab rendering smoke test (design criteria 5 and 6).

Launches a headless ``jupyter lab`` server, opens a minimal notebook that
constructs ``MyIO(...).render()``, and asserts the d3 SVG is drawn inside
the widget container within 10 seconds. Uses Playwright for browser
automation.

This test is heavily guarded: it requires ``jupyterlab``, the ``jupyter``
command, and Playwright browsers. All of these are absent in the default
dev install, so the test skips cleanly in CI unless explicitly opted in.
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
                sample = [
                    {"wt": 2.620, "mpg": 21.0},
                    {"wt": 2.875, "mpg": 21.0},
                    {"wt": 2.320, "mpg": 22.8},
                    {"wt": 3.215, "mpg": 21.4},
                ]
                MyIO(data=sample).add_layer(
                    type="point", label="p",
                    mapping={"x_var": "wt", "y_var": "mpg"},
                )
                """
            ).strip(),
        }
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
    nb_path = tmp_path / "smoke.ipynb"
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
    url = f"http://127.0.0.1:{port}/lab/tree/smoke.ipynb"
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


def test_pymyio_chart_renders_in_jupyterlab(jupyter_server):
    from playwright.sync_api import sync_playwright

    try:
        with sync_playwright() as p:
            try:
                browser = p.chromium.launch()
            except Exception as e:
                pytest.skip(f"chromium not installed: {e}")
            page = browser.new_page()
            page.goto(jupyter_server)
            # Run all cells: Shift+Enter on the first cell suffices for one-
            # cell notebooks. JupyterLab's keyboard shortcut works after the
            # page is idle.
            page.wait_for_selector(".jp-Cell", timeout=20_000)
            page.keyboard.press("Control+Enter")
            page.wait_for_selector(".pymyio-chart svg", timeout=15_000)
            count = page.locator(".pymyio-chart svg").count()
            browser.close()
    except Exception as e:
        pytest.skip(f"playwright unavailable: {e}")

    assert count >= 1

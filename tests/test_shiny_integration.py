"""Unit tests for ``pymyio.shiny`` — aliases, version gate, helper callables.

Covers design acceptance criteria 3 and 4 (ImportError paths).
"""

from __future__ import annotations

import importlib
import sys

import pytest


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
    for name in ("reactive_brush", "reactive_annotated", "reactive_rollover"):
        assert callable(getattr(mod, name))


def test_example_app_is_callable():
    mod = _reimport_pymyio_shiny()
    assert callable(mod.example_app)


def test_too_old_shinywidgets_raises(monkeypatch):
    # Criterion 3 — floor verified at 0.8.0 per Devil's Advocate §2.
    from importlib import metadata as md

    orig = md.version

    def fake(name):
        if name == "shinywidgets":
            return "0.5.0"
        return orig(name)

    monkeypatch.setattr(md, "version", fake)
    for k in [m for m in sys.modules if m.startswith("pymyio.shiny")]:
        del sys.modules[k]
    with pytest.raises(ImportError, match=r"0\.8\.0.*pip install"):
        importlib.import_module("pymyio.shiny")


def test_missing_shinywidgets_raises(monkeypatch):
    # Criterion 4.
    from importlib import metadata as md

    orig = md.version

    def fake(name):
        if name == "shinywidgets":
            raise md.PackageNotFoundError(name)
        return orig(name)

    monkeypatch.setattr(md, "version", fake)
    for k in [m for m in sys.modules if m.startswith("pymyio.shiny")]:
        del sys.modules[k]
    with pytest.raises(ImportError, match=r"pymyio\[shiny\]"):
        importlib.import_module("pymyio.shiny")

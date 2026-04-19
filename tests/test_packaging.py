"""Packaging-floor regression test (design criterion 14 companion).

Asserts the runtime environment's ``anywidget`` version satisfies the pin
declared in ``pyproject.toml``. If a pre-0.10.0 build of ``anywidget`` is
installed alongside this pymyio, the install is misconfigured.
"""

from __future__ import annotations

from importlib import metadata as md


def _ver_tuple(s: str) -> tuple:
    return tuple(int(x) for x in s.split(".")[:3] if x.isdigit())


def test_anywidget_version_meets_floor():
    ver = md.version("anywidget")
    assert _ver_tuple(ver) >= (0, 10, 0), (
        f"anywidget {ver} is below the pymyio's anywidget pin of >=0.10.0"
    )
    assert _ver_tuple(ver) < (0, 11, 0), (
        f"anywidget {ver} exceeds the pymyio's anywidget pin upper bound <0.11"
    )


def test_ipywidgets_is_installed_and_recent():
    ver = md.version("ipywidgets")
    assert _ver_tuple(ver) >= (8, 0, 0), (
        f"ipywidgets {ver} below the pymyio's ipywidgets floor of >=8.0"
    )


def test_traitlets_is_installed():
    ver = md.version("traitlets")
    assert _ver_tuple(ver) >= (5, 9, 0)

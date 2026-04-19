"""Regression guard: importing shinywidgets installs a process-wide
Widget._widget_construction_callback that raises RuntimeError on every
subsequent widget construction. `pymyio/__init__.py` must therefore NOT
import `pymyio.shiny` directly or transitively.

Design doc reference: acceptance criterion 14b.
"""

import importlib
import subprocess
import sys
import textwrap

import pytest


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
    # CRITICAL: the shinywidgets Widget._widget_construction_callback side
    # effect is process-wide. Run in a subprocess so no prior import in the
    # test session has already armed the callback. The _base_url trait
    # assertion rides the same subprocess to avoid the same hazard when
    # another test file in the same pytest session has already triggered
    # the shinywidgets import.
    script = textwrap.dedent(
        """
        import sys
        assert "shinywidgets" not in sys.modules
        import pymyio
        assert "pymyio.shiny" not in sys.modules
        w = (pymyio.MyIO(data=[{"x": 1, "y": 2}])
                .add_layer(type="point", label="p",
                           mapping={"x_var": "x", "y_var": "y"})
                .render())
        assert w.config["layers"][0]["type"] == "point"
        assert w._base_url == ""
        assert w.traits()["_base_url"].metadata.get("sync") is True
        """
    )
    r = subprocess.run(
        [sys.executable, "-c", script],
        capture_output=True,
        text=True,
    )
    assert r.returncode == 0, f"stderr:\n{r.stderr}"


def test_base_url_trait_declared_on_widget_class():
    # Inspect the class, not an instance — this must work even when the
    # shinywidgets global callback is armed by another test in the session.
    from pymyio.widget import MyIOWidget

    trait = MyIOWidget.class_traits().get("_base_url")
    assert trait is not None
    assert trait.metadata.get("sync") is True
    assert trait.default_value == ""

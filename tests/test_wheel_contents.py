"""Freeze test for the Hatch wheel ``force-include`` block.

The block materializes engine assets and the generated schema from the
vendored git submodule into the built wheel. Removing or renaming an entry
breaks installs for every downstream user — catch that mechanically.

Design doc reference: Slice 5; contract §"force-include block".
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest


if sys.version_info >= (3, 11):
    import tomllib
else:  # pragma: no cover — Python 3.9/3.10
    import tomli as tomllib  # type: ignore[no-redef]


_PYPROJECT = Path(__file__).resolve().parent.parent / "pyproject.toml"


EXPECTED_FORCE_INCLUDE = {
    "vendor/myIO/inst/htmlwidgets/myIO/myIOapi.js": "pymyio/static/myIOapi.js",
    "vendor/myIO/inst/htmlwidgets/myIO/style.css": "pymyio/static/style.css",
    "vendor/myIO/inst/htmlwidgets/lib/d3.min.js": "pymyio/static/lib/d3.min.js",
    "vendor/myIO/inst/htmlwidgets/lib/d3-hexbin.js": "pymyio/static/lib/d3-hexbin.js",
    "vendor/myIO/inst/htmlwidgets/lib/d3-sankey.min.js": "pymyio/static/lib/d3-sankey.min.js",
    "vendor/myIO/inst/myio-schema.json": "pymyio/myio-schema.json",
}


@pytest.fixture(scope="module")
def pyproject() -> dict:
    return tomllib.loads(_PYPROJECT.read_text(encoding="utf-8"))


def test_force_include_block_is_present(pyproject: dict):
    tool = pyproject.get("tool", {})
    hatch = tool.get("hatch", {})
    build = hatch.get("build", {})
    targets = build.get("targets", {})
    wheel = targets.get("wheel", {})
    assert "force-include" in wheel


def test_force_include_maps_all_frozen_assets(pyproject: dict):
    actual = (
        pyproject["tool"]["hatch"]["build"]["targets"]["wheel"]["force-include"]
    )
    for src, dst in EXPECTED_FORCE_INCLUDE.items():
        assert src in actual, f"missing force-include source: {src!r}"
        assert actual[src] == dst, (
            f"force-include[{src!r}] = {actual[src]!r} (expected {dst!r})"
        )


def test_wheel_static_files_exist_on_disk():
    static = Path(__file__).resolve().parent.parent / "src" / "pymyio" / "static"
    assert (static / "myIOapi.js").is_file()
    assert (static / "style.css").is_file()
    assert (static / "widget.js").is_file()  # not force-included — lives in tree
    assert (static / "lib" / "d3.min.js").is_file()
    assert (static / "lib" / "d3-hexbin.js").is_file()
    assert (static / "lib" / "d3-sankey.min.js").is_file()


def test_version_is_dynamic_and_resolves(pyproject: dict):
    import pymyio

    assert "version" in pyproject["project"].get("dynamic", []), (
        "pyproject must declare version as dynamic for hatch-vcs to manage it"
    )
    assert "version" not in pyproject["project"], (
        "pyproject must not have a static version field when using hatch-vcs"
    )
    assert isinstance(pymyio.__version__, str) and pymyio.__version__

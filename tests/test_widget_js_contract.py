"""Static contract tests for widget.js.

Asserts the shape of the anywidget entry point without running JS. If a
regression edits widget.js in a way that drops the data-pymyio-role tags,
base-URL traitlet read, double-load guard, or the frozen event wiring, one
of these regex assertions will fail.

Design doc reference: Slice 2 acceptance criterion 8; plan Phase 2.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest


WIDGET_JS = (
    Path(__file__).resolve().parent.parent
    / "src"
    / "pymyio"
    / "static"
    / "widget.js"
)


@pytest.fixture(scope="module")
def source() -> str:
    assert WIDGET_JS.is_file(), f"widget.js not found at {WIDGET_JS}"
    return WIDGET_JS.read_text(encoding="utf-8")


def test_role_string_d3_core_present(source: str):
    assert '"d3-core"' in source


def test_role_string_d3_hexbin_present(source: str):
    assert '"d3-hexbin"' in source


def test_role_string_d3_sankey_present(source: str):
    assert '"d3-sankey"' in source


def test_role_string_engine_present(source: str):
    # The literal "engine" passed as a role to injectScript. Match the
    # specific form `"engine"` to avoid false positives on the word "engine"
    # in comments / identifiers (enginePromise).
    assert re.search(r'injectScript\([^)]*"engine"\)', source)


def test_engine_version_global_set(source: str):
    assert "__pymyioEngineVersion" in source


def test_base_url_traitlet_read(source: str):
    assert re.search(r'model\.get\("_base_url"\)', source)


def test_inject_script_call_count_exact(source: str):
    # Exactly 5 occurrences of `injectScript(`: one function definition plus
    # four call sites inside loadEngine. Drop one role → drop from 5 to 4 →
    # this test fails loudly.
    assert source.count("injectScript(") == 5


def test_no_cdn_mode(source: str):
    assert "cdn.jsdelivr" not in source
    assert "unpkg.com" not in source


def test_myiochart_constructor_contract_frozen(source: str):
    # Frozen contract per design §Slice 5. Exactly one constructor call site.
    assert source.count("new window.myIOchart") == 1


def test_chart_event_wire_ups_exactly_four(source: str):
    # chart.on?.("error"|"brushed"|"annotated"|"rollover", ...) — four total.
    assert source.count("chart.on?.(") == 4


@pytest.mark.parametrize(
    "event",
    ["error", "brushed", "annotated", "rollover"],
)
def test_each_chart_event_wired(source: str, event: str):
    # Each event name appears as the first argument of an `.on?.(...)` call.
    pattern = rf'chart\.on\?\.\("{event}"'
    assert re.search(pattern, source), f"missing chart.on?.({event!r}, ...)"


def test_double_load_guard_present(source: str):
    # The guard must short-circuit when window.myIOchart is already loaded.
    assert re.search(
        r'typeof\s+window\.myIOchart\s*===\s*"function"',
        source,
    )

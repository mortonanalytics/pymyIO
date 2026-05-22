"""Regression guard for the public API surface (``pymyio.__all__``).

0.1.0 symbols must continue to exist in 0.2.0. The release may ADD symbols
(``to_standalone_html``, ``MyIOStaticWarning``) but must not REMOVE any.

Design doc reference: Slice 5 backward-compat freeze.
"""

from __future__ import annotations

import pymyio


_V_0_1_0 = {
    "MyIO",
    "MyIOWidget",
    "ALLOWED_TYPES",
    "VALID_COMBINATIONS",
    "COMPATIBILITY_GROUPS",
    "OKABE_ITO_PALETTE",
    "link_charts",
}

_V_0_2_0_ADDITIONS = {
    "MyIOStaticWarning",
    "to_standalone_html",
}

_PR_50_ADDITIONS = {
    "ERROR_CODES",
    "load_schema",
    "list_chart_types",
    "get_chart_schema",
    "validate_spec",
    "list_functions",
    "get_function_signature",
    "validate_call",
    "myio_list_chart_types",
    "myio_chart_schema",
    "myio_validate_spec",
    "myio_list_functions",
    "myio_function_signature",
    "myio_validate_call",
}


def test_all_contains_every_v0_1_0_symbol():
    missing = _V_0_1_0 - set(pymyio.__all__)
    assert not missing, f"0.1.0 symbols dropped from __all__: {sorted(missing)}"


def test_every_symbol_in_all_is_actually_importable():
    for name in pymyio.__all__:
        assert hasattr(pymyio, name), f"{name!r} listed in __all__ but not defined"


def test_all_is_exactly_the_expected_set():
    # Explicit snapshot — if this assert fires, the PR added or removed a
    # public symbol; update _V_0_2_0_ADDITIONS (and consider whether a
    # deprecation cycle is needed).
    assert set(pymyio.__all__) == _V_0_1_0 | _V_0_2_0_ADDITIONS | _PR_50_ADDITIONS


def test_version_string_is_well_formed():
    # The exact version string is not asserted here — releases are cut by
    # /release / /pr, not by implementation PRs. Just confirm it exists
    # and matches a dotted form.
    import re

    assert isinstance(pymyio.__version__, str)
    assert re.match(r"^\d+\.\d+\.\d+", pymyio.__version__)


def test_my_io_static_warning_is_user_warning_subclass():
    assert issubclass(pymyio.MyIOStaticWarning, UserWarning)

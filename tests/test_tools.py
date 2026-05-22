from __future__ import annotations

import json
from pathlib import Path

from pymyio import (
    ALLOWED_TYPES,
    COMPATIBILITY_GROUPS,
    ERROR_CODES,
    VALID_COMBINATIONS,
    get_chart_schema,
    get_function_signature,
    list_chart_types,
    list_functions,
    load_schema,
    validate_call,
    validate_spec,
)


CONFORMANCE = (
    Path(__file__).resolve().parent.parent
    / "vendor"
    / "myIO"
    / "tests"
    / "fixtures"
    / "validate-conformance.json"
)


def _as_tuple(value):
    if isinstance(value, list):
        return tuple(value)
    return (value,)


def test_schema_surface_matches_chart_contract_constants():
    schema = load_schema()
    assert list(schema["error_codes"]) == list(ERROR_CODES)
    assert list(schema["types"]) == ALLOWED_TYPES
    assert {
        chart_type: type_schema["group"]
        for chart_type, type_schema in schema["types"].items()
    } == COMPATIBILITY_GROUPS
    for chart_type, transforms in VALID_COMBINATIONS.items():
        assert _as_tuple(schema["types"][chart_type]["valid_transforms"]) == transforms


def test_tool_schema_lookup_surface():
    assert "point" in list_chart_types()
    assert "fan" in list_chart_types()
    assert get_chart_schema("boxplot")["kind"] == "composite"
    assert "setAxisFormat" in list_functions()
    assert get_function_signature("setAxisFormat") == [
        "myIO", "xAxis", "yAxis", "toolTip", "xLabel", "yLabel",
    ]


def test_validator_matches_shared_conformance_corpus():
    corpus = json.loads(CONFORMANCE.read_text(encoding="utf-8"))
    for item in corpus:
        if item["tool"] == "validate_spec":
            result = validate_spec(item["input"])
        elif item["tool"] == "validate_call":
            result = validate_call(item["input"]["fn"], item["input"].get("args"))
        else:
            raise AssertionError(f"unknown corpus tool: {item['tool']}")

        assert result["valid"] is item["valid"], item["name"]
        assert [error["code"] for error in result["errors"]] == item["error_codes"]
        suggestions = [error.get("suggestion", "") for error in result["errors"]]
        for target in item["suggestion_targets"]:
            assert target in suggestions, item["name"]


def test_validate_spec_optional_columns_argument_overrides_spec_columns():
    result = validate_spec(
        {
            "type": "point",
            "mapping": {"x_var": "wt", "y_var": "mpg"},
            "columns": {"wt": "numeric", "mpg": "character"},
        },
        columns={"wt": "numeric", "mpg": "numeric"},
    )
    assert result == {"valid": True, "errors": []}

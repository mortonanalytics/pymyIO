from __future__ import annotations

import json
from pathlib import Path

import pytest

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


_VENDOR = Path(__file__).resolve().parent.parent / "vendor" / "myIO"
CONFORMANCE = _VENDOR / "tests" / "fixtures" / "validate-conformance.json"
SCHEMA_INST = _VENDOR / "inst" / "myio-schema.json"
SCHEMA_MCP = _VENDOR / "mcp" / "myio-schema.json"

# List-typed schema fields that issue #52 collapsed to scalar strings for
# single-element lists. Iterating a scalar string yields one bogus error per
# character, so each of these must stay a JSON array.
_LIST_FIELDS = ("required_mappings", "numeric_fields", "valid_transforms")


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


@pytest.mark.parametrize("chart_type", list_chart_types())
def test_every_chart_type_accepts_its_minimal_spec(chart_type):
    """Mirror upstream tests/js/mcp-validate.test.js: a minimal valid spec for
    every chart type validates cleanly. Guards issue #52 — a required_mappings
    field serialized as a scalar string would split into characters and report
    one bogus MISSING_MAPPING per letter."""
    schema = get_chart_schema(chart_type)
    assert all(isinstance(f, str) for f in schema["required_mappings"])
    mapping = {field: field for field in schema["required_mappings"]}
    transforms = schema["valid_transforms"]
    transform = transforms[0] if transforms else "identity"

    result = validate_spec({"type": chart_type, "mapping": mapping, "transform": transform})

    assert result == {"valid": True, "errors": []}


def test_issue_52_histogram_minimal_does_not_split_string():
    result = validate_spec(
        {"type": "histogram", "mapping": {"value": "mag"}, "transform": "identity"}
    )
    assert result == {"valid": True, "errors": []}


def test_issue_52_genuinely_missing_single_mapping_reports_one_error():
    result = validate_spec({"type": "histogram", "mapping": {}, "transform": "identity"})
    assert result["valid"] is False
    missing = [e for e in result["errors"] if e["code"] == "MISSING_MAPPING"]
    assert len(missing) == 1
    assert missing[0]["field"] == "value"


def test_schema_list_fields_are_arrays_not_scalars():
    """Lock the issue #52 fix: every list-typed field is a JSON array for every
    chart type — never a scalar string, even for single-element lists."""
    schema = load_schema()
    for chart_type, type_schema in schema["types"].items():
        for field in _LIST_FIELDS:
            if field in type_schema:
                assert isinstance(type_schema[field], list), (
                    f"{chart_type}.{field} must be a JSON array, got "
                    f"{type(type_schema[field]).__name__}"
                )
                assert all(isinstance(v, str) for v in type_schema[field])
    for fn, args in schema["function_signatures"].items():
        assert isinstance(args, list), f"function_signatures.{fn} must be a JSON array"


def test_schema_byte_matches_canonical_mcp_copy():
    """Schema drift gate: pymyIO loads the canonical contract and the two
    canonical upstream copies (inst/ and mcp/) are byte-identical, so a
    regeneration that updates only one surface fails CI."""
    inst_bytes = SCHEMA_INST.read_bytes()
    mcp_bytes = SCHEMA_MCP.read_bytes()
    assert inst_bytes == mcp_bytes, "inst/ and mcp/ schema copies have drifted"
    assert load_schema() == json.loads(inst_bytes.decode("utf-8"))

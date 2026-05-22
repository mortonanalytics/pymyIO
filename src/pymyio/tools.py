"""Schema-backed myIO helper tools for LLM tool calling."""

from __future__ import annotations

import json
from importlib import resources
from pathlib import Path
from typing import Any, Mapping, Optional

ERROR_CODES = (
    "UNKNOWN_TYPE",
    "MISSING_MAPPING",
    "UNKNOWN_MAPPING_KEY",
    "INVALID_TRANSFORM",
    "MISSING_COLUMN",
    "NON_NUMERIC_COLUMN",
    "UNKNOWN_FUNCTION",
    "UNKNOWN_ARGUMENT",
)


def _as_list(value: Any) -> list:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    if isinstance(value, tuple):
        return list(value)
    return [value]


def load_schema() -> dict:
    """Load the generated myIO schema bundled with the package or submodule."""
    try:
        resource = resources.files("pymyio").joinpath("myio-schema.json")
        if resource.is_file():
            return json.loads(resource.read_text(encoding="utf-8"))
    except (FileNotFoundError, ModuleNotFoundError):
        pass

    repo_root = Path(__file__).resolve().parents[2]
    schema_path = repo_root / "vendor" / "myIO" / "inst" / "myio-schema.json"
    return json.loads(schema_path.read_text(encoding="utf-8"))


def _levenshtein(value: Any, choices: list[str]) -> Optional[str]:
    if not choices:
        return None
    normalized = str(value or "").lower()
    if "value" in normalized and "y_var" in choices:
        return "y_var"
    if "column" in normalized and "x_var" in choices:
        return "x_var"
    if "group" in normalized and "group" in choices:
        return "group"
    for choice in choices:
        if choice.lower().startswith(normalized):
            return choice
    return min(choices, key=lambda choice: _edit_distance(str(value or ""), choice))


def _edit_distance(left: str, right: str) -> int:
    previous = list(range(len(right) + 1))
    for i, left_char in enumerate(left, start=1):
        current = [i]
        for j, right_char in enumerate(right, start=1):
            current.append(min(
                previous[j] + 1,
                current[j - 1] + 1,
                previous[j - 1] + (left_char != right_char),
            ))
        previous = current
    return previous[-1]


def _tool_error(
    code: str,
    field: str,
    message: str,
    suggestion: Optional[str] = None,
) -> dict:
    result = {"code": code, "field": field, "message": message}
    if suggestion is not None:
        result["suggestion"] = suggestion
    return result


def _is_numeric_column(kind: Any) -> bool:
    normalized = " ".join(str(v) for v in _as_list(kind)).lower()
    return any(
        token in normalized
        for token in ("numeric", "integer", "double", "number", "float", "int", "real")
    )


def _normalize_columns(columns: Any) -> Optional[dict]:
    if columns is None:
        return None
    if isinstance(columns, Mapping):
        return dict(columns)
    if isinstance(columns, (list, tuple)):
        out = {}
        for item in columns:
            if isinstance(item, str):
                out[item] = "unknown"
            elif isinstance(item, Mapping) and "name" in item:
                out[str(item["name"])] = str(item.get("type", "unknown"))
        return out

    names = getattr(columns, "columns", None)
    if names is not None:
        return {str(name): str(dtype) for name, dtype in zip(names, getattr(columns, "dtypes", []))}
    return None


def _allowed_mapping_keys(type_schema: Mapping[str, Any]) -> list[str]:
    keys = set(_as_list(type_schema.get("required_mappings")))
    data_contract = type_schema.get("data_contract") or {}
    keys.update(data_contract.keys())
    keys.update(("group", "label", "low_x", "high_x", "total"))
    return sorted(keys)


def list_chart_types() -> list[str]:
    return list(load_schema()["types"].keys())


def get_chart_schema(type: Optional[str] = None) -> Any:
    types = load_schema()["types"]
    if type is None:
        return types
    return types.get(type)


def validate_spec(spec: Mapping[str, Any], columns: Any = None) -> dict:
    schema = load_schema()
    errors = []
    chart_type = spec.get("type")
    type_schema = schema["types"].get(chart_type)
    if type_schema is None:
        return {
            "valid": False,
            "errors": [_tool_error(
                "UNKNOWN_TYPE",
                "type",
                f"Unknown chart type '{chart_type or ''}'.",
                _levenshtein(chart_type or "", list(schema["types"].keys())),
            )],
        }

    mapping = spec.get("mapping") or {}
    transform = spec.get("transform") or "identity"
    valid_transforms = _as_list(type_schema.get("valid_transforms"))
    if transform not in valid_transforms:
        errors.append(_tool_error(
            "INVALID_TRANSFORM",
            "transform",
            f"Transform '{transform}' is not valid for chart type '{chart_type}'.",
            valid_transforms[0] if valid_transforms else None,
        ))

    allowed_keys = _allowed_mapping_keys(type_schema)
    for field in _as_list(type_schema.get("required_mappings")):
        if field not in mapping:
            errors.append(_tool_error(
                "MISSING_MAPPING",
                field,
                f"Missing required mapping '{field}' for chart type '{chart_type}'.",
            ))

    for field in mapping:
        if field not in allowed_keys:
            errors.append(_tool_error(
                "UNKNOWN_MAPPING_KEY",
                field,
                f"Unknown mapping key '{field}' for chart type '{chart_type}'.",
                _levenshtein(field, allowed_keys),
            ))

    column_map = _normalize_columns(columns if columns is not None else spec.get("columns"))
    if column_map is not None:
        for field, column_name in mapping.items():
            if isinstance(column_name, str) and column_name not in column_map:
                errors.append(_tool_error(
                    "MISSING_COLUMN",
                    field,
                    f"Mapped column '{column_name}' for '{field}' is not present in columns.",
                    _levenshtein(column_name, list(column_map.keys())),
                ))

        for field in _as_list(type_schema.get("numeric_fields")):
            column_name = mapping.get(field)
            if (
                isinstance(column_name, str)
                and column_name in column_map
                and not _is_numeric_column(column_map[column_name])
            ):
                errors.append(_tool_error(
                    "NON_NUMERIC_COLUMN",
                    field,
                    f"Mapped column '{column_name}' for '{field}' must be numeric.",
                ))

    return {"valid": len(errors) == 0, "errors": errors}


def list_functions() -> list[str]:
    return list(load_schema()["function_signatures"].keys())


def get_function_signature(fn: Optional[str] = None) -> Any:
    signatures = load_schema()["function_signatures"]
    if fn is None:
        return signatures
    return signatures.get(fn)


def validate_call(fn: str, args: Optional[Mapping[str, Any]] = None) -> dict:
    schema = load_schema()
    signatures = schema["function_signatures"]
    signature = signatures.get(fn)
    if signature is None:
        return {
            "valid": False,
            "errors": [_tool_error(
                "UNKNOWN_FUNCTION",
                "fn",
                f"Unknown function '{fn or ''}'.",
                _levenshtein(fn or "", list(signatures.keys())),
            )],
        }

    errors = []
    for arg in (args or {}):
        if arg not in signature and arg != "...":
            errors.append(_tool_error(
                "UNKNOWN_ARGUMENT",
                arg,
                f"Unknown argument '{arg}' for function '{fn}'.",
                _levenshtein(arg, list(signature)),
            ))
    return {"valid": len(errors) == 0, "errors": errors}


myio_list_chart_types = list_chart_types
myio_chart_schema = get_chart_schema
myio_validate_spec = validate_spec
myio_list_functions = list_functions
myio_function_signature = get_function_signature
myio_validate_call = validate_call

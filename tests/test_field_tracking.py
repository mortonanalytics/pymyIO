"""Field tracking layer — mirrors upstream tests/testthat/test-field-tracking.R."""

import json
import math

import pandas as pd
import pytest

import pymyio
from pymyio import MyIO

MAPPING = {"x_var": "east", "y_var": "north", "time": "seconds",
           "entity": "athlete", "team": "club"}


def _data(athletes=("a", "b")):
    return pd.DataFrame({"east": [1.0, 2.0], "north": [2.0, 3.0], "seconds": [0.0, 0.2],
                         "athlete": list(athletes), "club": ["home", "away"]})


def _field_options(**options):
    chart = MyIO(_data()).add_layer("field", label="Match", mapping=MAPPING, options=options)
    return chart.to_config()["layers"][0]["options"]


def test_field_is_a_listed_chart_type():
    assert "field" in pymyio.list_chart_types()
    assert pymyio.get_chart_schema("field")["required_mappings"] == [
        "x_var", "y_var", "time", "entity"]


def test_field_mappings_serialize_through_the_layer_api():
    chart = MyIO(_data(("a", "a"))).add_layer(
        "field", label="Match", mapping=MAPPING, options={"pitchLength": 105, "pitchWidth": 68})
    layer = chart.to_config()["layers"][0]
    assert layer["type"] == "field"
    assert layer["mapping"]["entity"] == "athlete"
    assert len(layer["data"]) == 2
    with pytest.raises(ValueError, match="time, entity"):
        MyIO(_data()).add_layer("field", label="Match",
                                mapping={"x_var": "east", "y_var": "north"})
    with pytest.raises(ValueError, match="existing column"):
        MyIO(_data()).add_layer("field", label="Match", mapping={**MAPPING, "time": "missing"})
    with pytest.raises(ValueError, match="team, not group"):
        MyIO(_data()).add_layer("field", label="Match", mapping={**MAPPING, "group": "club"})
    with pytest.raises(ValueError, match="must be numeric"):
        MyIO(_data()).add_layer("field", label="Match", mapping={**MAPPING, "x_var": "club"})
    with pytest.raises(ValueError, match="incompatible"):
        chart.add_layer("point", label="Points", mapping={"x_var": "east", "y_var": "north"})


def test_missing_positions_serialize_as_null_and_are_not_filled():
    data = pd.DataFrame({"east": [1.0, math.nan, 3.0], "north": [2.0, math.nan, 4.0],
                         "seconds": [0.0, 0.2, 0.4], "athlete": ["a"] * 3,
                         "club": ["home"] * 3})
    layer = MyIO(data).add_layer(
        "field", label="Match", mapping=MAPPING).to_config()["layers"][0]
    assert len(layer["data"]) == 3
    assert layer["data"][1]["east"] is None and layer["data"][1]["north"] is None
    json.dumps(layer["data"], allow_nan=False)


def test_field_overlay_options_are_validated_and_serialize_as_arrays():
    options = _field_options(overlays={"shape": True, "separation": False}, minPlayers=3,
                             excludeEntities="a", metricWindow=(0, 0.2))
    assert options["overlays"] == {"shape": True, "separation": False}
    assert options["minPlayers"] == 3 and isinstance(options["minPlayers"], int)
    assert options["excludeEntities"] == ["a"]
    assert options["metricWindow"] == [0.0, 0.2]
    assert _field_options(excludeEntities=[11, 25.0])["excludeEntities"] == ["11", "25"]
    assert "overlays" not in _field_options(pitchLength=105)
    bad = [
        ({"overlays": {"shape": "yes"}}, "overlays"),
        ({"overlays": {"pitchControl": True}}, "overlays"),
        ({"overlays": True}, "overlays"),
        ({"minPlayers": 1}, "minPlayers"),
        ({"minPlayers": 2.5}, "minPlayers"),
        ({"excludeEntities": ["a", None]}, "excludeEntities"),
        ({"metricWindow": (5, 1)}, "metricWindow"),
        ({"metricWindow": 3}, "metricWindow"),
        ({"metricWindow": (0, math.inf)}, "metricWindow"),
    ]
    for options, field in bad:
        with pytest.raises(ValueError, match=field):
            _field_options(**options)


def test_field_events_accept_a_data_frame_as_records():
    events = pd.DataFrame({"time": [0.0, 0.2], "type": pd.Categorical(["PASS", "SHOT"]),
                           "player": ["a", None]})
    options = _field_options(events=events)
    assert options["events"] == [{"time": 0.0, "type": "PASS", "player": "a"},
                                 {"time": 0.2, "type": "SHOT"}]
    assert '"events": [{"time": 0.0, "type": "PASS", "player": "a"}, ' \
           '{"time": 0.2, "type": "SHOT"}]' in json.dumps(options)

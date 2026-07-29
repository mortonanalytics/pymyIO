"""Tests for MyIO.add_keyframe — mirrors upstream tests/testthat/test_keyframes.R.

The R proxy helpers (setKeyframe/stepKeyframe) are Shiny-runtime custom
messages with no Python proxy surface (same precedent as myIOProxy /
setTransition) and are not ported.
"""

import pytest

from pymyio import MyIO


def _line_chart(data, transform="identity", options=None):
    return MyIO(data).add_layer(
        type="line", label="series",
        mapping={"x_var": "x", "y_var": "y"},
        transform=transform, options=options,
    )


def test_charts_without_keyframes_keep_the_existing_config_contract():
    chart = MyIO([{"x": 1, "y": 2}]).add_layer(
        type="point", label="cars", mapping={"x_var": "x", "y_var": "y"})
    assert "keyframes" not in chart.to_config()


def test_add_keyframe_serializes_a_transformed_single_layer_snapshot():
    first = [{"x": x, "y": y} for x, y in zip(range(1, 7), [2, 8, 3, 9, 4, 10])]
    second = [{"x": x, "y": y} for x, y in zip(range(1, 7), [10, 4, 9, 3, 8, 2])]
    chart = (
        _line_chart(first, transform="lttb", options={"threshold": 3})
        .add_keyframe(first, "Before")
        .add_keyframe(second, "After")
    )
    frames = chart.to_config()["keyframes"]
    assert [f["label"] for f in frames] == ["Before", "After"]
    assert len(frames[0]["layers"]) == 1
    assert frames[0]["layers"][0]["label"] == "series"
    assert len(frames[0]["layers"][0]["data"]) == 3  # lttb threshold applied
    assert all("_source_key" in row for row in frames[0]["layers"][0]["data"])


def test_multi_layer_keyframes_materialize_complete_snapshots():
    initial_a = [{"x": 1, "y": 1}, {"x": 2, "y": 2}]
    initial_b = [{"x": 1, "y": 3}, {"x": 2, "y": 4}]
    changed_a = [{"x": 1, "y": 9}, {"x": 2, "y": 8}, {"x": 3, "y": 7}]
    chart = (
        MyIO()
        .add_layer(type="line", label="a", data=initial_a,
                   mapping={"x_var": "x", "y_var": "y"})
        .add_layer(type="line", label="b", data=initial_b,
                   mapping={"x_var": "x", "y_var": "y"})
        .add_keyframe({"a": changed_a}, "Only A changes")
    )
    cfg = chart.to_config()
    frame = cfg["keyframes"][0]
    assert [snap["label"] for snap in frame["layers"]] == ["a", "b"]
    assert len(frame["layers"][0]["data"]) == 3
    assert frame["layers"][1]["data"] == cfg["layers"][1]["data"]


def test_omitted_layers_carry_forward_from_the_previous_keyframe():
    a1 = [{"x": 1, "y": 1}]
    a2 = [{"x": 1, "y": 5}]
    b1 = [{"x": 1, "y": 3}]
    chart = (
        MyIO()
        .add_layer(type="line", label="a", data=a1,
                   mapping={"x_var": "x", "y_var": "y"})
        .add_layer(type="line", label="b", data=b1,
                   mapping={"x_var": "x", "y_var": "y"})
        .add_keyframe({"a": a2}, "first")
        .add_keyframe({"b": [{"x": 1, "y": 7}]}, "second")
    )
    frames = chart.to_config()["keyframes"]
    # 'a' in frame 2 carries frame 1's serialized rows, not the layer's rows
    assert frames[1]["layers"][0]["data"] == frames[0]["layers"][0]["data"]
    assert frames[0]["layers"][0]["data"][0]["y"] == 5


def test_add_keyframe_rejects_ambiguous_and_malformed_inputs():
    empty = MyIO()
    with pytest.raises(ValueError, match="at least one layer"):
        empty.add_keyframe([{"x": 1}], "frame")

    one = MyIO([{"x": 1, "y": 2}]).add_layer(
        type="point", label="one", mapping={"x_var": "x", "y_var": "y"})
    with pytest.raises(ValueError, match="non-empty"):
        one.add_keyframe([{"x": 1}], "")
    with pytest.raises(ValueError, match="unknown layer"):
        one.add_keyframe({"missing": [{"x": 1}]}, "bad")
    with pytest.raises(ValueError, match="data frame"):
        one.add_keyframe({"one": 42}, "bad")

    one.add_keyframe([{"x": 1, "y": 2}], "same")
    with pytest.raises(ValueError, match="unique"):
        one.add_keyframe([{"x": 2, "y": 3}], "same")

    two = one.add_layer(type="point", label="two",
                        data=[{"x": 3, "y": 4}],
                        mapping={"x_var": "x", "y_var": "y"})
    with pytest.raises(ValueError, match="named list"):
        two.add_keyframe([{"x": 1, "y": 2}], "ambiguous")


def test_treemap_keyframes_keep_the_python_flat_row_serialization():
    # Divergence from R (which builds {name, children} server-side): the
    # Python builder ships flat rows for treemap layers, so keyframes do too.
    initial = [
        {"group": "A", "item": "one", "value": 2},
        {"group": "A", "item": "two", "value": 3},
        {"group": "B", "item": "three", "value": 4},
    ]
    changed = [{**row, "value": row["value"] * 2} for row in initial]
    chart = MyIO(initial).add_layer(
        type="treemap", label="tree",
        mapping={"level_1": "group", "level_2": "item", "y_var": "value"},
    ).add_keyframe(changed, "Changed")
    frame_data = chart.to_config()["keyframes"][0]["layers"][0]["data"]
    assert isinstance(frame_data, list)
    assert frame_data[0]["value"] == 4

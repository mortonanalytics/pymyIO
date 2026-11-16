"""raster, image and pointcloud layers, set_equal_aspect, and the new line and
point options (parity with myIO test_pointcloud.R / test_raster.R)."""

from __future__ import annotations

import base64

import numpy as np
import pytest

from pymyio import MyIO

# Tiny test-only fixtures.
CLOUD = [
    {"x": 0.0, "y": 1.0, "z": 0.0, "r": 10, "g": 0, "b": 5, "c": 2, "s": 0.02},
    {"x": 3.2, "y": 2.5, "z": 0.4, "r": 200, "g": 128, "b": 64, "c": 6, "s": 0.3},
    {"x": 7.5, "y": 4.0, "z": 2.1, "r": 255, "g": 30, "b": 90, "c": 11, "s": 4.0},
    {"x": None, "y": 4.0, "z": 2.1, "r": 1, "g": 1, "b": 1, "c": 1, "s": 1.0},
]
GRID = [{"x": float(x), "y": float(y), "v": float(x * y)} for x in range(3) for y in range(2)]
CLOUD_MAPPING = {"x_var": "x", "y_var": "y", "z_var": "z", "red": "r", "green": "g",
                 "blue": "b", "class": "c", "sigma": "s"}


def decode(b64: str, dtype: str) -> np.ndarray:
    return np.frombuffer(base64.b64decode(b64), dtype)


def test_pointcloud_packs_points_into_options_not_rows():
    chart = MyIO().add_layer(type="pointcloud", label="cloud", data=CLOUD, mapping=CLOUD_MAPPING,
                             options={"color": "rgb"})
    layer = chart.config["layers"][0]
    assert layer["data"] == []
    o = layer["options"]
    assert o["color"] == "rgb"
    assert o["n"] == 3  # the point with no x is dropped
    assert o["bbox"] == [0.0, 7.5, 1.0, 4.0, 0.0, 2.1]
    pos = decode(o["positions"], "<u2").reshape(-1, 3)
    np.testing.assert_allclose(pos[:, 0] / 65535 * 7.5, [0, 3.2, 7.5], atol=1e-3)
    assert pos[2].tolist() == [65535, 65535, 65535]
    assert decode(o["rgb"], "u1").reshape(-1, 3).tolist() == [[10, 0, 5], [200, 128, 64], [255, 30, 90]]
    assert decode(o["cls"], "u1").tolist() == [2, 6, 11]
    sigma = 10 ** (decode(o["sigma"], "u1") / 255 * 4 - 3)
    np.testing.assert_allclose(sigma, [0.02, 0.3, 4.0], rtol=0.04)


def test_pointcloud_validation_and_standalone_group():
    with pytest.raises(ValueError, match="Missing required mapping.*z_var"):
        MyIO().add_layer(type="pointcloud", label="c", data=CLOUD, mapping={"x_var": "x", "y_var": "y"})
    with pytest.raises(ValueError, match="Column 'nope' not found"):
        MyIO().add_layer(type="pointcloud", label="c", data=CLOUD,
                         mapping={"x_var": "x", "y_var": "y", "z_var": "nope"})
    with pytest.raises(ValueError, match="must be numeric"):
        MyIO().add_layer(type="pointcloud", label="c", data=[{"x": 1, "y": 1, "z": "a"}],
                         mapping={"x_var": "x", "y_var": "y", "z_var": "z"})
    with pytest.raises(ValueError, match="finite x, y and z"):
        MyIO().add_layer(type="pointcloud", label="c", data=[{"x": None, "y": 1, "z": 1}],
                         mapping={"x_var": "x", "y_var": "y", "z_var": "z"})
    chart = MyIO().add_layer(type="pointcloud", label="c", data=CLOUD, mapping=CLOUD_MAPPING)
    with pytest.raises(ValueError, match="incompatible"):
        chart.add_layer(type="point", label="p", data=GRID, mapping={"x_var": "x", "y_var": "y"})


def test_raster_and_image_layers():
    chart = (MyIO()
             .add_layer(type="image", label="Photo", data=[{"x": 0, "y": 0}, {"x": 2, "y": 1}],
                        mapping={"x_var": "x", "y_var": "y"},
                        options={"src": "data:image/png;base64,AAAA"})
             .add_layer(type="raster", label="v", data=GRID,
                        mapping={"x_var": "x", "y_var": "y", "value": "v"},
                        options={"palette": "cividis", "cellWidth": 1, "cellHeight": 1})
             .add_layer(type="point", label="p", data=GRID, mapping={"x_var": "x", "y_var": "y"},
                        options={"pointRadius": 2}))
    layers = chart.config["layers"]
    assert [layer["type"] for layer in layers] == ["image", "raster", "point"]
    assert layers[0]["options"]["src"].startswith("data:image/png")
    assert layers[1]["options"]["palette"] == "cividis"
    assert len(layers[1]["data"]) == 6
    assert layers[2]["options"]["pointRadius"] == 2
    with pytest.raises(ValueError, match="must be numeric"):
        MyIO().add_layer(type="raster", label="v", data=[{"x": 1, "y": 1, "v": "high"}],
                         mapping={"x_var": "x", "y_var": "y", "value": "v"})
    with pytest.raises(ValueError, match="Column 'shade' not found"):
        MyIO().add_layer(type="raster", label="v", data=GRID,
                         mapping={"x_var": "x", "y_var": "y", "value": "v", "shade": "shade"})


def test_line_options_and_set_equal_aspect():
    chart = MyIO().add_layer(type="line", label="track", data=GRID,
                             mapping={"x_var": "x", "y_var": "y"},
                             options={"curveType": "linear", "showPoints": False})
    opts = chart.config["layers"][0]["options"]
    assert opts["curveType"] == "linear" and opts["showPoints"] is False
    assert "equalAspect" not in MyIO().config["scales"]
    assert chart.set_equal_aspect().config["scales"]["equalAspect"] is True
    assert chart.set_equal_aspect(False).config["scales"]["equalAspect"] is False
    with pytest.raises(ValueError, match="True or False"):
        chart.set_equal_aspect("yes")


def test_pointcloud_accepts_a_pandas_frame():
    pd = pytest.importorskip("pandas")
    df = pd.DataFrame([row for row in CLOUD if row["x"] is not None])
    o = MyIO().add_layer(type="pointcloud", label="c", data=df, mapping=CLOUD_MAPPING).config["layers"][0]["options"]
    assert o["n"] == 3
    assert decode(o["cls"], "u1").tolist() == [2, 6, 11]


def test_pointcloud_packs_point_source_a_dem_grid_and_a_mesh():
    from pymyio.chart import pointcloud_mesh, pointcloud_terrain

    data = [{"x": 0, "y": 0, "z": 0, "src": "LiDAR"}, {"x": 1, "y": 1, "z": 1, "src": "camera"}]
    o = MyIO().add_layer(type="pointcloud", label="c", data=data,
                         mapping={"x_var": "x", "y_var": "y", "z_var": "z", "source": "src"}
                         ).config["layers"][0]["options"]
    assert decode(o["src"], "u1").tolist() == [0, 1]

    terrain = [{"x": 0, "y": 0, "z": 1}, {"x": 0.5, "y": 0, "z": 2}, {"x": 0, "y": 0.5, "z": 3}]
    g = pointcloud_terrain(terrain, cell_size=[0.5, 0.5])
    assert [g["cols"], g["rows"], g["x0"], g["y0"], g["dx"]] == [2, 2, 0, 0, 0.5]
    z = decode(g["z"], "<f4")
    assert z[:3].tolist() == [1, 2, 3] and np.isnan(z[3])

    vertices = [{"x": 0, "y": 0, "z": 0, "r": 1, "g": 2, "b": 3},
                {"x": 1, "y": 0, "z": 0, "r": 1, "g": 2, "b": 3},
                {"x": 0, "y": 1, "z": 0, "r": 1, "g": 2, "b": 3}]
    m = pointcloud_mesh(vertices, [[0, 1, 2]])
    assert (m["nv"], m["nf"]) == (3, 1)
    assert decode(m["faces"], "<u4").tolist() == [0, 1, 2]
    assert decode(m["colors"], "u1").tolist() == [1, 2, 3] * 3
    with pytest.raises(ValueError, match="0-based"):
        pointcloud_mesh(vertices, [[0, 1, 3]])

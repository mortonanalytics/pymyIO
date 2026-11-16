"""myDAR walk readers, bundled walk and views (parity with myIO test_mydar.R)."""

from __future__ import annotations

import base64
import importlib
import importlib.util
import json
import lzma
import math
import struct
from pathlib import Path

import numpy as np
import pytest

pd = pytest.importorskip("pandas")

from pymyio.mydar import (  # noqa: E402
    MydarDashboard,
    MydarWalk,
    mydar_accuracy_view,
    mydar_cloud_view,
    mydar_dashboard,
    mydar_gps_view,
    mydar_iphone_cloud,
    mydar_iphone_walk,
    mydar_orthophoto_view,
    mydar_plan_view,
    mydar_profile,
    mydar_profile_view,
    mydar_sigma_view,
    mydar_terrain_view,
    mydar_trajectory_view,
    read_mydar_points,
    read_mydar_trajectory,
    read_mydar_walk,
)
from pymyio.mydar._data import _read_cloud  # noqa: E402
from pymyio.mydar._read import png_chunks  # noqa: E402
from pymyio.mydar._views import _hillshade  # noqa: E402

DATA = Path(__file__).resolve().parent.parent / "src" / "pymyio" / "mydar" / "data"
SPATIAL = ("points", "terrain", "track", "track_points", "gps_fixes")


def layer_types(chart):
    return [layer["type"] for layer in chart.config["layers"]]


def layer_labels(chart):
    return [layer["label"] for layer in chart.config["layers"]]


@pytest.fixture
def walk():
    return mydar_iphone_walk()


# ---- readers -------------------------------------------------------------------


READER_WARNINGS = (
    pytest.mark.filterwarnings("ignore:Dataset has no geotransform"),
    pytest.mark.filterwarnings("ignore:'crs' was not provided"),
)


def _needs_readers():
    for module in ("laspy", "lazrs", "rasterio", "pyogrio", "shapely"):
        pytest.importorskip(module)


def write_walk_dir(walk: MydarWalk, root: Path) -> Path:
    """Write the bundled walk back out in the files the phone writes (COPC/LAZ
    cloud with sigma_m and source extra bytes, DEM and orthophoto GeoTIFFs,
    GeoPackage, trajectory CSV), so the readers run on real file formats."""
    import laspy
    import pyogrio
    import rasterio
    import shapely
    from rasterio.transform import from_origin

    root.mkdir()
    p = walk.points
    header = laspy.LasHeader(point_format=3, version="1.4")
    header.scales = np.array([1e-4, 1e-4, 1e-4])
    header.offsets = np.array([0.0, 0.0, 0.0])
    header.add_extra_dims([
        laspy.ExtraBytesParams(name="sigma_m", type=np.float64, description="1-sigma per axis, meters"),
        laspy.ExtraBytesParams(name="source", type=np.uint8, description="0 LiDAR, 1 camera"),
    ])
    las = laspy.LasData(header)
    las.x, las.y, las.z = p["x"].to_numpy(), p["y"].to_numpy(), p["z"].to_numpy()
    las.classification = p["class"].to_numpy().astype(np.uint8)
    for band, col in (("red", "r"), ("green", "g"), ("blue", "b")):
        setattr(las, band, (p[col].to_numpy() * 257).astype(np.uint16))
    las.sigma_m = p["sigma_m"].to_numpy()
    las.source = (p["source"] == "camera").to_numpy().astype(np.uint8)
    las.write(root / "walk.copc.laz")

    t = walk.terrain
    cw, ch = t.attrs["cell_size"]
    x0, y1 = t["x"].min(), t["y"].max()
    cols = np.round((t["x"] - x0) / cw).astype(int).to_numpy()
    rows = np.round((y1 - t["y"]) / ch).astype(int).to_numpy()
    grid = np.full((rows.max() + 1, cols.max() + 1), -9999.0)
    grid[rows, cols] = t["z"].to_numpy()
    with rasterio.open(root / "terrain.tif", "w", driver="GTiff", width=grid.shape[1],
                       height=grid.shape[0], count=1, dtype="float64", nodata=-9999.0,
                       transform=from_origin(x0 - cw / 2, y1 + ch / 2, cw, ch)) as dst:
        dst.write(grid, 1)

    # The orthophoto: the bundled PNG's pixels on its local extent.
    png = root / "ortho.png"
    png.write_bytes(walk.orthophoto["png"])
    with rasterio.open(png) as src:
        pixels = src.read()
    png.unlink()
    e, size = walk.orthophoto["extent"], walk.orthophoto["size"]
    with rasterio.open(root / "orthophoto.tif", "w", driver="GTiff", width=size["width"],
                       height=size["height"], count=pixels.shape[0], dtype="uint8",
                       transform=from_origin(e["xmin"], e["ymax"],
                                             (e["xmax"] - e["xmin"]) / size["width"],
                                             (e["ymax"] - e["ymin"]) / size["height"])) as dst:
        dst.write(pixels)

    gpkg = str(root / "walk.gpkg")

    def write_layer(name, geoms, fields, geometry_type):
        pyogrio.raw.write(gpkg, shapely.to_wkb(geoms), [f.to_numpy() for f in fields.values()],
                          fields=list(fields), layer=name, driver="GPKG",
                          geometry_type=geometry_type, append=Path(gpkg).exists())

    track = shapely.linestrings(walk.track[["x", "y", "z"]].to_numpy())
    write_layer("track", np.array([track]), {"length_m": pd.Series([1.0])}, "LineString Z")

    def point_layer(name, df, cols):
        geoms = shapely.points(df[["x", "y", "z"]].to_numpy()) if len(df) else np.array([], dtype=object)
        write_layer(name, geoms, {c: df[c].astype(float) for c in cols}, "Point Z")

    point_layer("track_points", walk.track_points, ["t_s", "map_95_m"])
    point_layer("gps_fixes", walk.gps_fixes,
                ["t_s", "h_acc_m", "used", "residual_m", "residual_95_m", "map_95_m"])
    acc = walk.accuracy
    pyogrio.raw.write(gpkg, None, [acc[c].to_numpy() for c in acc.columns], fields=list(acc.columns),
                      layer="accuracy", driver="GPKG", append=True)

    walk.trajectory.drop(columns="t_s").to_csv(root / "trajectory.csv", index=False)
    return root


@READER_WARNINGS[0]
@READER_WARNINGS[1]
def test_read_mydar_walk_reads_the_phone_file_formats_back(walk, tmp_path):
    _needs_readers()
    back = read_mydar_walk(str(write_walk_dir(walk, tmp_path / "walk")), max_points=math.inf,
                           local=False)
    assert isinstance(back, MydarWalk)
    assert len(back.points) == len(walk.points)
    np.testing.assert_allclose(back.points["x"], walk.points["x"], atol=1e-3)
    np.testing.assert_allclose(back.points["z"], walk.points["z"], atol=1e-3)
    assert list(back.points["class_name"]) == list(walk.points["class_name"])
    assert list(back.points["source"]) == list(walk.points["source"])
    np.testing.assert_allclose(back.points["sigma_m"], walk.points["sigma_m"], rtol=1e-12)
    assert (back.points[["r", "g", "b"]].to_numpy() == walk.points[["r", "g", "b"]].to_numpy()).all()
    assert back.orthophoto["size"] == walk.orthophoto["size"]
    for k, v in walk.orthophoto["extent"].items():
        assert back.orthophoto["extent"][k] == pytest.approx(v, abs=1e-6)
    assert list(dict.fromkeys(png_chunks(back.orthophoto["png"]))) == ["IHDR", "IDAT", "IEND"]
    assert len(back.terrain) == len(walk.terrain)
    np.testing.assert_allclose(back.terrain.attrs["cell_size"], walk.terrain.attrs["cell_size"])
    np.testing.assert_allclose(back.track[["x", "y", "z"]], walk.track[["x", "y", "z"]], atol=1e-9)
    np.testing.assert_array_equal(back.track_points["map_95_m"], walk.track_points["map_95_m"])
    np.testing.assert_array_equal(back.gps_fixes["residual_m"], walk.gps_fixes["residual_m"])
    np.testing.assert_allclose(back.trajectory["t_s"], walk.trajectory["t_s"], atol=1e-9)
    assert back.accuracy["shape_95_within_5m_m"].iloc[0] == walk.accuracy["shape_95_within_5m_m"].iloc[0]
    assert back.origin == {"x": 0.0, "y": 0.0, "z": 0.0}


@READER_WARNINGS[0]
@READER_WARNINGS[1]
def test_local_shifts_by_subtraction_and_max_points_max_cells_thin(walk, tmp_path):
    _needs_readers()
    lifted = mydar_iphone_walk()
    for part in SPATIAL:
        getattr(lifted, part)["z"] += 500  # so the z shift has something to remove
    root = write_walk_dir(lifted, tmp_path / "walk")

    thin = read_mydar_walk(str(root), max_points=1000, max_cells=500)
    assert len(thin.points) == 1000
    assert thin.points.attrs["n_total"] == len(walk.points)
    assert len(thin.terrain) <= 500
    assert (thin.points["x"] >= 0).all() and (thin.points["y"] >= 0).all()
    assert "1,000 of 6,000" in repr(thin)

    full = read_mydar_walk(str(root), max_points=math.inf)
    assert full.terrain["z"].min() == pytest.approx(0)
    assert full.origin["z"] == pytest.approx(500 + walk.terrain["z"].min(), abs=1e-6)
    np.testing.assert_allclose(full.points["x"] + full.origin["x"], walk.points["x"], atol=1e-3)
    np.testing.assert_allclose(full.points["z"], walk.points["z"], atol=1e-3)
    np.testing.assert_allclose(full.track["z"], walk.track["z"], atol=1e-6)


@READER_WARNINGS[0]
@READER_WARNINGS[1]
def test_empty_geopackage_layer_reads_as_zero_rows(tmp_path):
    _needs_readers()
    w = mydar_iphone_walk()
    w.gps_fixes = w.gps_fixes.iloc[0:0]
    back = read_mydar_walk(str(write_walk_dir(w, tmp_path / "walk")), max_points=100, local=False)
    assert len(back.gps_fixes) == 0


def test_readers_fail_clearly_on_missing_files_and_packages(tmp_path, monkeypatch):
    with pytest.raises(FileNotFoundError, match="directory not found"):
        read_mydar_walk(str(tmp_path / "nope"))
    with pytest.raises(FileNotFoundError, match="file not found"):
        read_mydar_trajectory(str(tmp_path / "nope.csv"))

    real = importlib.import_module

    def no_laspy(name, *args, **kwargs):
        if name == "laspy":
            raise ImportError("No module named 'laspy'")
        return real(name, *args, **kwargs)

    monkeypatch.setattr(importlib, "import_module", no_laspy)
    with pytest.raises(ImportError, match=r"pip install 'pymyio\[mydar\]'"):
        read_mydar_points("walk.copc.laz")


# ---- the bundled walk ------------------------------------------------------------


def test_bundled_walk_carries_no_location(walk):
    assert set(walk.origin) == {"x", "y", "z"}
    assert all(math.isnan(v) for v in walk.origin.values())
    assert walk.crs is None
    assert "crs" not in walk.accuracy.columns
    assert walk.features == {}
    location_words = ("lat", "lon", "easting", "northing", "crs", "epsg", "utm", "geoid")
    for part in SPATIAL + ("trajectory", "accuracy", "pins"):
        df = getattr(walk, part)
        for col in df.columns:
            assert not any(word in col.lower() for word in location_words), (part, col)
    for part in SPATIAL:
        df = getattr(walk, part)
        xy = df[["x", "y"]].to_numpy()
        assert np.nanmax(np.abs(xy)) < 1000, part  # no projected (project-scale) x/y
        # Heights above the lowest ground cell, so no absolute (site) height.
        assert np.nanmax(np.abs(df["z"])) < 100, part
    traj = walk.trajectory[["x", "y", "z"]].to_numpy()
    assert np.nanmax(np.abs(traj)) < 100  # meters from the first GPS fix
    assert walk.terrain["z"].min() == 0
    assert "origin withheld" in repr(walk)

    # The orthophoto is pixels only on a local extent.
    assert list(dict.fromkeys(png_chunks(walk.orthophoto["png"]))) == ["IHDR", "IDAT", "IEND"]
    assert all(abs(v) < 1000 for v in walk.orthophoto["extent"].values())
    meta = json.loads((DATA / "walk.json").read_text(encoding="utf-8"))
    assert set(meta) == {"points_n_total", "terrain_cell_size", "orthophoto_extent", "orthophoto_size"}

    # The bundled cloud file: local x/y/z in its header.
    raw = lzma.decompress((DATA / "mydar-iphone-walk-cloud.bin").read_bytes())
    assert raw[:8] == b"MYDARPC1"
    assert struct.unpack("<i", raw[8:12])[0] == 500_000
    assert all(abs(v) < 100 for v in struct.unpack("<6d", raw[12:60]))


def test_bundled_cloud_reads_back_as_500000_local_points():
    cloud = mydar_iphone_cloud()
    assert len(cloud) == 500_000
    assert list(cloud.columns) == ["x", "y", "z", "class", "class_name", "sigma_m", "source",
                                   "r", "g", "b"]
    assert cloud["x"].between(-1, 100).all() and cloud["y"].between(-1, 100).all()
    assert cloud["z"].between(-5, 20).all()
    assert {"Ground", "Building", "Low vegetation"} <= set(cloud["class_name"])
    assert cloud["sigma_m"].between(0.005, 0.1).all()


def test_cloud_file_format_decodes_within_its_quantization():
    # Three points packed by hand in myIO's cloud file layout.
    bbox = (0.0, 7.5, 1.0, 4.0, 0.0, 2.1)
    q = np.array([[0, 0, 0], [27962, 32768, 12483], [65535, 65535, 65535]], dtype="<u2")
    body = (b"MYDARPC1" + struct.pack("<i", 3) + struct.pack("<6d", *bbox)
            + q[:, 0].tobytes() + q[:, 1].tobytes() + q[:, 2].tobytes()
            + bytes([10, 200, 255]) + bytes([0, 128, 30]) + bytes([5, 64, 90])
            + bytes([2, 6, 11]) + bytes([0, 128, 255]) + bytes([0, 0, 1]))
    back = _read_cloud(lzma.compress(body))
    np.testing.assert_allclose(back["x"], [0, 3.2, 7.5], atol=1e-3)
    np.testing.assert_allclose(back["sigma_m"], [1e-3, 10 ** (128 / 255 * 4 - 3), 10])
    assert list(back["class_name"]) == ["Ground", "Building", "Road"]
    assert list(back["source"]) == ["LiDAR", "LiDAR", "camera"]


# ---- views -----------------------------------------------------------------------


def test_profile_keeps_points_in_the_corridor_ordered_along_the_line(walk):
    ym = (walk.track["y"].min() + walk.track["y"].max()) / 2
    prof = mydar_profile(walk, from_=(0, ym), to=(22, ym), width=0.4)
    assert len(prof) > 0
    assert (prof["offset"].abs() <= 0.2).all()
    assert prof["distance"].between(0, 22).all()
    assert prof["distance"].is_monotonic_increasing
    np.testing.assert_allclose(prof["distance"], prof["x"], atol=1e-9)
    np.testing.assert_allclose(prof["offset"], prof["y"] - ym, atol=1e-9)
    with pytest.raises(ValueError, match="same point"):
        mydar_profile(walk, from_=(1, 1), to=(1, 1))
    with pytest.raises(ValueError, match="positive number"):
        mydar_profile(walk, width=0)


def test_hillshade_is_uniform_on_a_plane_and_darker_facing_away():
    gx, gy = np.meshgrid(np.round(np.arange(0, 1.01, 0.1), 10), np.round(np.arange(0, 1.01, 0.1), 10))
    flat = pd.DataFrame({"x": gx.ravel(), "y": gy.ravel(), "z": 5.0})
    s = _hillshade(flat, [0.1, 0.1], azimuth=315, altitude=45)
    np.testing.assert_allclose(s, math.sin(math.pi / 4))
    east_up = flat.assign(z=flat["x"])  # the slope faces west
    away = _hillshade(east_up, [0.1, 0.1], azimuth=90, altitude=45)
    toward = _hillshade(east_up, [0.1, 0.1], azimuth=270, altitude=45)
    assert (away < math.sin(math.pi / 4)).all()
    assert (toward > away).all()


def with_gps(walk):
    """GPS fixes with an ignored fix, which the bundled walk does not have."""
    walk.gps_fixes = pd.DataFrame({
        "t_s": [1, 2, 3, 4], "h_acc_m": [4, 5, 5, 6], "used": [1, 1, 0, 1],
        "residual_m": [0.2, 0.1, 0.5, 0.3], "residual_95_m": [9, 9, 10, 11],
        "map_95_m": 17, "x": [1, 2, 3, 4], "y": [1, 2, 3, 4], "z": 0,
    })
    return walk


def test_views_build_the_expected_layers(walk):
    plan = mydar_plan_view(walk, profile={"from": (0, 4), "to": (10, 4)})
    assert layer_labels(plan) == ["Orthophoto", "Track", "Profile line", "Accuracy"]
    assert layer_types(plan)[0] == "image"
    assert plan.config["scales"]["equalAspect"] is True
    with_points = mydar_plan_view(walk, points=True)
    assert {"Ground", "Building", "Low vegetation"} <= set(layer_labels(with_points))
    ground = next(layer for layer in with_points.config["layers"] if layer["label"] == "Ground")
    assert ground["options"]["opacity"] < 1 and ground["options"]["pointRadius"] <= 1.5
    no_ortho = mydar_iphone_walk()
    no_ortho.orthophoto = None
    assert "Ground" in layer_labels(mydar_plan_view(no_ortho))
    cap = next(layer for layer in plan.config["layers"] if layer["label"] == "Accuracy")
    assert [row["text"] for row in cap["data"]] == ["Shape ±5.9 cm", "Map ±17 m"]
    track = next(layer for layer in plan.config["layers"] if layer["label"] == "Track")
    assert track["options"]["curveType"] == "linear" and track["options"]["showPoints"] is False
    assert plan.config["axes"]["xAxisLabel"] == "Easting from walk origin (m)"
    assert mydar_orthophoto_view(walk).config["scales"]["equalAspect"] is True

    terrain = mydar_terrain_view(walk)
    assert terrain.config["scales"]["equalAspect"] is True
    assert layer_types(terrain) == ["raster"]
    assert terrain.config["layers"][0]["mapping"]["shade"] == "shade"
    assert terrain.config["layers"][0]["options"]["cellWidth"] == walk.terrain.attrs["cell_size"][0]
    assert "shade" not in mydar_terrain_view(walk, hillshade=False).config["layers"][0]["mapping"]

    profile = mydar_profile_view(walk)
    assert "DEM" in layer_labels(profile)
    assert profile.config["axes"]["yAxisLabel"] == "Height above lowest ground (m)"
    with pytest.raises(ValueError, match="no points within"):
        mydar_profile_view(walk, from_=(100, 100), to=(101, 100))

    no_gps = mydar_iphone_walk()
    no_gps.gps_fixes = no_gps.gps_fixes.iloc[0:0]
    assert layer_types(mydar_trajectory_view(walk)) == ["line", "point"]
    assert layer_types(mydar_trajectory_view(no_gps)) == ["line"]
    with pytest.raises(ValueError, match="no gps_fixes"):
        mydar_gps_view(no_gps)
    assert {"Used", "Expected 95%"} <= set(layer_labels(mydar_gps_view(walk)))
    assert layer_labels(mydar_gps_view(with_gps(mydar_iphone_walk()))) == ["Used", "Ignored", "Expected 95%"]
    assert set(layer_types(mydar_sigma_view(walk))) <= {"area", "point", "rangeBar"}

    acc = mydar_accuracy_view(walk).config["layers"][0]
    assert [row["figure"] for row in acc["data"]] == ["Shape <5 m", "Map median", "Map max"]
    for chart in (plan, terrain, profile, mydar_gps_view(walk)):
        json.dumps(chart.to_config(), allow_nan=False)


def test_cloud_view_packs_the_cloud_with_ortho_track_and_accuracy_card(walk):
    layer = mydar_cloud_view(walk, color="class", mode="plan", point_size=3).config["layers"][0]
    assert layer["type"] == "pointcloud"
    assert layer["data"] == []
    o = layer["options"]
    assert o["n"] == len(walk.points)
    assert "rgb" in o
    assert (o["color"], o["mode"], o["pointSize"]) == ("class", "plan", 3)
    assert o["caption"] == {"shape": "±5.9 cm", "shapeNote": "within 5 m · 5–15 m withheld",
                            "map": "±17 m", "mapNote": "phone GPS"}
    assert o["ortho"]["src"].startswith("data:image/png;base64,")
    assert len(o["track"]) == len(walk.track)
    assert o["classNames"]["2"] == "Ground"
    assert "ortho" not in mydar_cloud_view(walk, ortho=False).config["layers"][0]["options"]
    with pytest.raises(ValueError, match="x, y and z"):
        mydar_cloud_view(walk, points=pd.DataFrame({"a": [1]}))
    with pytest.raises(ValueError, match="color"):
        mydar_cloud_view(walk, color="rainbow")


def test_views_refuse_a_walk_without_the_part_they_plot():
    w = mydar_iphone_walk()
    w.points = None
    with pytest.raises(ValueError, match="this walk has no points"):
        mydar_plan_view(w)
    with pytest.raises(TypeError, match="must be a MydarWalk"):
        mydar_plan_view({})


def key_columns(charts):
    return [(c.config["interactions"].get("linked") or {}).get("keyColumn") for c in charts]


def test_dashboard_links_plan_and_profile_and_time_charts_only_with_gps(walk):
    assert "Ground" not in layer_labels(mydar_dashboard(walk).charts[1])
    dash = mydar_dashboard(walk, plan_points=True)
    assert isinstance(dash, MydarDashboard)
    charts = dash.charts
    assert len(charts) == 8
    assert charts[0].config["layers"][0]["type"] == "pointcloud"
    assert "Ground" in layer_labels(charts[1])
    assert key_columns(charts).count("point_id") == 2
    assert key_columns(charts).count("t_s") == 2
    assert charts[1].config["interactions"]["brush"]["enabled"] is True
    assert [heading for heading, _ in dash.sections] == ["Map", "Profile", "Quality"]

    no_gps = mydar_iphone_walk()
    no_gps.gps_fixes = no_gps.gps_fixes.iloc[0:0]
    charts = mydar_dashboard(no_gps).charts
    assert len(charts) == 7
    assert key_columns(charts).count("t_s") == 0


def test_dashboard_page_holds_every_chart_and_the_engine_once(walk, tmp_path):
    dash = mydar_dashboard(walk)
    page = dash.to_html()
    assert page.count('class="pymyio-chart"') == 8
    assert page.count('type="application/json" id="pymyio-config-') == 8
    assert page.count("myIOchart") >= 1
    path = dash.save(str(tmp_path / "walk.html"))
    assert Path(path).read_text(encoding="utf-8").startswith("<!doctype html>")
    assert "srcdoc=" in dash._repr_html_()


@pytest.mark.skipif(importlib.util.find_spec("playwright") is None, reason="playwright not installed")
def test_dashboard_draws_the_cloud_and_every_svg_chart_in_a_browser(walk, tmp_path):
    from playwright.sync_api import sync_playwright

    path = mydar_dashboard(walk).save(str(tmp_path / "walk.html"))
    errors = []
    try:
        with sync_playwright() as p:
            try:
                browser = p.chromium.launch(args=["--use-angle=swiftshader",
                                                  "--enable-unsafe-swiftshader"])
            except Exception as e:  # pragma: no cover - depends on the machine
                pytest.skip(f"chromium not installed: {e}")
            page = browser.new_page(viewport={"width": 1200, "height": 900})
            page.on("pageerror", lambda e: errors.append(str(e)))
            page.goto(f"file://{path}")
            page.wait_for_selector(".pymyio-chart canvas", timeout=20_000)
            page.wait_for_timeout(1500)
            charts_with_svg = page.evaluate(
                "Array.from(document.querySelectorAll('.pymyio-chart'))"
                ".filter(el => el.querySelector('svg')).length")
            canvas = page.locator(".pymyio-chart canvas").first
            pixels = canvas.screenshot()
            browser.close()
    except Exception as e:  # pragma: no cover - depends on the machine
        if "Timeout" in type(e).__name__:
            raise
        pytest.skip(f"playwright browser unavailable: {e}")
    assert errors == []
    assert charts_with_svg >= 7
    # A blank canvas compresses to a few hundred bytes of PNG; drawn points do not.
    assert len(pixels) > 20_000


def test_png_data_url_round_trips_the_bundled_orthophoto(walk):
    src = mydar_plan_view(walk).config["layers"][0]["options"]["src"]
    assert base64.b64decode(src.split(",", 1)[1]) == (DATA / "orthophoto.png").read_bytes()

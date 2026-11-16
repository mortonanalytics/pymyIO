"""Readers for myDAR walk output folders (R ``read_mydar_*()``)."""

from __future__ import annotations

import importlib
import math
import os
import struct
import zlib
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd

MYDAR_CLASSES = pd.DataFrame({
    "class": [0, 1, 2, 3, 4, 5, 6, 9, 11],
    "class_name": ["Never classified", "Unclassified", "Ground", "Low vegetation",
                   "Medium vegetation", "High vegetation", "Building", "Water", "Road"],
    "color": ["#BBBBBB", "#777777", "#8C6D31", "#A6D96A", "#009E73", "#00573F",
              "#D55E00", "#0072B2", "#E69F00"],
})

_SPATIAL = ("points", "terrain", "track", "track_points", "gps_fixes", "pins")


@dataclass
class MydarWalk:
    """A myDAR walk read into data frames (R class ``mydar_walk``).

    ``points`` carries ``attrs["n_total"]`` (points in the file) and
    ``terrain`` carries ``attrs["cell_size"]`` (cell width and height).
    ``orthophoto`` is ``{"png": bytes, "extent": {...}, "size": {...}}``.
    ``origin`` is the x/y/z subtracted by ``local=True``; its values are NaN
    when the origin is withheld, as in the bundled walk.
    """

    points: Optional[pd.DataFrame] = None
    terrain: Optional[pd.DataFrame] = None
    track: Optional[pd.DataFrame] = None
    track_points: Optional[pd.DataFrame] = None
    gps_fixes: Optional[pd.DataFrame] = None
    pins: Optional[pd.DataFrame] = None
    features: Dict[str, pd.DataFrame] = field(default_factory=dict)
    accuracy: pd.DataFrame = field(default_factory=pd.DataFrame)
    trajectory: Optional[pd.DataFrame] = None
    orthophoto: Optional[Dict[str, Any]] = None
    crs: Optional[str] = None
    origin: Dict[str, float] = field(default_factory=lambda: {"x": 0.0, "y": 0.0, "z": 0.0})

    def __repr__(self) -> str:
        def rows(df: Optional[pd.DataFrame]) -> str:
            return "none" if df is None else f"{len(df):,}"

        n_total = self.points.attrs.get("n_total") if self.points is not None else None
        points = rows(self.points)
        if n_total is not None and n_total > len(self.points):
            points += f" of {n_total:,}"
        lines = [
            "<MydarWalk>" + (f" {self.crs}" if self.crs else ""),
            f"  points:       {points}",
            f"  terrain:      {rows(self.terrain)} cells",
            f"  track:        {rows(self.track)} vertices",
            f"  gps_fixes:    {rows(self.gps_fixes)}",
            "  features:     " + (", ".join(self.features) if self.features else "none"),
            f"  trajectory:   {rows(self.trajectory)} poses",
        ]
        if self.orthophoto is not None:
            size = self.orthophoto["size"]
            lines.append(f"  orthophoto:   {size['width']:g} x {size['height']:g} px")
        values = list(self.origin.values())
        if any(math.isnan(v) for v in values):
            lines.append("  local coordinates (origin withheld)")
        elif any(v != 0 for v in values):
            lines.append("  local origin: " + ", ".join(f"{v:g}" for v in values))
        return "\n".join(lines)


def read_mydar_walk(dir: str, max_points: float = 20000, max_cells: float = 40000,
                    local: bool = True) -> MydarWalk:
    """Read a myDAR walk output folder.

    The folder holds ``walk.copc.laz`` (the point cloud), ``terrain.tif`` (the
    DEM), ``orthophoto.tif``, ``walk.gpkg`` (track, GPS fixes, pins, features
    and the ``accuracy`` table) and ``trajectory.csv`` (the device poses).
    Walks recorded without LiDAR have no point cloud or DEM; those parts are
    ``None``.

    ``max_points`` thins the cloud to every k-th point in file order (use
    ``math.inf`` to keep every point); ``max_cells`` aggregates a larger DEM
    by the smallest whole factor that fits (cell mean). With ``local=True``
    (default) every spatial table is moved to walk-local coordinates by
    subtraction only: x and y become meters from a whole-meter origin at the
    walk's south-west corner, and z becomes height above the lowest DEM cell
    (or the lowest ground-class point when there is no DEM). The subtracted
    origin is kept in ``origin``. ``trajectory.csv`` is in its own local frame
    and is left as written.

    Needs the ``mydar`` extra: ``pip install 'pymyio[mydar]'``.
    """
    _check_flag(local, "local", "read_mydar_walk")
    if not isinstance(dir, (str, os.PathLike)):
        raise ValueError("read_mydar_walk(): `dir` must be a path.")
    if not os.path.isdir(dir):
        raise FileNotFoundError(f"read_mydar_walk(): directory not found: {dir}")

    def file_in(name: str) -> Optional[str]:
        p = os.path.join(dir, name)
        return p if os.path.exists(p) else None

    gpkg_path = file_in("walk.gpkg")
    if gpkg_path is None:
        raise FileNotFoundError(f"read_mydar_walk(): no walk.gpkg in {dir}.")
    gpkg = read_mydar_gpkg(gpkg_path)
    laz, dem = file_in("walk.copc.laz"), file_in("terrain.tif")
    traj, ortho = file_in("trajectory.csv"), file_in("orthophoto.tif")
    accuracy = gpkg["accuracy"]
    crs = None
    if len(accuracy) > 0 and "crs" in accuracy.columns:
        crs = accuracy["crs"].iloc[0]

    walk = MydarWalk(
        points=read_mydar_points(laz, max_points=max_points) if laz else None,
        terrain=read_mydar_terrain(dem, max_cells=max_cells) if dem else None,
        trajectory=read_mydar_trajectory(traj) if traj else None,
        orthophoto=read_mydar_orthophoto(ortho) if ortho else None,
        crs=crs,
        **gpkg,
    )
    if local:
        _shift_local(walk)
    return walk


def read_mydar_points(path: str, max_points: float = 20000) -> pd.DataFrame:
    """Read a walk's ``walk.copc.laz`` point cloud (needs laspy with lazrs).

    Returns one row per kept point: ``point_id`` (row in the file), ``x``,
    ``y``, ``z``, ``class`` (LAS code), ``class_name``, ``sigma_m`` (per-point
    1-sigma per axis, meters), ``source`` (``"LiDAR"`` or ``"camera"``) and,
    when the cloud is colored, ``r``, ``g``, ``b`` (0-255).
    ``attrs["n_total"]`` holds the number of points in the file.
    """
    laspy = _require("laspy", "read_mydar_points")
    _check_file(path, "read_mydar_points")
    if (not isinstance(max_points, (int, float)) or isinstance(max_points, bool)
            or math.isnan(max_points) or max_points < 1):
        raise ValueError("read_mydar_points(): `max_points` must be a single number of at least 1.")

    las = laspy.read(path)
    extra = set(las.point_format.extra_dimension_names)
    missing = [name for name in ("sigma_m", "source") if name not in extra]
    if missing:
        raise ValueError(
            f"read_mydar_points(): {path} has no extra bytes {' and '.join(missing)}; "
            "is it a myDAR walk cloud?"
        )

    n = len(las.points)
    if n > max_points:
        keep = np.unique(np.round(np.linspace(1, n, int(max_points)))).astype(np.int64) - 1
    else:
        keep = np.arange(n)
    class_code = np.asarray(las.classification)[keep].astype(np.int64)
    points = pd.DataFrame({
        "point_id": keep + 1,
        "x": np.asarray(las.x)[keep],
        "y": np.asarray(las.y)[keep],
        "z": np.asarray(las.z)[keep],
        "class": class_code,
        "class_name": mydar_class_name(class_code),
        "sigma_m": np.asarray(las["sigma_m"], dtype=np.float64)[keep],
        "source": np.where(np.asarray(las["source"])[keep] == 1, "camera", "LiDAR"),
    })
    dims = set(las.point_format.dimension_names)
    if {"red", "green", "blue"} <= dims:
        rgb = [np.asarray(las[c], dtype=np.float64) for c in ("red", "green", "blue")]
        # LAS stores 16-bit color; scale to 0-255 unless the file wrote 8-bit.
        k = 257 if max(float(v.max()) for v in rgb) > 255 else 1
        for name, v in zip(("r", "g", "b"), rgb):
            points[name] = np.round(v[keep] / k).astype(np.int64)
    points.attrs["n_total"] = n
    return points


def read_mydar_terrain(path: str, max_cells: float = 40000) -> pd.DataFrame:
    """Read a walk's ``terrain.tif`` DEM (needs rasterio).

    Returns one row per cell with a height: ``x``, ``y`` (cell center) and
    ``z``. ``attrs["cell_size"]`` holds the cell width and height.
    """
    rasterio = _require("rasterio", "read_mydar_terrain")
    _check_file(path, "read_mydar_terrain")
    if (not isinstance(max_cells, (int, float)) or isinstance(max_cells, bool)
            or math.isnan(max_cells) or max_cells < 1):
        raise ValueError("read_mydar_terrain(): `max_cells` must be a single number of at least 1.")

    with rasterio.open(path) as src:
        z = src.read(1, masked=True).astype(np.float64).filled(np.nan)
        transform = src.transform
    factor = math.ceil(math.sqrt(z.size / max_cells))
    z = _aggregate_mean(z, factor)
    xres, yres = abs(transform.a) * factor, abs(transform.e) * factor
    rows, cols = np.indices(z.shape)
    x = transform.c + (cols + 0.5) * xres
    y = transform.f - (rows + 0.5) * yres
    ok = np.isfinite(z)
    terrain = pd.DataFrame({"x": x[ok], "y": y[ok], "z": z[ok]})
    terrain.attrs["cell_size"] = [xres, yres]
    return terrain


def read_mydar_orthophoto(path: str, max_pixels: float = 4e6) -> Dict[str, Any]:
    """Read a walk's ``orthophoto.tif`` (needs rasterio).

    Returns ``{"png": bytes, "extent": {"xmin", "xmax", "ymin", "ymax"},
    "size": {"width", "height"}}``. The PNG holds the pixels only (IHDR, IDAT
    and IEND chunks): no georeference or metadata travels with the image. A
    larger image is averaged down by the smallest whole factor that keeps it
    under ``max_pixels``.
    """
    rasterio = _require("rasterio", "read_mydar_orthophoto")
    _check_file(path, "read_mydar_orthophoto")
    with rasterio.open(path) as src:
        if src.count not in (3, 4):
            raise ValueError(f"read_mydar_orthophoto(): {path} needs RGB or RGBA bands.")
        bands = src.read(masked=True).astype(np.float64).filled(np.nan)
        transform = src.transform
    factor = math.ceil(math.sqrt(bands[0].size / max_pixels))
    bands = np.stack([_aggregate_mean(b, factor) for b in bands])
    height, width = bands.shape[1:]
    xmin, ymax = transform.c, transform.f
    xmax = xmin + width * abs(transform.a) * factor
    ymin = ymax - height * abs(transform.e) * factor
    pixels = np.clip(np.round(np.nan_to_num(bands, nan=0.0)), 0, 255).astype(np.uint8)
    return {
        "png": _png_bytes(np.moveaxis(pixels, 0, -1)),
        "extent": {"xmin": xmin, "xmax": xmax, "ymin": ymin, "ymax": ymax},
        "size": {"width": width, "height": height},
    }


def read_mydar_gpkg(path: str) -> Dict[str, Any]:
    """Read a walk's ``walk.gpkg`` (needs pyogrio and shapely).

    Returns ``track``, ``track_points``, ``gps_fixes``, ``pins`` (one row per
    vertex, with ``vertex``, ``x``, ``y``, ``z`` and the layer's attributes),
    ``features`` (one such table per feature layer) and the one-row
    ``accuracy`` table.
    """
    pyogrio = _require("pyogrio", "read_mydar_gpkg")
    shapely = _require("shapely", "read_mydar_gpkg")
    _check_file(path, "read_mydar_gpkg")

    layers = pyogrio.list_layers(path)
    names_all = [str(name) for name, _ in layers]
    has_geom = [str(name) for name, geom in layers if geom is not None]

    def read(name: str) -> Optional[pd.DataFrame]:
        if name not in names_all:
            return None
        meta, _, geometry, field_data = pyogrio.raw.read(path, layer=name,
                                                         read_geometry=name in has_geom)
        attrs = pd.DataFrame({col: np.asarray(values)
                              for col, values in zip(meta["fields"], field_data)})
        if geometry is None:
            return attrs
        return _vertices(attrs, shapely.from_wkb(geometry), shapely)

    core = {"track", "track_points", "gps_fixes", "pins", "loops", "photos"}
    features = {name: read(name) for name in has_geom if name not in core}
    track = read("track")
    if track is not None:
        track = track[["vertex", "x", "y", "z"]]
    accuracy = read("accuracy")
    return {
        "track": track,
        "track_points": read("track_points"),
        "gps_fixes": read("gps_fixes"),
        "pins": read("pins"),
        "features": features,
        "accuracy": pd.DataFrame() if accuracy is None else accuracy,
    }


def read_mydar_trajectory(path: str) -> pd.DataFrame:
    """Read a walk's ``trajectory.csv``; adds ``t_s``, seconds from the first pose."""
    _check_file(path, "read_mydar_trajectory")
    traj = pd.read_csv(path, dtype=np.float64, float_precision="round_trip")
    if not {"t_ns", "x", "y", "z"} <= set(traj.columns):
        raise ValueError(f"read_mydar_trajectory(): {path} needs columns t_ns, x, y and z.")
    traj.insert(0, "t_s", (traj["t_ns"] - traj["t_ns"].iloc[0]) / 1e9)
    return traj


# ---- helpers ----------------------------------------------------------------


def mydar_class_name(code: Any) -> np.ndarray:
    """LAS class names for class codes; unknown codes read ``"Class <code>"``."""
    lookup = dict(zip(MYDAR_CLASSES["class"], MYDAR_CLASSES["class_name"]))
    return np.array([lookup.get(int(c), f"Class {int(c)}") for c in np.asarray(code)], dtype=object)


def _require(module: str, caller: str):
    try:
        return importlib.import_module(module)
    except ImportError:
        raise ImportError(
            f"{caller}() needs the '{module}' package. Install the myDAR readers with: "
            "pip install 'pymyio[mydar]'"
        ) from None


def _check_file(path: Any, caller: str) -> None:
    if not isinstance(path, (str, os.PathLike)):
        raise ValueError(f"{caller}(): `path` must be a path.")
    if not os.path.exists(path):
        raise FileNotFoundError(f"{caller}(): file not found: {path}")


def _check_flag(value: Any, name: str, caller: str) -> None:
    if not isinstance(value, bool):
        raise ValueError(f"{caller}(): `{name}` must be True or False.")


def _aggregate_mean(a: np.ndarray, factor: int) -> np.ndarray:
    """Block mean ignoring NaN, padding the right and bottom edges (terra::aggregate)."""
    if factor <= 1:
        return a
    rows = -(-a.shape[0] // factor) * factor
    cols = -(-a.shape[1] // factor) * factor
    padded = np.full((rows, cols), np.nan)
    padded[: a.shape[0], : a.shape[1]] = a
    blocks = padded.reshape(rows // factor, factor, cols // factor, factor)
    count = np.isfinite(blocks).sum(axis=(1, 3))
    total = np.nansum(blocks, axis=(1, 3))
    with np.errstate(invalid="ignore", divide="ignore"):
        return np.where(count > 0, total / count, np.nan)


def _vertices(attrs: pd.DataFrame, geoms: np.ndarray, shapely) -> pd.DataFrame:
    """One row per vertex (x, y, z) with the layer's attributes.

    Empty geometries keep their row with NaN coordinates.
    """
    pieces: List[pd.DataFrame] = []
    for i, g in enumerate(geoms):
        if g is None or shapely.is_empty(g):
            xyz = np.full((1, 3), np.nan)
        else:
            xyz = shapely.get_coordinates(g, include_z=True)
        pieces.append(pd.DataFrame({"row": i, "vertex": np.arange(1, len(xyz) + 1),
                                    "x": xyz[:, 0], "y": xyz[:, 1], "z": xyz[:, 2]}))
    if not pieces:
        out = attrs.iloc[0:0].copy()
        for col in ("vertex", "fid"):
            out[col] = pd.Series(dtype=np.int64)
        for col in ("x", "y", "z"):
            out[col] = pd.Series(dtype=np.float64)
        return out
    v = pd.concat(pieces, ignore_index=True)
    out = attrs.iloc[v["row"].to_numpy()].reset_index(drop=True)
    out = pd.concat([out, v[["vertex", "x", "y", "z"]]], axis=1)
    if "fid" not in out.columns:
        out["fid"] = v["row"].to_numpy() + 1
    return out


def _shift_local(walk: MydarWalk) -> None:
    tables = [getattr(walk, name) for name in _SPATIAL] + list(walk.features.values())
    xs = [df["x"].to_numpy() for df in tables if df is not None and len(df) > 0]
    ys = [df["y"].to_numpy() for df in tables if df is not None and len(df) > 0]
    if not xs or not np.isfinite(np.concatenate(xs)).any():
        return
    # Heights: the lowest DEM cell (the DEM is the ground surface), else the
    # lowest ground-class point, else the lowest point.
    pts = walk.points
    if walk.terrain is not None and np.isfinite(walk.terrain["z"]).any():
        z0 = float(np.nanmin(walk.terrain["z"]))
    elif pts is not None and (pts["class"] == 2).any():
        z0 = float(np.nanmin(pts.loc[pts["class"] == 2, "z"]))
    elif pts is not None and len(pts) > 0:
        z0 = float(np.nanmin(pts["z"]))
    else:
        z0 = 0.0
    origin = {"x": float(math.floor(np.nanmin(np.concatenate(xs)))),
              "y": float(math.floor(np.nanmin(np.concatenate(ys)))), "z": z0}

    def shift(df: Optional[pd.DataFrame]) -> Optional[pd.DataFrame]:
        if df is None:
            return None
        attrs = dict(df.attrs)
        df = df.copy()
        df["x"] = df["x"] - origin["x"]
        df["y"] = df["y"] - origin["y"]
        if "z" in df.columns:
            df["z"] = df["z"] - origin["z"]
        df.attrs.update(attrs)
        return df

    if walk.orthophoto is not None:
        e = walk.orthophoto["extent"]
        walk.orthophoto["extent"] = {
            "xmin": e["xmin"] - origin["x"], "xmax": e["xmax"] - origin["x"],
            "ymin": e["ymin"] - origin["y"], "ymax": e["ymax"] - origin["y"],
        }
    for name in _SPATIAL:
        setattr(walk, name, shift(getattr(walk, name)))
    walk.features = {name: shift(df) for name, df in walk.features.items()}
    walk.origin = origin


def _png_bytes(pixels: np.ndarray) -> bytes:
    """Encode an 8-bit RGB or RGBA array (height, width, bands) as a PNG.

    Writes only IHDR, IDAT and IEND, so the file carries pixels and nothing
    else.
    """
    height, width, bands = pixels.shape
    color_type = {3: 2, 4: 6}[bands]

    def chunk(kind: bytes, data: bytes) -> bytes:
        return (struct.pack(">I", len(data)) + kind + data
                + struct.pack(">I", zlib.crc32(kind + data) & 0xFFFFFFFF))

    raw = np.concatenate([np.zeros((height, 1), np.uint8),
                          pixels.reshape(height, width * bands)], axis=1).tobytes()
    header = struct.pack(">IIBBBBB", width, height, 8, color_type, 0, 0, 0)
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", header)
            + chunk(b"IDAT", zlib.compress(raw, 9)) + chunk(b"IEND", b""))


def png_chunks(png: bytes) -> List[str]:
    """PNG chunk types in file order."""
    if png[:8] != b"\x89PNG\r\n\x1a\n":
        raise ValueError("not a PNG file")
    types, i = [], 8
    while i + 8 <= len(png):
        length = struct.unpack(">I", png[i:i + 4])[0]
        types.append(png[i + 4:i + 8].decode("latin-1"))
        i += 12 + length
    return types

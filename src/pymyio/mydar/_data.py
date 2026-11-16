"""The real myDAR iPhone walk that ships with myIO, in local coordinates."""

from __future__ import annotations

import json
import lzma
import math
from importlib.resources import files
from typing import Any, Dict

import numpy as np
import pandas as pd

from ._read import MydarWalk, mydar_class_name

_DATA = files("pymyio.mydar") / "data"
_CLOUD_FILE = "mydar-iphone-walk-cloud.bin"
_CLOUD_MAGIC = b"MYDARPC1"
_TABLES = ("points", "terrain", "track", "track_points", "gps_fixes", "pins",
           "accuracy", "trajectory", "mesh_vertices", "mesh_faces")


def mydar_iphone_walk() -> MydarWalk:
    """A real myDAR iPhone walk, in local coordinates.

    Ryan Morton's outdoor walk of 2026-11-15: about 50 seconds and 25 m of
    track, recorded with the myDAR iPhone app and processed from the phone's
    capture files with the myDAR CLI at autodar commit ``5f3aeb4``. It holds
    6,000 of the walk's 887,038 LiDAR points with their classes (vegetation
    split by height) and per-point sigma, the DEM, the orthophoto, the phone's
    scene mesh (11,219 triangles with vertex colors), the track, 49 GPS fixes
    with residuals, the accuracy figures and the trajectory. It is the same
    data as myIO's ``mydar_iphone_walk``.

    The walk is in local coordinates only, moved there by subtraction (no
    rotation or scaling): x and y are meters from the walk's south-west corner
    and z is height above the lowest DEM (ground) cell. The mesh was converted
    from the phone's east-north-up frame into the project CRS before the same
    shift. The subtracted origin,
    the project CRS and the feature layers are not included (``origin`` values
    are NaN, ``crs`` is ``None``, ``features`` is empty). ``sigma_m``,
    classes, the accuracy figures, GPS residuals and the trajectory (meters
    east, north and up of the first GPS fix) are as measured.

    Needs pandas only, not the readers' packages.
    """
    meta = json.loads((_DATA / "walk.json").read_text(encoding="utf-8"))
    tables: Dict[str, Any] = {}
    for name in _TABLES:
        with (_DATA / f"{name}.csv.gz").open("rb") as fh:
            tables[name] = pd.read_csv(fh, compression="gzip", float_precision="round_trip",
                                       keep_default_na=False, na_values=[""])
    tables["points"].attrs["n_total"] = meta["points_n_total"]
    tables["terrain"].attrs["cell_size"] = meta["terrain_cell_size"]
    faces = tables.pop("mesh_faces")[["a", "b", "c"]].to_numpy(dtype=np.int64)
    mesh = {"vertices": tables.pop("mesh_vertices"), "faces": faces,
            "n_triangles_total": meta["mesh_n_triangles_total"]}
    e, size = meta["orthophoto_extent"], meta["orthophoto_size"]
    return MydarWalk(
        **tables,
        features={},
        mesh=mesh,
        orthophoto={
            "png": (_DATA / "orthophoto.png").read_bytes(),
            "extent": dict(zip(("xmin", "xmax", "ymin", "ymax"), e)),
            "size": {"width": int(size[0]), "height": int(size[1])},
        },
        crs=None,
        origin={"x": math.nan, "y": math.nan, "z": math.nan},
    )


def mydar_iphone_cloud() -> pd.DataFrame:
    """The bundled walk's point cloud: 500,000 of its 887,038 points.

    Same local coordinates as :func:`mydar_iphone_walk`, for the 3D view
    (:func:`mydar_cloud_view`). It is myIO's ``inst/extdata`` cloud file:
    x, y and z to a fraction of a millimeter, colors as 8-bit RGB, and sigma
    to about 4% of its value. Returns ``x``, ``y``, ``z``, ``class``,
    ``class_name``, ``sigma_m``, ``source``, ``r``, ``g`` and ``b``.
    """
    ref = _DATA / _CLOUD_FILE
    if not ref.is_file():
        raise RuntimeError(
            "mydar_iphone_cloud(): the bundled cloud file is missing from this installation."
        )
    with ref.open("rb") as fh:
        return _read_cloud(fh.read())


# Binary cloud file (xz-compressed), the format myIO's mydar_write_cloud() writes:
#   "MYDARPC1", n (int32), bbox (6 float64: xmin xmax ymin ymax zmin zmax),
#   then n Uint16 x, n Uint16 y, n Uint16 z (scaled to bbox), n Uint8 r, g, b,
#   n Uint8 class, n Uint8 sigma (log scale as in the pointcloud payload),
#   n Uint8 source (0 LiDAR, 1 camera). Little-endian.
def _read_cloud(compressed: bytes) -> pd.DataFrame:
    raw = lzma.decompress(compressed)
    if raw[:8] != _CLOUD_MAGIC:
        raise ValueError("mydar_iphone_cloud(): not a myDAR cloud file.")
    n = int(np.frombuffer(raw, "<i4", 1, 8)[0])
    bbox = np.frombuffer(raw, "<f8", 6, 12)
    offset = 60

    def take(dtype: str) -> np.ndarray:
        nonlocal offset
        out = np.frombuffer(raw, dtype, n, offset)
        offset += n * np.dtype(dtype).itemsize
        return out.astype(np.int64)

    def scale(v: np.ndarray, lo: float, hi: float) -> np.ndarray:
        return lo + v / 65535 * (hi - lo)

    x = scale(take("<u2"), bbox[0], bbox[1])
    y = scale(take("<u2"), bbox[2], bbox[3])
    z = scale(take("<u2"), bbox[4], bbox[5])
    r, g, b, cls = take("u1"), take("u1"), take("u1"), take("u1")
    sigma = 10 ** (take("u1") / 255 * 4 - 3)
    source = np.where(take("u1") == 1, "camera", "LiDAR")
    return pd.DataFrame({
        "x": x, "y": y, "z": z, "class": cls, "class_name": mydar_class_name(cls),
        "sigma_m": sigma, "source": source, "r": r, "g": g, "b": b,
    })

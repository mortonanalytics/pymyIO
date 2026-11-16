"""Read and plot myDAR walks (parity with myIO's ``read_mydar_*()`` and
``mydar_*_view()`` functions).

The views and the bundled walk need pandas. The readers also need laspy
(with lazrs), rasterio, pyogrio and shapely; install them all with
``pip install 'pymyio[mydar]'``.
"""

try:
    import pandas  # noqa: F401
except ImportError:  # pragma: no cover - exercised only without pandas
    raise ImportError(
        "pymyio.mydar needs pandas. Install the myDAR extra with: pip install 'pymyio[mydar]'"
    ) from None

from ._data import mydar_iphone_cloud, mydar_iphone_walk
from ._read import (
    MYDAR_CLASSES,
    MydarWalk,
    read_mydar_gpkg,
    read_mydar_orthophoto,
    read_mydar_points,
    read_mydar_terrain,
    read_mydar_trajectory,
    read_mydar_walk,
)
from ._views import (
    MydarDashboard,
    mydar_accuracy_view,
    mydar_cloud_view,
    mydar_dashboard,
    mydar_gps_view,
    mydar_orthophoto_view,
    mydar_plan_view,
    mydar_profile,
    mydar_profile_view,
    mydar_sigma_view,
    mydar_terrain_view,
    mydar_trajectory_view,
)

__all__ = [
    "MYDAR_CLASSES",
    "MydarDashboard",
    "MydarWalk",
    "mydar_accuracy_view",
    "mydar_cloud_view",
    "mydar_dashboard",
    "mydar_gps_view",
    "mydar_iphone_cloud",
    "mydar_iphone_walk",
    "mydar_orthophoto_view",
    "mydar_plan_view",
    "mydar_profile",
    "mydar_profile_view",
    "mydar_sigma_view",
    "mydar_terrain_view",
    "mydar_trajectory_view",
    "read_mydar_gpkg",
    "read_mydar_orthophoto",
    "read_mydar_points",
    "read_mydar_terrain",
    "read_mydar_trajectory",
    "read_mydar_walk",
]

# myDAR walks

myDAR maps a site from a phone walk. Each walk produces a point cloud, a DEM,
an orthophoto, a GeoPackage with the track, GPS fixes and accuracy figures,
and the device trajectory. `pymyio.mydar` reads those files into pandas data
frames and plots them with the same functions as R-myIO.

## Reading a walk

`read_mydar_walk()` reads a walk output folder into a `MydarWalk`:

| File | Attribute | Reader |
|---|---|---|
| `walk.copc.laz` | `points` | `read_mydar_points()` (laspy with lazrs) |
| `terrain.tif` | `terrain` | `read_mydar_terrain()` (rasterio) |
| `orthophoto.tif` | `orthophoto` | `read_mydar_orthophoto()` (rasterio) |
| `walk.gpkg` | `track`, `track_points`, `gps_fixes`, `pins`, `features`, `accuracy` | `read_mydar_gpkg()` (pyogrio, shapely) |
| `trajectory.csv` | `trajectory` | `read_mydar_trajectory()` |

Install the readers' packages with `pip install 'pymyio[mydar]'`. A reader
called without them names the missing package and that command.

```python
from pymyio.mydar import read_mydar_walk

walk = read_mydar_walk("path/to/walk", max_points=20000)
walk
```

The reader keeps `max_points` of the cloud (every k-th point in file order,
which keeps the relative density across the walk; `math.inf` keeps them all)
and records the full count in `walk.points.attrs["n_total"]`. The DEM is
averaged down when it has more than `max_cells` cells. By default every table
moves to walk-local coordinates by subtraction: x and y become meters from
the walk's south-west corner and z the height above the lowest ground cell
(`walk.origin` holds the shift). The orthophoto comes back as a PNG holding
only its pixels, with its extent in the same coordinates.

## The bundled walk

`mydar_iphone_walk()` returns a real outdoor walk recorded with the myDAR
iPhone app and processed with the myDAR CLI (autodar commit `a1388d8`): about
50 seconds and 25 m of track. It is the same data R-myIO ships as
`mydar_iphone_walk`, shown in local coordinates only. Its x and y were moved
to meters from the walk's south-west corner and its heights to height above
the lowest ground cell, by subtraction only. The subtracted origin and the
project CRS are not included, and the orthophoto holds pixels only. Classes,
point sigma, GPS residuals and the accuracy figures are as measured.

It keeps 6,000 of the walk's 887,038 points for the SVG charts.
`mydar_iphone_cloud()` returns 500,000 of them for the 3D view. Neither needs
the readers' packages, only pandas.

```python
from pymyio.mydar import mydar_iphone_cloud, mydar_iphone_walk

walk = mydar_iphone_walk()
ym = (walk.track["y"].min() + walk.track["y"].max()) / 2
line = {"from": (0, ym), "to": (22, ym)}  # a profile line across the track
```

## The views

Each view returns a `MyIO` chart, so it displays in a notebook cell and takes
the usual setters.

### 3D point cloud

The cloud in 3D, the way the myDAR app's Results screen shows it: drag to
orbit, shift-drag to pan, scroll or pinch to zoom, or switch to 2D for a
top-down plan with a scale bar. The chips color the points by camera color,
class, height or sigma and turn the orthophoto under them on and off. The
card gives the walk's two accuracy figures, Shape and Map, separately.

```python
from pymyio.mydar import mydar_cloud_view

mydar_cloud_view(walk, points=mydar_iphone_cloud())
```

### Plan view

The orthophoto with the track and the profile line over it, drawn to scale
(`set_equal_aspect()`), with the accuracy figures in the corner. `points=True`
adds the points colored by class. `mydar_orthophoto_view()` shows the
orthophoto alone.

```python
from pymyio.mydar import mydar_plan_view

mydar_plan_view(walk, profile=line)
```

### Terrain

The DEM as a `raster` layer, colored by height and shaded by a hillshade.
Hover a cell for its height.

```python
from pymyio.mydar import mydar_terrain_view

mydar_terrain_view(walk, azimuth=315, altitude=45)
```

### Profile

Points within a corridor along a line, as height against distance along the
line, with the DEM height along the same line. `mydar_profile()` returns the
corridor points as a data frame. Python spells R's `from` argument `from_`.

```python
from pymyio.mydar import mydar_profile, mydar_profile_view

mydar_profile_view(walk, from_=line["from"], to=line["to"], width=0.5)
mydar_profile(walk, from_=line["from"], to=line["to"]).head()
```

### Uncertainty and QA

```python
from pymyio.mydar import (mydar_accuracy_view, mydar_gps_view, mydar_sigma_view,
                          mydar_trajectory_view)

mydar_trajectory_view(walk)
mydar_gps_view(walk)
mydar_sigma_view(walk)
mydar_accuracy_view(walk)
```

`mydar_gps_view()` plots each GPS fix's residual against the fused track,
next to the 95% residual the processing expected. `sigma_m` is the per-point
1-sigma per axis that the cloud stores, on a log10 axis because camera points
(when a walk has them) run to meters while LiDAR stays near 2-3 cm; this walk
is LiDAR only. The accuracy chart puts the shape figure (how well distances
inside the walk hold) next to map position (where the walk sits on the map).
Here the map position comes from phone GPS, so it is far larger than the
shape figure within 5 m.

## All at once

`mydar_dashboard()` lays out the views on one page in the app's order: the
3D cloud and the plan view first, then the profile, then the quality charts.
With `plan_points=True`, brushing the plan view lights up the same points on
the profile. Hovering the uncertainty or GPS chart shows a cursor at the same
moment on the other; the GPS chart appears when the walk has GPS residuals.

```python
from pymyio.mydar import mydar_dashboard

dash = mydar_dashboard(walk, points=mydar_iphone_cloud())
dash                      # in a notebook: the page in an iframe
dash.save("walk.html")    # one self-contained HTML file
```

The 3D view is a WebGL canvas, so it is not part of PNG or SVG export.

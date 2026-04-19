# R → Python API map

Every R export has a Python equivalent with matching semantics. The JSON
config both wrappers produce is identical (byte-for-byte where possible), so
the same engine renders both.

## Chart construction

| R export | Python equivalent |
|---|---|
| `myIO()` | `MyIO()` |
| `addIoLayer()` | `MyIO.add_layer()` |
| `linkCharts()` | `pymyio.link_charts()` (module-level) |
| `setLinked()` | n/a — Crosstalk-specific; use `link_charts()` |

## Chart-level setters

| R export | Python equivalent |
|---|---|
| `setMargin()` | `MyIO.set_margin()` |
| `setAxisFormat()` | `MyIO.set_axis_format()` |
| `setAxisLimits()` | `MyIO.set_axis_limits()` |
| `setColorScheme()` | `MyIO.set_color_scheme()` |
| `setReferenceLines()` | `MyIO.set_reference_lines()` |
| `setTheme()` | `MyIO.set_theme()` |
| `setTransitionSpeed()` | `MyIO.set_transition_speed()` |
| `setToolTipOptions()` | `MyIO.set_tooltip_options()` |
| `defineCategoricalAxis()` | `MyIO.define_categorical_axis()` |
| `flipAxis()` | `MyIO.flip_axis()` |
| `suppressLegend()` | `MyIO.suppress_legend()` |
| `suppressAxis()` | `MyIO.suppress_axis()` |

## Interactions

| R export | Python equivalent |
|---|---|
| `setBrush()` | `MyIO.set_brush()` |
| `setAnnotation()` | `MyIO.set_annotation()` |
| `setExportOptions()` | `MyIO.set_export_options()` |
| `setFacet()` | `MyIO.set_facet()` |
| `setLayerOpacity()` | `MyIO.set_layer_opacity()` |
| `setSlider()` | `MyIO.set_slider()` |
| `setToggle()` | `MyIO.set_toggle()` |
| `setLinkedCursor()` | `MyIO.set_linked_cursor()` |
| `dragPoints()` | `MyIO.drag_points()` |

## Shiny bindings

| R export | Python equivalent |
|---|---|
| `myIOOutput` | `pymyio.shiny.output_myio` |
| `renderMyIO` | `pymyio.shiny.render_myio` |
| — | `pymyio.shiny.reactive_brush` (thin wrapper over `shinywidgets.reactive_read`) |
| — | `pymyio.shiny.reactive_annotated` |
| — | `pymyio.shiny.reactive_rollover` |
| — | `pymyio.shiny.example_app()` |

## Diagnostics

| R export | Python equivalent |
|---|---|
| `myIO_last_error()` | `MyIOWidget.last_error` traitlet |

## Data containers accepted

Both `MyIO(data=…)` and `add_layer(data=…)` accept:

- pandas `DataFrame`
- polars `DataFrame` (uses `.to_dicts()`)
- `list[dict]`
- any object exposing `.to_dict(orient="records")`

## Rendering

| Use case | Python |
|---|---|
| Display in Jupyter / VS Code / marimo | bare expression in a cell |
| Programmatic widget | `chart.render()` → `MyIOWidget` |
| JSON config only | `chart.to_config()` → `dict` |
| Static HTML | `pymyio.to_standalone_html(chart)` |

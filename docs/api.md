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

## LLM tool calling

Schema-backed helpers for letting an LLM propose and validate myIO specs.
Both the Pythonic names and the `myio_*` R-parity aliases are exported from
`pymyio`.

| R export | Python equivalent |
|---|---|
| `myio_list_chart_types()` | `pymyio.list_chart_types()` (alias `myio_list_chart_types`) |
| `myio_chart_schema()` | `pymyio.get_chart_schema()` (alias `myio_chart_schema`) |
| `myio_validate_spec()` | `pymyio.validate_spec()` (alias `myio_validate_spec`) |
| `myio_list_functions()` | `pymyio.list_functions()` (alias `myio_list_functions`) |
| `myio_function_signature()` | `pymyio.get_function_signature()` (alias `myio_function_signature`) |
| `myio_validate_call()` | `pymyio.validate_call()` (alias `myio_validate_call`) |
| `myio_load_schema()` | `pymyio.load_schema()` |

Error objects use stable `code` values (`pymyio.ERROR_CODES`) shared with the
R and JS implementations.

These helpers run **in-process** — call them directly, or wrap them as tools
in your own agent loop. If you instead want a ready-to-run **MCP server** for
any MCP-capable agent, the myIO sibling already ships one in JavaScript:
[`@mortonanalytics/myio-mcp`](https://github.com/mortonanalytics/myIO/tree/main/mcp)
(Node, stdio transport, same six tools). It is driven by the same generated
`myio-schema.json`, so R, JS, and Python validate identically. See the
[myIO LLM tool-calling guide](https://mortonanalytics.github.io/myIO/articles/llm-tool-calling.html).

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

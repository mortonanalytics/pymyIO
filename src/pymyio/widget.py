"""anywidget binding for the vendored myIO d3 engine."""

from __future__ import annotations

import pathlib
from typing import Any, Mapping, Optional, Union

import anywidget
import traitlets

_HERE = pathlib.Path(__file__).parent
_STATIC = _HERE / "static"


class MyIOWidget(anywidget.AnyWidget):
    """Render a myIO chart config in any anywidget-compatible frontend.

    The widget loads the vendored ``myIOapi.js`` engine plus the d3 bundle
    and dispatches a config dict produced by :class:`pymyio.MyIO`.
    """

    _esm = _STATIC / "widget.js"
    _css = _STATIC / "style.css"

    config = traitlets.Dict().tag(sync=True)
    width = traitlets.Union([traitlets.Int(), traitlets.Unicode()], default_value="100%").tag(sync=True)
    height = traitlets.Union([traitlets.Int(), traitlets.Unicode()], default_value="400px").tag(sync=True)

    last_error = traitlets.Dict(allow_none=True, default_value=None).tag(sync=True)
    brushed = traitlets.Dict(allow_none=True, default_value=None).tag(sync=True)
    annotated = traitlets.Dict(allow_none=True, default_value=None).tag(sync=True)
    rollover = traitlets.Dict(allow_none=True, default_value=None).tag(sync=True)

    # Private override for the asset base URL resolved by widget.js. Left
    # empty by default; host integrations may set it when import.meta.url
    # resolves incorrectly (nbconvert-embedded HTML, Colab sandboxed iframe).
    # Underscore prefix signals "not part of the user-facing API."
    _base_url = traitlets.Unicode("").tag(sync=True)

    def __init__(
        self,
        config: dict,
        width: Union[int, str] = "100%",
        height: Union[int, str] = "400px",
        **kwargs: Any,
    ):
        super().__init__(config=config, width=width, height=height, **kwargs)

    def update_options(
        self,
        updates: Optional[Mapping[str, Mapping[str, Any]]] = None,
        /,
        **kwargs: Mapping[str, Any],
    ) -> "MyIOWidget":
        """Merge new options into existing layers of the drawn chart, in place.

        Python counterpart of R myIO's ``updateMyIOOptions()``. Only the
        supplied option names change; every other option keeps its value, and
        the chart is updated without a full redraw (a field chart keeps its
        playback time, selection and metric window across overlay changes; a
        point cloud keeps its camera). Layers are matched by ``label``; unknown
        labels are ignored by the browser.

        Pass labels as keyword arguments, or as a dict when a label is not a
        valid identifier::

            widget.update_options({"Point cloud": {"profile": [[0, 0], [10, 5]]}})
            widget.update_options(match={"overlays": {"shape": True}})

        In Shiny for Python, call it on the rendered widget
        (``chart.widget.update_options(...)``).
        """
        from .chart import _validate_field_options

        merged: dict = {}
        if updates is not None:
            if not isinstance(updates, Mapping):
                raise ValueError(
                    "update_options(): `updates` must be a dict of label -> options."
                )
            merged.update(updates)
        merged.update(kwargs)
        if not merged or not all(isinstance(k, str) and k for k in merged):
            raise ValueError(
                "update_options(): supply one or more named `label = dict(...)` updates."
            )

        layers = []
        for label, options in merged.items():
            if (not isinstance(options, Mapping) or not options
                    or not all(isinstance(k, str) and k for k in options)):
                raise ValueError(
                    f"update_options(): update for layer '{label}' must be a "
                    "named dict of options."
                )
            layers.append({
                "label": label,
                "options": _validate_field_options(options, "update_options"),
            })
        self.send({"type": "myio:proxy-options", "layers": layers})
        return self

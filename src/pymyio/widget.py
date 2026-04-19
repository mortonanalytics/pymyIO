"""anywidget binding for the vendored myIO d3 engine."""

from __future__ import annotations

import pathlib
from typing import Any, Union

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

    def __init__(
        self,
        config: dict,
        width: Union[int, str] = "100%",
        height: Union[int, str] = "400px",
        **kwargs: Any,
    ):
        super().__init__(config=config, width=width, height=height, **kwargs)

"""Self-contained HTML export for pymyIO charts.

``to_standalone_html`` produces an HTML string that renders a chart without
an anywidget runtime or Python kernel. Works in Quarto, nbconvert, email
attachments, and static hosting. Does NOT depend on ``ipywidgets.embed`` —
it emits the same ``myIOchart`` constructor call that widget.js uses at
runtime, just with assets inlined or bundled alongside the HTML.

Design doc reference: Slice 3. Contract: §Standalone vs widget path.
"""

from __future__ import annotations

import html
import json
import uuid
import warnings
from importlib.resources import files
from typing import Any, Mapping, Tuple, Union

__all__ = ["to_standalone_html", "MyIOStaticWarning"]


class MyIOStaticWarning(UserWarning):
    """Emitted when ``to_standalone_html`` degrades chart capabilities.

    Two triggers today: (1) the chart was built with interactive-only
    features (brush, annotation, drag) that require a Python kernel to
    round-trip events; (2) inline-mode output exceeds a 2 MB soft ceiling.
    """


_ASSET_KEYS: Tuple[str, ...] = (
    "myIOapi.js",
    "style.css",
    "lib/d3.min.js",
    "lib/d3-hexbin.js",
    "lib/d3-sankey.min.js",
)

_INLINE_SIZE_WARN_BYTES = 2 * 1024 * 1024

_INTERACTIVE_KEYS = ("brush", "annotation")


def to_standalone_html(
    chart_or_config: Any,
    *,
    width: Union[int, str] = "100%",
    height: Union[int, str] = "400px",
    include_assets: str = "inline",
    title: str = None,
) -> Union[str, Tuple[str, dict]]:
    """Render a pymyIO chart to a self-contained HTML page.

    Parameters
    ----------
    chart_or_config
        Either a :class:`pymyio.MyIO` builder or a config ``dict``
        (what ``MyIO.to_config()`` returns).
    width, height
        Chart dimensions; int values are treated as pixels.
    include_assets
        ``"inline"`` (default) embeds all assets into one HTML string.
        ``"bundled"`` returns ``(html_str, assets_dict)`` where the assets
        dict maps relative paths to byte contents for the caller to write
        alongside the HTML.
    title
        Optional ``<title>`` text; defaults to ``"pymyIO chart"``.

    Returns
    -------
    str
        For ``include_assets="inline"``.
    tuple[str, dict[str, bytes]]
        For ``include_assets="bundled"``.

    Raises
    ------
    ValueError
        If ``include_assets`` is not one of ``{"inline", "bundled"}``.
    RuntimeError
        If a required bundled asset is missing from the wheel.
    """
    if include_assets not in ("inline", "bundled"):
        raise ValueError(
            "include_assets must be 'inline' or 'bundled', "
            f"got {include_assets!r}."
        )

    # Duck-type on the builder contract: anything with a callable .to_config()
    # is treated as a MyIO chart. isinstance() would be brittle under test
    # tooling that clears sys.modules (e.g. the footgun regression test) and
    # unnecessarily couples standalone.py to the chart module.
    to_config = getattr(chart_or_config, "to_config", None)
    if callable(to_config):
        cfg = to_config()
    else:
        cfg = dict(chart_or_config)

    interactive = _has_interactive_only_features(cfg)
    if interactive:
        warnings.warn(
            f"Chart uses interactive-only features {interactive}; "
            "static HTML renders the UI but callbacks no-op without a "
            "Python kernel.",
            MyIOStaticWarning,
            stacklevel=2,
        )

    assets = _load_assets()
    uid = uuid.uuid4().hex[:12]
    cfg_json = _safe_json(cfg)
    page_title = html.escape(title or "pymyIO chart")
    width_js, height_js = _js_dims(width, height)

    if include_assets == "inline":
        html_str = _render_inline(
            uid, cfg_json, page_title, width, height, width_js, height_js, assets,
        )
        if len(html_str.encode("utf-8")) > _INLINE_SIZE_WARN_BYTES:
            warnings.warn(
                "Inline HTML exceeds 2 MB; pass include_assets='bundled' to "
                "emit sidecar assets instead.",
                MyIOStaticWarning,
                stacklevel=2,
            )
        return html_str

    html_str = _render_bundled(
        uid, cfg_json, page_title, width, height, width_js, height_js,
    )
    return html_str, dict(assets)


# ---- helpers ---------------------------------------------------------------


def _load_assets() -> dict:
    """Read the five frozen assets from ``pymyio/static/`` in the wheel.

    Uses ``importlib.resources.files`` so this works inside zipped wheels
    as well as editable installs. Raises ``RuntimeError`` if any asset is
    missing — that is a packaging bug, not a user error.
    """
    root = files("pymyio") / "static"
    out: dict = {}
    for key in _ASSET_KEYS:
        ref = root.joinpath(*key.split("/"))
        if not ref.is_file():
            raise RuntimeError(
                f"pymyIO packaging error: required asset '{key}' is missing "
                f"from the installed wheel (expected at pymyio/static/{key})."
            )
        out[key] = ref.read_bytes()
    return out


def _has_interactive_only_features(cfg: Mapping[str, Any]) -> list:
    """Return the list of interactive-only feature names present in ``cfg``.

    Used to decide whether to emit ``MyIOStaticWarning`` — the chart will
    still render, but brush/annotation/drag callbacks have no kernel to
    round-trip to.
    """
    inter = cfg.get("interactions") or {}
    found: list = []
    for key in _INTERACTIVE_KEYS:
        node = inter.get(key) or {}
        if isinstance(node, Mapping) and node.get("enabled"):
            found.append(key)
    if inter.get("dragPoints"):
        found.append("dragPoints")
    return found


def _safe_json(cfg: Mapping[str, Any]) -> str:
    r"""Serialize ``cfg`` to JSON safe for inlining into a ``<script>`` island.

    Closes the ``</script>`` / ``</style>`` escape hole: any string value
    containing a closing tag sequence would otherwise terminate the
    enclosing script element. ``ensure_ascii`` keeps Unicode values inert
    and the ``</`` → ``<\/`` pass handles the closing-tag case.
    """
    return json.dumps(cfg, default=str, ensure_ascii=True).replace("</", "<\\/")


def _js_dims(width: Union[int, str], height: Union[int, str]) -> Tuple[str, str]:
    """Render width/height values as JavaScript literal tokens.

    Integer-like inputs produce bare numbers (``600``). Strings like
    ``"100%"`` produce quoted, JSON-escaped JS strings (``"100%"``).
    """

    def one(v: Union[int, str]) -> str:
        if isinstance(v, (int, float)) and not isinstance(v, bool):
            return str(int(v))
        return json.dumps(str(v))

    return one(width), one(height)


def _escape_script_body(s: str) -> str:
    """Escape any literal closing-tag sequence inside an inline asset.

    Any ``</`` inside a ``<script>`` or ``<style>`` body would close the
    enclosing tag and leak the rest of the asset into the document. JS and
    CSS tolerate the backslash variant.
    """
    return s.replace("</", "<\\/")


def _render_inline(
    uid: str,
    cfg_json: str,
    page_title: str,
    width: Union[int, str],
    height: Union[int, str],
    width_js: str,
    height_js: str,
    assets: dict,
) -> str:
    """Assemble the single-page HTML by concatenating chunks.

    Cannot use ``str.format`` or f-strings over the asset bytes — the
    vendored d3 and engine files contain ``{`` literals in function bodies
    and CSS rules that would raise ``KeyError`` or silently rewrite braces.
    """
    def decoded(key: str) -> str:
        return assets[key].decode("utf-8")

    css = _escape_script_body(decoded("style.css"))
    d3 = _escape_script_body(decoded("lib/d3.min.js"))
    d3hex = _escape_script_body(decoded("lib/d3-hexbin.js"))
    d3sank = _escape_script_body(decoded("lib/d3-sankey.min.js"))
    engine = _escape_script_body(decoded("myIOapi.js"))

    w_css = html.escape(str(width))
    h_css = html.escape(str(height))

    init = (
        "(function(){"
        "var el=document.getElementById('pymyio-chart-" + uid + "');"
        "var cfg=JSON.parse(document.getElementById('pymyio-config-" + uid
        + "').textContent);"
        "new window.myIOchart({element:el,config:cfg,width:"
        + width_js + ",height:" + height_js + "});"
        "})();"
    )

    parts = [
        '<!doctype html><html><head><meta charset="utf-8">',
        f"<title>{page_title}</title>",
        f"<style>{css}</style></head><body>",
        f'<div id="pymyio-chart-{uid}" class="pymyio-chart" '
        f'style="width:{w_css};height:{h_css}"></div>',
        f'<script type="application/json" id="pymyio-config-{uid}">'
        f"{cfg_json}</script>",
        f"<script>{d3}</script>",
        f"<script>{d3hex}</script>",
        f"<script>{d3sank}</script>",
        f"<script>{engine}</script>",
        f"<script>{init}</script>",
        "</body></html>",
    ]
    return "".join(parts)


def _render_bundled(
    uid: str,
    cfg_json: str,
    page_title: str,
    width: Union[int, str],
    height: Union[int, str],
    width_js: str,
    height_js: str,
) -> str:
    """Assemble a page that references assets by relative path.

    The caller receives the five assets as bytes and must write them to
    the same directory as the HTML (preserving the ``lib/`` subpath).
    """
    w_css = html.escape(str(width))
    h_css = html.escape(str(height))
    init = (
        "(function(){"
        "var el=document.getElementById('pymyio-chart-" + uid + "');"
        "var cfg=JSON.parse(document.getElementById('pymyio-config-" + uid
        + "').textContent);"
        "new window.myIOchart({element:el,config:cfg,width:"
        + width_js + ",height:" + height_js + "});"
        "})();"
    )
    parts = [
        '<!doctype html><html><head><meta charset="utf-8">',
        f"<title>{page_title}</title>",
        '<link rel="stylesheet" href="style.css">',
        "</head><body>",
        f'<div id="pymyio-chart-{uid}" class="pymyio-chart" '
        f'style="width:{w_css};height:{h_css}"></div>',
        f'<script type="application/json" id="pymyio-config-{uid}">'
        f"{cfg_json}</script>",
        '<script src="lib/d3.min.js"></script>',
        '<script src="lib/d3-hexbin.js"></script>',
        '<script src="lib/d3-sankey.min.js"></script>',
        '<script src="myIOapi.js"></script>',
        f"<script>{init}</script>",
        "</body></html>",
    ]
    return "".join(parts)

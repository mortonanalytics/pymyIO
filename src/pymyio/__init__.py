from .chart import (
    ALLOWED_TYPES,
    COMPATIBILITY_GROUPS,
    OKABE_ITO_PALETTE,
    VALID_COMBINATIONS,
    MyIO,
    link_charts,
)
from .standalone import MyIOStaticWarning, to_standalone_html
from .widget import MyIOWidget

__all__ = [
    "MyIO",
    "MyIOWidget",
    "MyIOStaticWarning",
    "ALLOWED_TYPES",
    "VALID_COMBINATIONS",
    "COMPATIBILITY_GROUPS",
    "OKABE_ITO_PALETTE",
    "link_charts",
    "to_standalone_html",
]

try:
    from ._version import __version__
except ImportError:
    from importlib.metadata import PackageNotFoundError, version
    try:
        __version__ = version("pymyio")
    except PackageNotFoundError:
        __version__ = "0.0.0+unknown"

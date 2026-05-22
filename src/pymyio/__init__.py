from .chart import (
    ALLOWED_TYPES,
    COMPATIBILITY_GROUPS,
    OKABE_ITO_PALETTE,
    VALID_COMBINATIONS,
    MyIO,
    link_charts,
)
from .standalone import MyIOStaticWarning, to_standalone_html
from .tools import (
    ERROR_CODES,
    get_chart_schema,
    get_function_signature,
    list_chart_types,
    list_functions,
    load_schema,
    myio_chart_schema,
    myio_function_signature,
    myio_list_chart_types,
    myio_list_functions,
    myio_validate_call,
    myio_validate_spec,
    validate_call,
    validate_spec,
)
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
    "ERROR_CODES",
    "load_schema",
    "list_chart_types",
    "get_chart_schema",
    "validate_spec",
    "list_functions",
    "get_function_signature",
    "validate_call",
    "myio_list_chart_types",
    "myio_chart_schema",
    "myio_validate_spec",
    "myio_list_functions",
    "myio_function_signature",
    "myio_validate_call",
]

try:
    from ._version import __version__
except ImportError:
    from importlib.metadata import PackageNotFoundError, version
    try:
        __version__ = version("pymyio")
    except PackageNotFoundError:
        __version__ = "0.0.0+unknown"

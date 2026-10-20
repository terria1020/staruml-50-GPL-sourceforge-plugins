"""staruml5 - Mermaid <-> StarUML 5.0 (.uml) conversion, StarUML COM bridge and MCP server.

Core library is pure Python 3.8+ standard library.
"""
__version__ = "0.1.0"

from .api import convert, make_fragment, to_mermaid, list_diagrams  # noqa: F401

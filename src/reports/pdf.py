"""Local HTML -> PDF via WeasyPrint.

WeasyPrint's native libraries (gobject/pango/harfbuzz) live under Homebrew's
prefix on macOS, which is not on dyld's default search path. cffi falls back
to ctypes.util.find_library, whose macOS implementation reads
DYLD_FALLBACK_LIBRARY_PATH from os.environ AT CALL TIME - so extending it
here, before the import, is enough. No launcher/env configuration needed,
which matters because Claude Desktop launches the MCP server itself.
"""
from __future__ import annotations

import os
import sys

_BREW_LIB_DIRS = ("/opt/homebrew/lib", "/usr/local/lib")


def _extend_dyld_fallback() -> None:
    if sys.platform != "darwin":
        return
    current = [p for p in os.environ.get("DYLD_FALLBACK_LIBRARY_PATH", "").split(":") if p]
    for lib_dir in _BREW_LIB_DIRS:
        if lib_dir not in current and os.path.isdir(lib_dir):
            current.append(lib_dir)
    if current:
        os.environ["DYLD_FALLBACK_LIBRARY_PATH"] = ":".join(current)


def html_to_pdf(html: str) -> bytes:
    _extend_dyld_fallback()
    import weasyprint  # deferred: import itself needs the dyld fix above

    return weasyprint.HTML(string=html).write_pdf()

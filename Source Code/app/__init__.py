"""
File2MD — Lightweight local document-to-Markdown converter.

Package entry points:
  - main.py        -> GUI launcher
  - cli.py         -> CLI launcher
  - app.gui.launch -> GUI entry function (for ``python -m app.gui``)
"""

from .config import APP_NAME, APP_VERSION  # noqa: F401

__version__ = APP_VERSION
__app_name__ = APP_NAME

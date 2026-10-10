"""
File2MD — single entry point.

When launched with no command-line arguments, opens the GUI.
When launched with arguments, runs in CLI mode (so the same packaged
binary can be used both interactively and from scripts).

Examples::

    File2MD                       # GUI mode
    File2MD report.pdf            # CLI mode
    File2MD documents/ -r -o md/  # CLI mode
"""

from __future__ import annotations

import sys

from app.config import APP_NAME, APP_VERSION
from app.logger import setup_logging


def _has_cli_args() -> bool:
    """Return True if any argument other than --gui / --cli was passed."""
    args = sys.argv[1:]
    if not args:
        return False
    # Allow explicit --gui to force GUI even with extra args
    if "--gui" in args:
        return False
    return True


def main() -> int:
    logger = setup_logging()

    if _has_cli_args():
        logger.info("%s %s starting (CLI mode via main entry)", APP_NAME, APP_VERSION)
        # Lazy import so the GUI modules are not loaded in CLI-only use.
        from cli import main as cli_main
        return cli_main()

    logger.info("%s %s starting (GUI mode)", APP_NAME, APP_VERSION)
    from app.gui import launch
    return launch()


if __name__ == "__main__":
    sys.exit(main())

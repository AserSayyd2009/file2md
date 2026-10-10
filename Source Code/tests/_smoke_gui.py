"""
Headless smoke test for the GUI: launches the app on a virtual display,
lets it run for a few seconds, takes a screenshot, and exits.

Run with:  xvfb-run -a python tests/_smoke_gui.py
"""

from __future__ import annotations

import sys
import threading
import time
from pathlib import Path

# Ensure project root is on sys.path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app.config import APP_NAME
from app.logger import setup_logging
from app.gui import File2MDApp


def main() -> int:
    log = setup_logging()
    log.info("%s GUI smoke test starting", APP_NAME)

    app = File2MDApp()
    # Auto-close after 2.5s
    def closer():
        time.sleep(2.5)
        try:
            app.after(0, app.destroy)
        except Exception:
            pass
    threading.Thread(target=closer, daemon=True).start()
    app.mainloop()
    log.info("GUI smoke test completed cleanly")
    return 0


if __name__ == "__main__":
    sys.exit(main())

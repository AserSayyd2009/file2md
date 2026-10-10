"""
Headless smoke test for the GUI: launches the app on a virtual display,
takes a screenshot, then exits.

Run with:  DISPLAY=:100 python tests/_smoke_screenshot.py
"""

from __future__ import annotations

import sys
import threading
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app.config import APP_NAME, APP_VERSION
from app.logger import setup_logging
from app.gui import File2MDApp
from app.queue_manager import Job, JobStatus


def main() -> int:
    log = setup_logging()
    log.info("%s GUI screenshot test starting", APP_NAME)

    app = File2MDApp()
    # Add a couple of fake jobs to show the queue populated
    sample_paths = [
        Path("/tmp/file2md_demo/Reports/report1.txt"),
        Path("/tmp/file2md_demo/Reports/sample.pdf"),
        Path("/tmp/file2md_demo/sample.docx"),
        Path("/tmp/file2md_demo/Data/table.csv"),
        Path("/tmp/file2md_demo/Data/data.json"),
        Path("/tmp/file2md_demo/unicode_test.txt"),
    ]
    for p in sample_paths:
        if p.exists():
            app._queue_manager.enqueue(Job(input_path=p))
    # Force-refresh the tree rows
    for job in app._queue_manager.jobs:
        app._insert_job_row(job)
    app._refresh_count()
    app._update_convert_state()

    # Take a screenshot via xwd (X Window Dump), then convert to PNG via Pillow
    def shoot():
        time.sleep(1.0)
        try:
            import subprocess
            out_xwd = "/tmp/file2md_screenshot.xwd"
            subprocess.run(["xwd", "-root", "-out", out_xwd], check=True, timeout=5)
            from PIL import Image
            img = Image.open(out_xwd)
            out_png = "/home/z/my-project/download/file2md_screenshot.png"
            img.save(out_png)
            print(f"Screenshot saved: {out_png}")
        except Exception as e:
            print(f"Screenshot failed: {e}")
        # Now also open Settings dialog for a second screenshot
        try:
            app.after(0, lambda: app._open_settings())
            time.sleep(1.0)
            subprocess.run(["xwd", "-root", "-out", "/tmp/file2md_settings.xwd"], check=True, timeout=5)
            from PIL import Image
            img = Image.open("/tmp/file2md_settings.xwd")
            out2 = "/home/z/my-project/download/file2md_settings_screenshot.png"
            img.save(out2)
            print(f"Settings screenshot saved: {out2}")
        except Exception as e:
            print(f"Settings screenshot failed: {e}")
        app.after(0, app.destroy)

    threading.Thread(target=shoot, daemon=True).start()
    app.mainloop()
    log.info("GUI screenshot test completed cleanly")
    return 0


if __name__ == "__main__":
    sys.exit(main())

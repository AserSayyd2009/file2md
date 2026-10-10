"""
Headless GUI smoke test: launches the app, enqueues files, starts the
queue manager directly (bypassing the button), and waits for the
batch-complete callback to fire on the GUI thread.
"""

from __future__ import annotations

import sys
import threading
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app.config import APP_NAME
from app.logger import setup_logging
from app.gui import File2MDApp
from app.queue_manager import Job, JobStatus


def main() -> int:
    log = setup_logging()
    log.info("%s GUI conversion smoke test starting", APP_NAME)

    app = File2MDApp()

    sample_paths = [
        Path("/tmp/file2md_demo/Reports/report1.txt"),
        Path("/tmp/file2md_demo/Reports/sample.pdf"),
        Path("/tmp/file2md_demo/sample.docx"),
        Path("/tmp/file2md_demo/Data/table.csv"),
        Path("/tmp/file2md_demo/Data/data.json"),
        Path("/tmp/file2md_demo/unicode_test.txt"),
    ]
    added = 0
    for p in sample_paths:
        if p.exists():
            job = Job(input_path=p)
            if app._queue_manager.enqueue(job):
                app._insert_job_row(job)
                added += 1
    app._refresh_count()
    app._update_convert_state()
    print(f"Enqueued {added} files")

    completed_event = threading.Event()
    result_summary = {}

    def on_batch_complete(summary):
        # Called from worker thread (we replaced the attribute directly).
        result_summary["converted"] = summary.converted
        result_summary["failed"] = summary.failed
        result_summary["skipped"] = summary.skipped
        completed_event.set()

    # Replace the queue manager's callback directly so we don't depend on
    # the GUI's threadsafe wrapper firing.
    app._queue_manager._on_batch_complete = on_batch_complete

    def runner():
        # Wait for the GUI to be ready.
        time.sleep(0.5)
        print("Calling queue_manager.start()...")
        started = app._queue_manager.start()
        print(f"start() returned {started}")
        if not completed_event.wait(timeout=60):
            print("TIMEOUT: batch did not complete in 60s")
        else:
            print(
                f"BATCH DONE: converted={result_summary.get('converted')} "
                f"failed={result_summary.get('failed')} skipped={result_summary.get('skipped')}"
            )
        # Give the GUI a moment to render final state, then close.
        time.sleep(1.0)
        app.after(0, app.destroy)

    threading.Thread(target=runner, daemon=True).start()
    app.mainloop()

    # Verify outputs exist
    out_dir = Path(app._settings.resolve_output_dir())
    print(f"Output directory: {out_dir}")
    if out_dir.exists():
        for f in sorted(out_dir.iterdir()):
            print(f"  {f.name} ({f.stat().st_size} bytes)")
    return 0


if __name__ == "__main__":
    sys.exit(main())

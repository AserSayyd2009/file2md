"""Direct test of the QueueManager (no GUI)."""

from __future__ import annotations

import sys
import threading
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app.config import APP_NAME, Settings
from app.logger import setup_logging
from app.queue_manager import Job, JobStatus, QueueManager


def main() -> int:
    log = setup_logging()
    log.info("%s queue manager test starting", APP_NAME)

    settings = Settings(
        output_directory="/tmp/file2md_qm_out",
        include_subfolders=False,
        preserve_structure=False,
        overwrite_existing=False,
        create_unique_filenames=True,
    )

    done_event = threading.Event()

    def on_progress(done, total, name):
        print(f"  progress: {done}/{total} — {name}")

    def on_job_updated(job):
        print(f"  job updated: {job.display_name} -> {job.status.value}")

    def on_batch_complete(summary):
        print(f"BATCH DONE: converted={summary.converted} failed={summary.failed} skipped={summary.skipped}")
        for name, reason in summary.failures:
            print(f"  failed: {name} — {reason}")
        done_event.set()

    qm = QueueManager(
        settings=settings,
        on_progress=on_progress,
        on_job_updated=on_job_updated,
        on_batch_complete=on_batch_complete,
    )

    paths = [
        Path("/tmp/file2md_demo/Reports/report1.txt"),
        Path("/tmp/file2md_demo/Reports/sample.pdf"),
        Path("/tmp/file2md_demo/sample.docx"),
        Path("/tmp/file2md_demo/Data/table.csv"),
        Path("/tmp/file2md_demo/Data/data.json"),
        Path("/tmp/file2md_demo/unicode_test.txt"),
    ]
    for p in paths:
        if p.exists():
            qm.enqueue(Job(input_path=p))

    print(f"Enqueued {len(qm.jobs)} jobs")
    qm.start()
    print("Worker started, waiting for completion...")

    if not done_event.wait(timeout=60):
        print("TIMEOUT")
        qm.cancel_pending()
        qm.wait_until_idle(timeout=5)
        return 1

    print("Output directory:")
    out = Path(settings.output_directory)
    if out.exists():
        for f in sorted(out.iterdir()):
            print(f"  {f.name} ({f.stat().st_size} bytes)")
    return 0


if __name__ == "__main__":
    sys.exit(main())

"""
Queue manager: drives batch conversion on a single worker thread.

Design:
  - One persistent worker thread consumes a FIFO queue of conversion jobs.
  - Status callbacks are invoked from the worker thread; callers that
    touch Tkinter must marshal them via ``widget.after`` / a thread-safe
    event mechanism.
  - Cancellation is cooperative: setting ``cancel_pending=True`` causes
    the worker to stop dequeuing new jobs. The currently running
    MarkItDown conversion is allowed to finish (we never forcibly kill
    the thread, since MarkItDown / pdfplumber do not expose safe cancel).
  - Remaining queued jobs are marked ``Cancelled``.
"""

from __future__ import annotations

import queue
import threading
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Callable, Optional

from .config import Settings
from .converter import ConversionError, Converter
from .file_manager import compute_output_path
from .logger import get_logger
from .utils import write_text_file


log = get_logger("queue")


class JobStatus(str, Enum):
    READY = "Ready"
    CONVERTING = "Converting"
    CONVERTED = "Converted"
    FAILED = "Failed"
    SKIPPED = "Skipped"
    CANCELLED = "Cancelled"


@dataclass
class Job:
    """A single file conversion job."""

    input_path: Path
    input_root: Optional[Path] = None  # for structure preservation
    status: JobStatus = JobStatus.READY
    output_path: Optional[Path] = None
    error_message: str = ""

    @property
    def display_name(self) -> str:
        return self.input_path.name


@dataclass
class BatchSummary:
    total: int = 0
    converted: int = 0
    failed: int = 0
    skipped: int = 0
    cancelled: int = 0
    failures: list[tuple[str, str]] = field(default_factory=list)


# Callback type signatures (kept simple, no fancy typing).
ProgressCallback = Callable[[int, int, str], None]
JobUpdatedCallback = Callable[[Job], None]
BatchCompleteCallback = Callable[[BatchSummary], None]


class QueueManager:
    """Threaded batch converter.

    The GUI (or CLI) enqueues jobs via :meth:`enqueue`, then calls
    :meth:`start`. Status updates flow back through the callbacks provided
    at construction time.
    """

    def __init__(
        self,
        converter: Optional[Converter] = None,
        settings: Optional[Settings] = None,
        *,
        on_progress: Optional[ProgressCallback] = None,
        on_job_updated: Optional[JobUpdatedCallback] = None,
        on_batch_complete: Optional[BatchCompleteCallback] = None,
    ) -> None:
        self._converter = converter or Converter()
        self._settings = settings or Settings()
        self._on_progress = on_progress
        self._on_job_updated = on_job_updated
        self._on_batch_complete = on_batch_complete

        self._queue: queue.Queue[Optional[Job]] = queue.Queue()
        self._worker: Optional[threading.Thread] = None
        self._lock = threading.Lock()
        self._cancel_pending = threading.Event()
        self._idle = threading.Event()
        self._idle.set()

        self._jobs: list[Job] = []
        self._total = 0
        self._done = 0
        self._summary = BatchSummary()

    # ------------------------------------------------------------------ #
    # Queue state
    # ------------------------------------------------------------------ #
    @property
    def jobs(self) -> list[Job]:
        """Snapshot of all jobs currently known to the manager."""
        with self._lock:
            return list(self._jobs)

    @property
    def is_running(self) -> bool:
        return self._worker is not None and self._worker.is_alive()

    @property
    def is_idle(self) -> bool:
        return self._idle.is_set()

    def update_settings(self, settings: Settings) -> None:
        self._settings = settings

    # ------------------------------------------------------------------ #
    # Job management
    # ------------------------------------------------------------------ #
    def enqueue(self, job: Job) -> bool:
        """Add a job to the queue. Returns False if it was a duplicate."""
        with self._lock:
            for existing in self._jobs:
                try:
                    if existing.input_path.resolve() == job.input_path.resolve():
                        return False
                except OSError:
                    if existing.input_path == job.input_path:
                        return False
            self._jobs.append(job)
        self._queue.put(job)
        return True

    def enqueue_many(self, jobs: list[Job]) -> int:
        added = 0
        for j in jobs:
            if self.enqueue(j):
                added += 1
        return added

    def remove_job(self, job: Job) -> bool:
        """Remove a job that has not started yet."""
        with self._lock:
            if job not in self._jobs:
                return False
            if job.status in (JobStatus.CONVERTING, JobStatus.CONVERTED):
                return False
            self._jobs.remove(job)
        # Drain it from the underlying queue if present.
        drained: list[Optional[Job]] = []
        try:
            while True:
                drained.append(self._queue.get_nowait())
        except queue.Empty:
            pass
        for item in drained:
            if item is not None and item is not job:
                self._queue.put(item)
        return True

    def clear_all(self) -> None:
        """Discard every job that is not currently being converted."""
        with self._lock:
            keep: list[Job] = []
            for j in self._jobs:
                if j.status == JobStatus.CONVERTING:
                    keep.append(j)
            self._jobs = keep
        # Drain the queue.
        try:
            while True:
                self._queue.get_nowait()
        except queue.Empty:
            pass

    # ------------------------------------------------------------------ #
    # Run / cancel
    # ------------------------------------------------------------------ #
    def start(self) -> bool:
        """Begin processing queued jobs on a worker thread.

        Returns False if a worker is already running.
        """
        if self.is_running:
            return False
        self._cancel_pending.clear()
        self._idle.clear()
        with self._lock:
            self._total = sum(
                1 for j in self._jobs if j.status == JobStatus.READY
            )
            self._done = 0
            self._summary = BatchSummary(total=self._total)
        self._worker = threading.Thread(
            target=self._run, name="file2md-worker", daemon=True
        )
        self._worker.start()
        return True

    def cancel_pending(self) -> None:
        """Stop processing new jobs. The current conversion finishes."""
        self._cancel_pending.set()

    def wait_until_idle(self, timeout: Optional[float] = None) -> bool:
        return self._idle.wait(timeout)

    # ------------------------------------------------------------------ #
    # Worker loop
    # ------------------------------------------------------------------ #
    def _run(self) -> None:
        log.info("Worker started. %d job(s) queued.", self._total)
        try:
            while True:
                if self._cancel_pending.is_set():
                    break
                try:
                    job = self._queue.get(timeout=0.1)
                except queue.Empty:
                    if self._queue.empty():
                        break
                    continue
                if job is None:
                    break
                if self._cancel_pending.is_set():
                    self._mark_cancelled(job)
                    continue
                if job.status != JobStatus.READY:
                    continue
                self._process_job(job)
            self._drain_cancelled()
        finally:
            self._idle.set()
            log.info(
                "Worker finished. converted=%d failed=%d skipped=%d cancelled=%d",
                self._summary.converted,
                self._summary.failed,
                self._summary.skipped,
                self._summary.cancelled,
            )
            if self._on_batch_complete:
                try:
                    self._on_batch_complete(self._summary)
                except Exception:
                    log.exception("Batch-complete callback raised")

    def _process_job(self, job: Job) -> None:
        job.status = JobStatus.CONVERTING
        self._notify(job)

        try:
            result = self._converter.convert_file(job.input_path)
        except ConversionError as exc:
            job.status = JobStatus.FAILED
            job.error_message = str(exc)
            self._summary.failed += 1
            self._summary.failures.append((job.display_name, str(exc)))
            self._done += 1
            self._notify_progress(job)
            self._notify(job)
            log.warning("Conversion failed: %s — %s", job.input_path, exc)
            return
        except Exception as exc:
            # Defensive: should not happen because converter wraps everything.
            job.status = JobStatus.FAILED
            job.error_message = f"Unexpected error: {exc}"
            self._summary.failed += 1
            self._summary.failures.append((job.display_name, str(exc)))
            self._done += 1
            self._notify_progress(job)
            self._notify(job)
            log.exception("Unexpected error converting %s", job.input_path)
            return

        try:
            output_path = compute_output_path(
                job.input_path,
                Path(self._settings.resolve_output_dir()),
                preserve_structure=self._settings.preserve_structure,
                input_root=job.input_root,
                overwrite=self._settings.overwrite_existing,
                create_unique=self._settings.create_unique_filenames,
            )
        except Exception as exc:
            job.status = JobStatus.FAILED
            job.error_message = f"Could not compute output path: {exc}"
            self._summary.failed += 1
            self._summary.failures.append((job.display_name, str(exc)))
            self._done += 1
            self._notify_progress(job)
            self._notify(job)
            return

        if output_path is None:
            job.status = JobStatus.SKIPPED
            job.output_path = None
            job.error_message = "Output file already exists"
            self._summary.skipped += 1
            self._done += 1
            self._notify_progress(job)
            self._notify(job)
            return

        try:
            write_text_file(output_path, result.markdown)
        except OSError as exc:
            job.status = JobStatus.FAILED
            job.error_message = f"Could not write output file: {exc}"
            self._summary.failed += 1
            self._summary.failures.append((job.display_name, str(exc)))
            self._done += 1
            self._notify_progress(job)
            self._notify(job)
            return

        job.status = JobStatus.CONVERTED
        job.output_path = output_path
        self._summary.converted += 1
        self._done += 1
        self._notify_progress(job)
        self._notify(job)

    # ------------------------------------------------------------------ #
    # Helpers
    # ------------------------------------------------------------------ #
    def _mark_cancelled(self, job: Job) -> None:
        job.status = JobStatus.CANCELLED
        self._summary.cancelled += 1
        self._done += 1
        self._notify_progress(job)
        self._notify(job)

    def _drain_cancelled(self) -> None:
        """Cancel every READY job still in our list once worker stops."""
        with self._lock:
            for job in self._jobs:
                if job.status == JobStatus.READY:
                    job.status = JobStatus.CANCELLED
                    self._summary.cancelled += 1
                    self._notify(job)

    def _notify(self, job: Job) -> None:
        if self._on_job_updated:
            try:
                self._on_job_updated(job)
            except Exception:
                log.exception("Job-updated callback raised")

    def _notify_progress(self, job: Job) -> None:
        if self._on_progress:
            try:
                self._on_progress(self._done, self._total, job.display_name)
            except Exception:
                log.exception("Progress callback raised")

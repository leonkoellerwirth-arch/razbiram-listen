"""Background job manager — a bounded worker pool over ``process_audio``.

Large audio (a film) can take far longer than an HTTP request should stay open, so
the studio submits a **job** instead of streaming synchronously: the upload is
written to a library entry, the job is queued, and a small pool of worker threads
runs :func:`razbiram_listen.pipeline.process_audio` in the background, updating each
job's progress. Finished results land in the persistent library
(:mod:`razbiram_listen.library`); the browser polls :meth:`JobManager.snapshot`.

Parallelism is **bounded** (default 2, ``$RAZBIRAM_LISTEN_WORKERS``) so a film does
not thrash the machine. ``process_audio`` is injectable for net-free tests.
"""

from __future__ import annotations

import os
import queue
import threading
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

from . import library
from .pipeline import process_audio

# The pipeline seam: (audio, *, gloss_lang, gloss_model, enrich, show_progress,
# on_event) -> ProcessResult. Injected in tests.
ProcessFn = Callable[..., object]

# How the caller streams the (possibly multi-GB) upload to a path, in chunks.
WriteAudioFn = Callable[[Path], None]


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()


def default_workers() -> int:
    """Worker count from ``$RAZBIRAM_LISTEN_WORKERS`` (default 2, floor 1)."""
    try:
        return max(1, int(os.environ.get("RAZBIRAM_LISTEN_WORKERS", "2")))
    except ValueError:
        return 2


@dataclass
class Job:
    """One unit of background work, mirrored to the queue panel."""

    id: str
    filename: str
    title: str
    enrich: bool
    gloss: str | None
    model: str | None
    audio_path: str
    status: str = "queued"  # queued | running | done | error
    stage: str | None = None
    fraction: float | None = None
    error: str | None = None
    created_at: str = field(default_factory=_now_iso)

    def snapshot(self) -> dict:
        return {
            "id": self.id,
            "filename": self.filename,
            "title": self.title,
            "status": self.status,
            "stage": self.stage,
            "fraction": self.fraction,
            "error": self.error,
            "createdAt": self.created_at,
            "mode": "enriched" if self.enrich else "core",
        }


class JobManager:
    """Thread-safe queue + bounded worker pool; results go to the library."""

    def __init__(self, *, workers: int | None = None, process: ProcessFn = process_audio) -> None:
        self._process = process
        self._queue: queue.Queue[str] = queue.Queue()
        self._jobs: dict[str, Job] = {}
        self._lock = threading.Lock()
        self._n = workers if workers is not None else default_workers()
        self._started = False

    @property
    def workers(self) -> int:
        return self._n

    def start(self) -> None:
        """Spin up the daemon worker threads (idempotent)."""
        if self._started:
            return
        self._started = True
        for i in range(self._n):
            threading.Thread(target=self._worker, name=f"rzl-worker-{i}", daemon=True).start()

    def submit(
        self,
        *,
        filename: str,
        enrich: bool,
        gloss: str | None,
        model: str | None,
        write_audio: WriteAudioFn,
    ) -> str:
        """Reserve a library entry, stream the upload into it, and enqueue the job."""
        entry_id, audio_path = library.reserve(filename)
        write_audio(audio_path)  # caller streams the request body here, in chunks
        job = Job(
            id=entry_id,
            filename=filename,
            title=Path(filename).stem or filename,
            enrich=enrich,
            gloss=gloss,
            model=model,
            audio_path=str(audio_path),
        )
        with self._lock:
            self._jobs[entry_id] = job
        self._queue.put(entry_id)
        return entry_id

    def snapshot(self) -> list[dict]:
        """All jobs this session, newest-first (the queue panel polls this)."""
        with self._lock:
            jobs = sorted(self._jobs.values(), key=lambda j: j.created_at, reverse=True)
        return [job.snapshot() for job in jobs]

    def get(self, job_id: str) -> dict | None:
        with self._lock:
            job = self._jobs.get(job_id)
            return job.snapshot() if job else None

    def join(self) -> None:
        """Block until every queued job has finished (used by tests)."""
        self._queue.join()

    # --- internals ------------------------------------------------------------

    def _update(self, job_id: str, **fields: object) -> None:
        with self._lock:
            job = self._jobs.get(job_id)
            if job is not None:
                for key, value in fields.items():
                    setattr(job, key, value)

    def _worker(self) -> None:
        while True:
            job_id = self._queue.get()
            try:
                self._run(job_id)
            except Exception as exc:  # a bad job must never kill the worker
                self._update(job_id, status="error", error=f"{type(exc).__name__}: {exc}")
                library.discard(job_id)  # drop the orphaned reserved audio
            finally:
                self._queue.task_done()

    def _run(self, job_id: str) -> None:
        with self._lock:
            job = self._jobs.get(job_id)
        if job is None:
            return
        self._update(job_id, status="running", stage="transcribe", fraction=0.0)

        def on_event(stage: str, fraction: float | None) -> None:
            self._update(job_id, stage=stage, fraction=fraction)

        result = self._process(
            job.audio_path,
            gloss_lang=job.gloss if job.enrich else None,
            gloss_model=job.model,
            enrich=job.enrich,
            show_progress=False,
            on_event=on_event,
        )
        meta = {
            "title": job.title,
            "filename": job.filename,
            "durationS": getattr(result, "duration", None),
            "mode": "enriched" if getattr(result, "enriched", job.enrich) else "core",
            "glossLang": job.gloss if job.enrich else None,
            "coverage": getattr(getattr(result, "stats", None), "coverage", None),
            "createdAt": job.created_at,
        }
        library.save_result(job_id, result.document.to_json(), meta)
        self._update(job_id, status="done", stage="done", fraction=1.0)

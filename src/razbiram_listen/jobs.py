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

import json
import os
import queue
import threading
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

from . import enrichment, library
from .pipeline import process_audio

# The pipeline seam: (audio, *, gloss_lang, gloss_model, enrich, show_progress,
# on_event) -> ProcessResult. Injected in tests.
ProcessFn = Callable[..., object]

# The re-translate seam: (document, *, lang, gloss_model, on_progress) -> json str.
TranslateFn = Callable[..., str]

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
    entry_id: str  # the library entry this job produces or updates
    kind: str = "process"  # process (audio → result) | translate (re-gloss an entry)
    status: str = "queued"  # queued | running | done | error
    stage: str | None = None
    fraction: float | None = None
    error: str | None = None
    created_at: str = field(default_factory=_now_iso)

    def snapshot(self) -> dict:
        return {
            "id": self.id,
            "entryId": self.entry_id,
            "kind": self.kind,
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

    def __init__(
        self,
        *,
        workers: int | None = None,
        process: ProcessFn = process_audio,
        translate: TranslateFn = enrichment.retranslate,
    ) -> None:
        self._process = process
        self._translate = translate
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
            entry_id=entry_id,
        )
        with self._lock:
            self._jobs[entry_id] = job
        self._queue.put(entry_id)
        return entry_id

    def submit_translate(self, entry_id: str, *, lang: str, model: str | None) -> str:
        """Queue a re-gloss of an existing library entry into ``lang`` (no re-transcribe)."""
        meta = library.read_meta(entry_id) or {}
        title = meta.get("title") or entry_id
        job_id = uuid.uuid4().hex[:12]
        job = Job(
            id=job_id,
            filename=meta.get("filename", title),
            title=f"{title} → {lang.upper()}",
            enrich=True,
            gloss=lang,
            model=model,
            audio_path="",
            entry_id=entry_id,
            kind="translate",
        )
        with self._lock:
            self._jobs[job_id] = job
        self._queue.put(job_id)
        return job_id

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
                with self._lock:
                    job = self._jobs.get(job_id)
                # Only a failed process job leaves an orphaned reserved entry to drop;
                # a failed translate must never touch the existing entry.
                if job is not None and job.kind == "process":
                    library.discard(job.entry_id)
            finally:
                self._queue.task_done()

    def _run(self, job_id: str) -> None:
        with self._lock:
            job = self._jobs.get(job_id)
        if job is None:
            return
        if job.kind == "translate":
            self._run_translate(job)
        else:
            self._run_process(job)

    def _run_process(self, job: Job) -> None:
        self._update(job.id, status="running", stage="transcribe", fraction=0.0)

        def on_event(stage: str, fraction: float | None) -> None:
            self._update(job.id, stage=stage, fraction=fraction)

        result = self._process(
            job.audio_path,
            gloss_lang=job.gloss if job.enrich else None,
            gloss_model=job.model,
            enrich=job.enrich,
            show_progress=False,
            on_event=on_event,
        )
        enriched = getattr(result, "enriched", job.enrich)
        meta = {
            "title": job.title,
            "filename": job.filename,
            "durationS": getattr(result, "duration", None),
            "mode": "enriched" if enriched else "core",
            "glossLang": job.gloss if enriched else None,
            "langs": [job.gloss] if (enriched and job.gloss) else [],
            "coverage": getattr(getattr(result, "stats", None), "coverage", None),
            "createdAt": job.created_at,
        }
        library.save_result(job.entry_id, result.document.to_json(), meta)
        self._update(job.id, status="done", stage="done", fraction=1.0)

    def _run_translate(self, job: Job) -> None:
        # Re-gloss an existing entry into job.gloss, reusing its transcript + timings.
        self._update(job.id, status="running", stage="enrich", fraction=None)

        def on_progress(done: int, total: int) -> None:
            self._update(job.id, stage="enrich", fraction=(done / total) if total else 1.0)

        stored = library.read_result(job.entry_id)
        if stored is None:
            self._update(job.id, status="error", error="Eintrag nicht gefunden.")
            return
        updated = self._translate(
            json.loads(stored), lang=job.gloss, gloss_model=job.model, on_progress=on_progress
        )
        meta = library.read_meta(job.entry_id) or {}
        langs = set(meta.get("langs") or [])
        if job.gloss:
            langs.add(job.gloss)
        meta["langs"] = sorted(langs)
        meta["glossLang"] = job.gloss
        meta["mode"] = "enriched"
        meta.setdefault("title", job.title)
        meta.setdefault("createdAt", job.created_at)
        library.save_result(job.entry_id, updated, meta)
        self._update(job.id, status="done", stage="done", fraction=1.0)

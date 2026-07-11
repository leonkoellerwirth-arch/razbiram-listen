"""Tests for the background job manager (net-free; a fake process_audio)."""

from __future__ import annotations

import threading

import pytest

from razbiram_listen import jobs, library


class _FakeDocument:
    def to_json(self, *, indent: int | None = 2) -> str:
        return '{"text":"ok","schemaVersion":"1.0.0"}'


class _FakeStats:
    coverage = 1.0


class _FakeResult:
    def __init__(self, *, enriched: bool = False) -> None:
        self.enriched = enriched
        self.duration = 3.0
        self.stats = _FakeStats()
        self.document = _FakeDocument()


@pytest.fixture
def lib_home(tmp_path, monkeypatch):
    monkeypatch.setenv("RAZBIRAM_LISTEN_HOME", str(tmp_path))
    return tmp_path


def test_submit_runs_job_and_saves_to_library(lib_home) -> None:
    seen: dict[str, object] = {}

    def fake_process(audio, *, gloss_lang, gloss_model, enrich, show_progress, on_event):
        seen["audio"] = audio
        seen["enrich"] = enrich
        on_event("transcribe", 0.5)
        on_event("done", 1.0)
        return _FakeResult(enriched=enrich)

    mgr = jobs.JobManager(workers=1, process=fake_process)
    mgr.start()
    job_id = mgr.submit(
        filename="song.mp3",
        enrich=False,
        gloss=None,
        model=None,
        write_audio=lambda p: p.write_bytes(b"data"),
    )
    mgr.join()

    assert mgr.get(job_id)["status"] == "done"
    assert seen["enrich"] is False
    entries = library.list_entries()
    assert len(entries) == 1 and entries[0]["id"] == job_id
    assert entries[0]["mode"] == "core"
    assert library.read_result(job_id).startswith("{")
    # The audio was streamed into the entry and kept for replay.
    assert library.audio_path(job_id) is not None


def test_enrich_true_passes_gloss_through(lib_home) -> None:
    def fake_process(audio, *, gloss_lang, gloss_model, enrich, show_progress, on_event):
        assert enrich is True and gloss_lang == "de" and gloss_model == "aya-expanse:8b"
        return _FakeResult(enriched=True)

    mgr = jobs.JobManager(workers=1, process=fake_process)
    mgr.start()
    job_id = mgr.submit(
        filename="f.mp3",
        enrich=True,
        gloss="de",
        model="aya-expanse:8b",
        write_audio=lambda p: p.write_bytes(b"d"),
    )
    mgr.join()

    assert mgr.get(job_id)["status"] == "done"
    meta = library.read_meta(job_id)
    assert meta["mode"] == "enriched"
    assert meta["glossLang"] == "de"


def test_failed_job_reports_error_and_discards_reserved_entry(lib_home) -> None:
    def boom(audio, **_kw):
        raise RuntimeError("kaputt")

    mgr = jobs.JobManager(workers=1, process=boom)
    mgr.start()
    job_id = mgr.submit(
        filename="f.mp3",
        enrich=False,
        gloss=None,
        model=None,
        write_audio=lambda p: p.write_bytes(b"d"),
    )
    mgr.join()

    snap = mgr.get(job_id)
    assert snap["status"] == "error"
    assert "kaputt" in snap["error"]
    assert library.list_entries() == []  # reserved entry cleaned up


def test_translate_job_reglosses_existing_entry(lib_home) -> None:
    def fake_process(audio, *, gloss_lang, gloss_model, enrich, show_progress, on_event):
        return _FakeResult(enriched=True)

    captured: dict[str, object] = {}

    def fake_translate(document, *, lang, gloss_model=None, on_progress=None):
        captured["lang"] = lang
        on_progress(1, 2)
        on_progress(2, 2)
        return __import__("json").dumps({**document, "_lang": lang})

    mgr = jobs.JobManager(workers=1, process=fake_process, translate=fake_translate)
    mgr.start()
    entry = mgr.submit(
        filename="f.mp3",
        enrich=True,
        gloss="en",
        model=None,
        write_audio=lambda p: p.write_bytes(b"d"),
    )
    mgr.join()
    assert library.read_meta(entry)["glossLang"] == "en"

    # Now translate the existing entry to German — a separate job, same entry.
    tid = mgr.submit_translate(entry, lang="de", model=None)
    assert tid != entry
    mgr.join()

    snap = mgr.get(tid)
    assert snap["status"] == "done"
    assert snap["kind"] == "translate"
    assert snap["entryId"] == entry
    assert captured["lang"] == "de"
    meta = library.read_meta(entry)
    assert meta["glossLang"] == "de"
    assert set(meta["langs"]) == {"de", "en"}  # both remembered


def test_workers_run_in_parallel(lib_home) -> None:
    # A barrier both jobs must reach at once: with 2 workers they do; with 1 the
    # first would block until the 3s timeout and raise BrokenBarrierError.
    barrier = threading.Barrier(2, timeout=3)

    def slow(audio, **_kw):
        barrier.wait()
        return _FakeResult()

    mgr = jobs.JobManager(workers=2, process=slow)
    mgr.start()
    for i in range(2):
        mgr.submit(
            filename=f"{i}.mp3",
            enrich=False,
            gloss=None,
            model=None,
            write_audio=lambda p: p.write_bytes(b"d"),
        )
    mgr.join()

    assert all(s["status"] == "done" for s in mgr.snapshot())

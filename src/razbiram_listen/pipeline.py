"""Pipeline orchestration (M4): audio → transcript → (enrichment) → alignment → doc.

``process_audio`` is the end-to-end entry point behind the ``process`` CLI
command. It always transcribes and aligns; **enrichment is optional** (ECOSYSTEM
§3 / this repo's plugin model):

- **Core mode (default):** transcribe → build a document straight from Whisper
  (:func:`~razbiram_listen.segment.build_core_document`) → align. No razbiram-nlp
  needed; the karaoke viewer plays the synced transcript immediately.
- **Enriched mode (opt-in):** when ``enrich=True`` (or a ``gloss_lang`` is given)
  the razbiram-nlp plugin adds glosses/CEFR/morphology
  (:mod:`razbiram_listen.enrichment`) before alignment.

Testability
-----------
The heavy collaborators are injectable: pass a ``transcriber`` (a Whisper model
fake) and/or an ``enrich_fn`` to unit-test the orchestration with no model and no
network. When omitted, the real Whisper wrapper and the real razbiram-nlp plugin
are used lazily.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from . import enrichment
from .align import AlignmentStats, align
from .contract import EnrichedDocument
from .models import AudioRef, ListenDocument
from .segment import build_core_document
from .transcribe import DEFAULT_MODEL, Transcriber, Transcription

# The enrichment seam: text (+ gloss language/model) -> EnrichedDocument.
EnrichFn = Callable[..., EnrichedDocument]


@dataclass(frozen=True)
class ProcessResult:
    """The produced document plus the signals worth reporting to the user."""

    document: ListenDocument
    stats: AlignmentStats
    language: str
    duration: float
    enriched: bool


def process_audio(
    audio: str | Path,
    *,
    gloss_lang: str | None = None,
    gloss_model: str | None = None,
    enrich: bool = False,
    model_size: str = DEFAULT_MODEL,
    language: str = "bg",
    transcriber: Transcriber | None = None,
    enrich_fn: EnrichFn | None = None,
    show_progress: bool = True,
    on_event: Callable[[str, float | None], None] | None = None,
) -> ProcessResult:
    """Run the pipeline on one local audio file.

    Parameters
    ----------
    audio:
        Path to a local audio file (BYO-audio; never uploaded).
    gloss_lang:
        Gloss target language (``"de"``/``"en"``) or ``None`` for no glosses.
        Passing a language implies ``enrich=True``.
    gloss_model:
        Local Ollama model for glossing (e.g. ``"aya-expanse:8b"``); ``None`` uses
        the hub default. Only used when enriching and no ``enrich_fn`` is injected.
    enrich:
        Opt in to razbiram-nlp enrichment (glosses/CEFR/morphology). Off by
        default: the core produces a synced transcript with no plugin installed.
    model_size:
        Whisper model when no ``transcriber`` is injected.
    transcriber, enrich_fn:
        Injectable seams for testing; real ones are used lazily when omitted.

    Raises
    ------
    razbiram_listen.enrichment.EnrichmentUnavailable
        If enrichment is requested but razbiram-nlp is not installed and no
        ``enrich_fn`` is injected. Callers should check
        :func:`razbiram_listen.enrichment.is_available` first.
    """
    transcriber = transcriber or Transcriber(model_size)

    def emit(stage: str, fraction: float | None) -> None:
        if on_event:
            on_event(stage, fraction)

    emit("transcribe", 0.0)
    on_progress = (lambda f: emit("transcribe", f)) if on_event else None
    transcription: Transcription = transcriber.transcribe(
        audio, language=language, show_progress=show_progress, on_progress=on_progress
    )

    want_enrich = enrich or gloss_lang is not None
    if want_enrich:
        emit("enrich", None)  # indeterminate while the cheap analysis stages run

        def enrich_progress(done: int, total: int) -> None:
            # Real "sentence X of N" fractions once glossing (the slow part) starts.
            emit("enrich", (done / total) if total else 1.0)

        do_enrich = enrich_fn or enrichment.enrich_document
        doc = do_enrich(
            transcription.text,
            gloss_lang=gloss_lang,
            gloss_model=gloss_model,
            on_progress=enrich_progress,
        )
    else:
        doc = build_core_document(transcription)

    emit("align", None)
    alignment = align(doc, transcription)
    emit("done", 1.0)

    audio_ref = AudioRef(filename=Path(audio).name, duration_s=transcription.duration)
    document = ListenDocument.from_enriched(doc, audio_ref=audio_ref, timings=alignment.timings)
    return ProcessResult(
        document=document,
        stats=alignment.stats,
        language=transcription.language,
        duration=transcription.duration,
        enriched=want_enrich,
    )

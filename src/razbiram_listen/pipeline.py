"""Pipeline orchestration (M4): audio → transcript → enrichment → alignment → doc.

``process_audio`` is the end-to-end entry point behind the ``process`` CLI
command. It wires the three stages together and wraps the result as a
:class:`~razbiram_listen.models.ListenDocument` (an ``EnrichedDocument`` + audio
timings), ready to serialise as ``.listen.json``.

Reuse, not reinvention (ECOSYSTEM §3): enrichment is delegated to the razbiram-nlp
hub's ``enrich_text``; only transcription (M2) and alignment (M3) are ours.

Testability
-----------
The two heavy collaborators are injectable: pass a ``transcriber`` (a Whisper
model fake) and/or an ``enrich`` callable to unit-test the orchestration with no
model and no network. When omitted, the real Whisper wrapper and the real
``razbiram_nlp.enrich_text`` are built lazily.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from razbiram_nlp import EnrichedDocument

from .align import AlignmentStats, align
from .models import AudioRef, ListenDocument
from .transcribe import DEFAULT_MODEL, Transcriber, Transcription

# The enrichment seam: text (+ gloss language) -> EnrichedDocument.
EnrichFn = Callable[..., EnrichedDocument]


@dataclass(frozen=True)
class ProcessResult:
    """The produced document plus the signals worth reporting to the user."""

    document: ListenDocument
    stats: AlignmentStats
    language: str
    duration: float


def process_audio(
    audio: str | Path,
    *,
    gloss_lang: str | None = None,
    gloss_model: str | None = None,
    model_size: str = DEFAULT_MODEL,
    language: str = "bg",
    transcriber: Transcriber | None = None,
    enrich: EnrichFn | None = None,
    show_progress: bool = True,
) -> ProcessResult:
    """Run the full pipeline on one local audio file.

    Parameters
    ----------
    audio:
        Path to a local audio file (BYO-audio; never uploaded).
    gloss_lang:
        Gloss target language (``"de"``/``"en"``) or ``None`` for no glosses.
    gloss_model:
        Local Ollama model for glossing (e.g. ``"aya-expanse:8b"``); ``None`` uses
        the hub default. Only used when ``gloss_lang`` is set and no ``enrich`` is
        injected.
    model_size:
        Whisper model when no ``transcriber`` is injected.
    transcriber, enrich:
        Injectable seams for testing; real ones are built lazily when omitted.
    """
    transcriber = transcriber or Transcriber(model_size)
    enrich = enrich or _make_enrich(gloss_model)

    transcription: Transcription = transcriber.transcribe(
        audio, language=language, show_progress=show_progress
    )
    doc = enrich(transcription.text, gloss_lang=gloss_lang)
    alignment = align(doc, transcription)

    audio_ref = AudioRef(filename=Path(audio).name, duration_s=transcription.duration)
    document = ListenDocument.from_enriched(doc, audio_ref=audio_ref, timings=alignment.timings)
    return ProcessResult(
        document=document,
        stats=alignment.stats,
        language=transcription.language,
        duration=transcription.duration,
    )


def _make_enrich(gloss_model: str | None) -> EnrichFn:
    """Build the default enrich function, bound to a chosen local gloss model."""

    def _enrich(text: str, *, gloss_lang: str | None) -> EnrichedDocument:
        return _default_enrich(text, gloss_lang=gloss_lang, gloss_model=gloss_model)

    return _enrich


def _default_enrich(
    text: str, *, gloss_lang: str | None, gloss_model: str | None = None
) -> EnrichedDocument:
    """Delegate to the hub, selecting the stages the local install can actually run.

    Morphology needs the optional ``classla`` extra; difficulty/vocab need the hub's
    ``data/``+``config/`` (set ``RAZBIRAM_NLP_DATA_DIR``/``RAZBIRAM_NLP_CONFIG_DIR``
    or install a hub checkout). Missing pieces degrade gracefully rather than crash.
    Imported lazily so plain imports stay light.
    """
    from razbiram_nlp import enrich_text

    provider = None
    if gloss_lang is not None and gloss_model:
        from razbiram_nlp.gloss import OllamaGlossProvider

        provider = OllamaGlossProvider(model=gloss_model)

    stages = _available_stages(gloss_lang)
    try:
        return enrich_text(text, gloss_lang=gloss_lang, stages=stages, gloss_provider=provider)
    except FileNotFoundError:
        # The hub's difficulty/vocab resources aren't available in a bare install;
        # degrade to segmentation (+ morphology) + gloss (sentence glosses survive).
        reduced = stages - {"difficulty", "vocab"}
        return enrich_text(text, gloss_lang=gloss_lang, stages=reduced, gloss_provider=provider)


def _available_stages(gloss_lang: str | None) -> set[str]:
    """The stages this install can run: morphology only if ``classla`` is present."""
    from importlib.util import find_spec

    stages = {"segmentation", "difficulty", "vocab"}
    if find_spec("classla") is not None:
        stages.add("morphology")
    if gloss_lang is not None:
        stages.add("gloss")
    return stages

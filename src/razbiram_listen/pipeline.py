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
    model_size:
        Whisper model when no ``transcriber`` is injected.
    transcriber, enrich:
        Injectable seams for testing; real ones are built lazily when omitted.
    """
    transcriber = transcriber or Transcriber(model_size)
    enrich = enrich or _default_enrich

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


def _default_enrich(text: str, *, gloss_lang: str | None) -> EnrichedDocument:
    """Delegate to the hub. Imported lazily so plain imports stay light."""
    from razbiram_nlp import enrich_text

    return enrich_text(text, gloss_lang=gloss_lang)

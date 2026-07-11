"""Transcription stage — a thin, testable wrapper around faster-whisper.

Turns a local audio file into a :class:`Transcription`: the full text plus
segment- and **word-level** timestamps. Word timestamps are the input the
alignment stage (M3) maps onto razbiram tokens, so they are always requested.

Design
------
- **The model is injectable.** ``Transcriber`` takes an optional pre-built model
  object; when omitted it lazily constructs a ``faster_whisper.WhisperModel``.
  Unit tests inject a fake and never touch the real model or the network; one
  ``slow`` test exercises the real path (ECOSYSTEM §5).
- **faster-whisper types stay at the boundary.** Its ``Segment``/``Word`` objects
  are mapped to our own value objects here, so ``align.py`` and the tests depend
  only on this module, not on faster-whisper.
- **Nothing is downloaded at import time.** ``faster_whisper`` is imported inside
  the loader, so importing this module (and running the unit tests) is cheap.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable, Iterator
from pathlib import Path
from typing import Protocol

from pydantic import BaseModel, ConfigDict, Field
from rich.progress import BarColumn, Progress, TaskProgressColumn, TextColumn, TimeElapsedColumn

# Default model: small is the CPU-friendly floor (Briefing §4). Vielnutzer with a
# GPU can pass medium/large.
DEFAULT_MODEL = "small"


class _Frozen(BaseModel):
    model_config = ConfigDict(extra="forbid")


class TranscribedWord(_Frozen):
    """One recognised word with its playback window, from a Whisper word timestamp."""

    text: str = Field(description="Surface form as Whisper emitted it (leading space stripped).")
    start: float = Field(ge=0.0, description="Word start, in seconds.")
    end: float = Field(ge=0.0, description="Word end, in seconds.")
    probability: float | None = Field(
        default=None, ge=0.0, le=1.0, description="Whisper's confidence for this word, if given."
    )


class TranscribedSegment(_Frozen):
    """One Whisper segment (roughly a sentence): its text, span, and words."""

    text: str
    start: float = Field(ge=0.0)
    end: float = Field(ge=0.0)
    words: list[TranscribedWord] = Field(default_factory=list)


class Transcription(_Frozen):
    """The full transcription result: text plus segment/word timings."""

    text: str = Field(description="Full transcript text, segments joined and trimmed.")
    language: str = Field(description="Language code Whisper decoded (expected 'bg').")
    duration: float = Field(ge=0.0, description="Audio duration in seconds, per Whisper.")
    model: str = Field(description="Whisper model size used, e.g. 'small'.")
    segments: list[TranscribedSegment] = Field(default_factory=list)

    @property
    def words(self) -> list[TranscribedWord]:
        """All words across all segments, in order."""
        return [w for seg in self.segments for w in seg.words]


class _WhisperLike(Protocol):
    """The slice of ``faster_whisper.WhisperModel`` this wrapper relies on."""

    def transcribe(self, audio: str, **kwargs: object) -> tuple[Iterable[object], object]: ...


class Transcriber:
    """Transcribes local audio with word timestamps.

    Parameters
    ----------
    model_size:
        Whisper model to load when no ``model`` is injected (default ``small``).
    device, compute_type:
        Passed to ``WhisperModel``; ``cpu``/``int8`` is the portable default.
    model:
        A pre-built model (or fake) exposing ``transcribe`` — injected in tests.
    """

    def __init__(
        self,
        model_size: str = DEFAULT_MODEL,
        *,
        device: str = "cpu",
        compute_type: str = "int8",
        model: _WhisperLike | None = None,
    ) -> None:
        self.model_size = model_size
        self._device = device
        self._compute_type = compute_type
        self._model = model

    def _get_model(self) -> _WhisperLike:
        if self._model is None:
            # Imported lazily so unit tests and plain imports never load it.
            from faster_whisper import WhisperModel

            self._model = WhisperModel(
                self.model_size, device=self._device, compute_type=self._compute_type
            )
        return self._model

    def transcribe(
        self,
        audio: str | Path,
        *,
        language: str = "bg",
        beam_size: int = 5,
        show_progress: bool = True,
        on_progress: Callable[[float], None] | None = None,
    ) -> Transcription:
        """Transcribe ``audio`` and return a :class:`Transcription`.

        Word timestamps are always on. faster-whisper transcribes lazily as the
        segment generator is consumed, so progress is reported by walking it.
        ``on_progress`` receives a 0..1 fraction as segments complete (for a UI).
        """
        model = self._get_model()
        segment_iter, info = model.transcribe(
            str(audio),
            language=language,
            beam_size=beam_size,
            word_timestamps=True,
        )
        duration = float(getattr(info, "duration", 0.0) or 0.0)

        segments = []
        for seg in _with_progress(segment_iter, duration, enabled=show_progress):
            segments.append(_map_segment(seg))
            if on_progress and duration > 0:
                on_progress(min(float(seg.end) / duration, 1.0))
        text = "".join(seg.text for seg in segments).strip()
        return Transcription(
            text=text,
            language=str(getattr(info, "language", language)),
            duration=duration,
            model=self.model_size,
            segments=segments,
        )


def _map_segment(seg: object) -> TranscribedSegment:
    """Map a faster-whisper segment (or a compatible fake) to our value object."""
    raw_words = getattr(seg, "words", None) or []
    words = [
        TranscribedWord(
            text=str(w.word).strip(),
            start=float(w.start),
            end=float(w.end),
            probability=_opt_float(getattr(w, "probability", None)),
        )
        for w in raw_words
    ]
    return TranscribedSegment(
        text=str(seg.text),
        start=float(seg.start),
        end=float(seg.end),
        words=words,
    )


def _opt_float(value: object) -> float | None:
    return None if value is None else float(value)


def _with_progress(
    segments: Iterable[object], duration: float, *, enabled: bool
) -> Iterator[object]:
    """Yield segments, driving a rich progress bar toward ``duration`` seconds."""
    if not enabled or duration <= 0:
        yield from segments
        return

    with Progress(
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TaskProgressColumn(),
        TimeElapsedColumn(),
        transient=True,
    ) as progress:
        task = progress.add_task("Transcribing", total=duration)
        for seg in segments:
            yield seg
            progress.update(task, completed=min(float(seg.end), duration))
        progress.update(task, completed=duration)

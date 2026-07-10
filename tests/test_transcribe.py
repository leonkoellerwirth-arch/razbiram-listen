"""Tests for the transcription wrapper (M2).

Unit tests inject a fake model shaped like ``faster_whisper.WhisperModel`` and
never touch the real model or the network. One ``slow`` test exercises the real
faster-whisper path on a synthesized tone (opt in with ``-m slow``).
"""

from __future__ import annotations

import math
import struct
import wave
from pathlib import Path
from types import SimpleNamespace

import pytest

from razbiram_listen.transcribe import Transcriber, Transcription


def _word(word: str, start: float, end: float, probability: float | None = 0.9) -> SimpleNamespace:
    # Mirrors faster-whisper's Word: note the leading space on `.word`.
    return SimpleNamespace(word=word, start=start, end=end, probability=probability)


def _segment(text: str, start: float, end: float, words: list[SimpleNamespace]) -> SimpleNamespace:
    return SimpleNamespace(text=text, start=start, end=end, words=words)


class FakeModel:
    """A stand-in for WhisperModel that records the kwargs it was called with."""

    def __init__(self, segments: list[SimpleNamespace], duration: float, language: str = "bg"):
        self._segments = segments
        self._info = SimpleNamespace(language=language, duration=duration)
        self.calls: list[dict[str, object]] = []

    def transcribe(self, audio: str, **kwargs: object):
        self.calls.append({"audio": audio, **kwargs})
        # faster-whisper yields segments lazily — mimic with a generator.
        return (s for s in self._segments), self._info


def _two_segment_model() -> FakeModel:
    seg1 = _segment(
        " Здравей свят.", 0.0, 1.2, [_word(" Здравей", 0.0, 0.6), _word(" свят.", 0.6, 1.2)]
    )
    seg2 = _segment(" Как си?", 1.2, 2.0, [_word(" Как", 1.2, 1.5), _word(" си?", 1.5, 2.0, None)])
    return FakeModel([seg1, seg2], duration=2.0)


def test_transcribe_concatenates_and_trims_text() -> None:
    result = Transcriber(model=_two_segment_model()).transcribe("x.mp3", show_progress=False)
    assert isinstance(result, Transcription)
    assert result.text == "Здравей свят. Как си?"


def test_word_timestamps_are_always_requested() -> None:
    fake = _two_segment_model()
    Transcriber(model=fake).transcribe("x.mp3", show_progress=False)
    assert fake.calls[0]["word_timestamps"] is True
    assert fake.calls[0]["language"] == "bg"


def test_words_are_flattened_in_order_with_spaces_stripped() -> None:
    result = Transcriber(model=_two_segment_model()).transcribe("x.mp3", show_progress=False)
    assert [w.text for w in result.words] == ["Здравей", "свят.", "Как", "си?"]
    # Timings survive the mapping.
    assert result.words[0].start == 0.0
    assert result.words[-1].end == 2.0


def test_missing_probability_maps_to_none() -> None:
    result = Transcriber(model=_two_segment_model()).transcribe("x.mp3", show_progress=False)
    assert result.words[-1].probability is None
    assert result.words[0].probability == pytest.approx(0.9)


def test_language_and_duration_come_from_info() -> None:
    result = Transcriber(model=_two_segment_model()).transcribe("x.mp3", show_progress=False)
    assert result.language == "bg"
    assert result.duration == pytest.approx(2.0)
    assert result.model == "small"


def test_progress_enabled_still_yields_every_segment() -> None:
    # duration > 0 activates the progress bar path; output must be unchanged.
    result = Transcriber(model=_two_segment_model()).transcribe("x.mp3", show_progress=True)
    assert len(result.segments) == 2


def _write_tone_wav(path: Path, *, seconds: float = 1.0, rate: int = 16000) -> None:
    """Write a short mono 16-bit sine tone — enough to drive the real model."""
    with wave.open(str(path), "w") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(rate)
        frames = bytearray()
        for i in range(int(seconds * rate)):
            sample = int(0.3 * 32767 * math.sin(2 * math.pi * 220 * i / rate))
            frames += struct.pack("<h", sample)
        wav.writeframes(bytes(frames))


@pytest.mark.slow
def test_real_tiny_model_returns_a_transcription(tmp_path: Path) -> None:
    audio = tmp_path / "tone.wav"
    _write_tone_wav(audio)
    # 'tiny' keeps the download and compute small; we assert the contract, not
    # transcription accuracy (a tone has no words).
    result = Transcriber("tiny").transcribe(audio, show_progress=False)
    assert isinstance(result, Transcription)
    assert result.duration > 0
    assert result.model == "tiny"

"""Tests for the end-to-end pipeline (M4).

Unit tests inject fake transcribe/enrich seams so the orchestration is verified
with no Whisper model and no network. One ``slow`` test runs the real pipeline
(real Whisper ``tiny`` + the hub's real segmentation stage — no heavy morphology
model) end to end.
"""

from __future__ import annotations

import json
import math
import struct
import wave
from pathlib import Path

import pytest
from razbiram_nlp import EnrichedDocument
from razbiram_nlp.models import Sentence, Token

from razbiram_listen import SCHEMA_VERSION, ListenDocument
from razbiram_listen.pipeline import process_audio
from razbiram_listen.transcribe import TranscribedSegment, TranscribedWord, Transcription


class FakeTranscriber:
    """Stands in for Transcriber — returns a canned Transcription."""

    def __init__(self, transcription: Transcription):
        self._t = transcription
        self.model_size = "fake"

    def transcribe(self, audio, *, language="bg", show_progress=True, **_kw) -> Transcription:  # noqa: ANN001
        return self._t


def _canned_transcription() -> Transcription:
    words = [
        TranscribedWord(text="Аз", start=0.0, end=0.4),
        TranscribedWord(text="съм", start=0.4, end=0.7),
        TranscribedWord(text="тук.", start=0.7, end=1.1),
    ]
    seg = TranscribedSegment(text="Аз съм тук.", start=0.0, end=1.1, words=words)
    return Transcription(
        text="Аз съм тук.", language="bg", duration=1.1, model="fake", segments=[seg]
    )


def _fake_enrich(text: str, *, gloss_lang: str | None) -> EnrichedDocument:
    # Tokens consistent with the canned transcription so alignment matches 3/3.
    toks = [
        Token(text="Аз", kind="word", start=0, end=2),
        Token(text="съм", kind="word", start=3, end=6),
        Token(text="тук", kind="word", start=7, end=10),
        Token(text=".", kind="punct", start=10, end=11),
    ]
    sent = Sentence(text=text, start=0, end=len(text), tokens=toks)
    return EnrichedDocument(text=text, lang="bg", stages=["segmentation"], sentences=[sent])


def test_process_audio_assembles_a_listen_document() -> None:
    result = process_audio(
        "episode.mp3",
        gloss_lang=None,
        transcriber=FakeTranscriber(_canned_transcription()),
        enrich=_fake_enrich,
        show_progress=False,
    )
    doc = result.document
    assert isinstance(doc, ListenDocument)
    assert doc.text == "Аз съм тук."
    assert doc.schema_version == SCHEMA_VERSION
    # audioRef references the file by name only — never the audio itself.
    assert doc.audio_ref is not None
    assert doc.audio_ref.filename == "episode.mp3"
    assert doc.audio_ref.duration_s == pytest.approx(1.1)
    # Timings were aligned onto every word token.
    assert doc.timings is not None
    assert len(doc.timings.tokens) == 3
    assert result.stats.coverage == pytest.approx(1.0)


def test_process_audio_output_is_valid_listen_json() -> None:
    result = process_audio(
        "лекция.mp3",
        transcriber=FakeTranscriber(_canned_transcription()),
        enrich=_fake_enrich,
        show_progress=False,
    )
    payload = json.loads(result.document.to_json())
    assert payload["schemaVersion"] == SCHEMA_VERSION
    assert payload["audioRef"]["filename"] == "лекция.mp3"
    assert payload["timings"]["tokens"][0]["source"] == "word"


def test_gloss_lang_is_passed_through_to_enrich() -> None:
    seen: dict[str, str | None] = {}

    def spy_enrich(text: str, *, gloss_lang: str | None) -> EnrichedDocument:
        seen["gloss_lang"] = gloss_lang
        return _fake_enrich(text, gloss_lang=gloss_lang)

    process_audio(
        "a.mp3",
        gloss_lang="de",
        transcriber=FakeTranscriber(_canned_transcription()),
        enrich=spy_enrich,
        show_progress=False,
    )
    assert seen["gloss_lang"] == "de"


def _write_tone_wav(path: Path, *, seconds: float = 1.0, rate: int = 16000) -> None:
    with wave.open(str(path), "w") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(rate)
        frames = bytearray()
        for i in range(int(seconds * rate)):
            frames += struct.pack("<h", int(0.3 * 32767 * math.sin(2 * math.pi * 220 * i / rate)))
        wav.writeframes(bytes(frames))


@pytest.mark.slow
def test_real_end_to_end_pipeline(tmp_path: Path) -> None:
    # Real Whisper tiny + the hub's real segmentation stage (light; no classla).
    from functools import partial

    from razbiram_nlp import enrich_text

    audio = tmp_path / "tone.wav"
    _write_tone_wav(audio)
    result = process_audio(
        audio,
        gloss_lang=None,
        model_size="tiny",
        enrich=partial(enrich_text, stages={"segmentation"}),
        show_progress=False,
    )
    assert isinstance(result.document, ListenDocument)
    # The output is always a valid .listen.json, even for near-empty audio.
    json.loads(result.document.to_json())
    assert result.document.audio_ref is not None
    assert result.document.audio_ref.filename == "tone.wav"

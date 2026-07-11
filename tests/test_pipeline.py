"""Tests for the end-to-end pipeline (M4).

Unit tests inject fake transcribe/enrich seams so the orchestration is verified
with no Whisper model and no network. Core mode (no razbiram-nlp) is exercised
directly; one ``slow`` test runs the real pipeline (real Whisper ``tiny`` + the
hub's real segmentation stage) end to end when the plugin is installed.
"""

from __future__ import annotations

import json
import math
import struct
import wave
from pathlib import Path

import pytest

from razbiram_listen import SCHEMA_VERSION, ListenDocument
from razbiram_listen.contract import EnrichedDocument, Sentence, Token
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


def _fake_enrich(
    text: str, *, gloss_lang: str | None, gloss_model: str | None = None
) -> EnrichedDocument:
    # Tokens consistent with the canned transcription so alignment matches 3/3.
    toks = [
        Token(text="Аз", kind="word", start=0, end=2),
        Token(text="съм", kind="word", start=3, end=6),
        Token(text="тук", kind="word", start=7, end=10),
        Token(text=".", kind="punct", start=10, end=11),
    ]
    sent = Sentence(text=text, start=0, end=len(text), tokens=toks)
    return EnrichedDocument(text=text, lang="bg", stages=["segmentation"], sentences=[sent])


# --- Core mode: no razbiram-nlp, document built straight from Whisper ---------


def test_core_mode_needs_no_enrichment() -> None:
    result = process_audio(
        "episode.mp3",
        transcriber=FakeTranscriber(_canned_transcription()),
        show_progress=False,
    )
    doc = result.document
    assert isinstance(doc, ListenDocument)
    assert result.enriched is False
    assert doc.text == "Аз съм тук."
    # Whisper-derived tokens: three words + one punctuation.
    assert [t.text for t in doc.sentences[0].tokens] == ["Аз", "съм", "тук", "."]
    assert [t.kind for t in doc.sentences[0].tokens] == ["word", "word", "word", "punct"]
    # Every word token aligned to a Whisper timing.
    assert doc.timings is not None
    assert len(doc.timings.tokens) == 3
    assert result.stats.coverage == pytest.approx(1.0)
    # No enrichment ran → no glosses/CEFR.
    assert doc.sentences[0].gloss is None
    assert doc.difficulty is None


def test_core_mode_output_is_valid_listen_json() -> None:
    result = process_audio(
        "лекция.mp3",
        transcriber=FakeTranscriber(_canned_transcription()),
        show_progress=False,
    )
    payload = json.loads(result.document.to_json())
    assert payload["schemaVersion"] == SCHEMA_VERSION
    assert payload["audioRef"]["filename"] == "лекция.mp3"
    assert payload["timings"]["tokens"][0]["source"] == "word"


# --- Enriched mode: the razbiram-nlp plugin fills glosses/CEFR (injected here) -


def test_enriched_mode_assembles_a_listen_document() -> None:
    result = process_audio(
        "episode.mp3",
        enrich=True,
        transcriber=FakeTranscriber(_canned_transcription()),
        enrich_fn=_fake_enrich,
        show_progress=False,
    )
    doc = result.document
    assert isinstance(doc, ListenDocument)
    assert result.enriched is True
    assert doc.text == "Аз съм тук."
    assert doc.schema_version == SCHEMA_VERSION
    # audioRef references the file by name only — never the audio itself.
    assert doc.audio_ref is not None
    assert doc.audio_ref.filename == "episode.mp3"
    assert doc.audio_ref.duration_s == pytest.approx(1.1)
    assert doc.timings is not None
    assert len(doc.timings.tokens) == 3
    assert result.stats.coverage == pytest.approx(1.0)


def test_gloss_lang_implies_enrichment_and_is_passed_through() -> None:
    seen: dict[str, str | None] = {}

    def spy_enrich(
        text: str, *, gloss_lang: str | None, gloss_model: str | None = None
    ) -> EnrichedDocument:
        seen["gloss_lang"] = gloss_lang
        seen["gloss_model"] = gloss_model
        return _fake_enrich(text, gloss_lang=gloss_lang)

    result = process_audio(
        "a.mp3",
        gloss_lang="de",
        gloss_model="aya-expanse:8b",
        transcriber=FakeTranscriber(_canned_transcription()),
        enrich_fn=spy_enrich,
        show_progress=False,
    )
    # A gloss language implies enrichment even without enrich=True.
    assert result.enriched is True
    assert seen["gloss_lang"] == "de"
    assert seen["gloss_model"] == "aya-expanse:8b"


def test_available_stages_reflects_environment() -> None:
    from importlib.util import find_spec

    from razbiram_listen.enrichment import _available_stages

    base = _available_stages(None)
    assert {"segmentation", "difficulty", "vocab"} <= base
    assert "gloss" not in base
    assert "gloss" in _available_stages("de")
    # Morphology is offered iff the optional classla extra is installed.
    assert ("morphology" in base) == (find_spec("classla") is not None)


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
def test_real_end_to_end_core_pipeline(tmp_path: Path) -> None:
    # Real Whisper tiny, core mode — no plugin needed.
    audio = tmp_path / "tone.wav"
    _write_tone_wav(audio)
    result = process_audio(audio, model_size="tiny", show_progress=False)
    assert isinstance(result.document, ListenDocument)
    assert result.enriched is False
    # The output is always a valid .listen.json, even for near-empty audio.
    json.loads(result.document.to_json())
    assert result.document.audio_ref is not None
    assert result.document.audio_ref.filename == "tone.wav"


@pytest.mark.slow
def test_real_end_to_end_enriched_pipeline(tmp_path: Path) -> None:
    # Real Whisper tiny + the hub's real segmentation stage (light; no classla).
    pytest.importorskip("razbiram_nlp")
    from razbiram_nlp import enrich_text

    def enrich_seg_only(text: str, *, gloss_lang: str | None, gloss_model: str | None = None):
        return enrich_text(text, gloss_lang=None, stages={"segmentation"})

    audio = tmp_path / "tone.wav"
    _write_tone_wav(audio)
    result = process_audio(
        audio,
        enrich=True,
        model_size="tiny",
        enrich_fn=enrich_seg_only,
        show_progress=False,
    )
    assert isinstance(result.document, ListenDocument)
    assert result.enriched is True
    json.loads(result.document.to_json())

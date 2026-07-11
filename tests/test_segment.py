"""Tests for hub-free core segmentation (:func:`build_core_document`).

The delicate part is character offsets: a token's ``start``/``end`` must index the
reconstructed document text exactly, across multiple Whisper segments and the
leading space Whisper puts on each. That offset is the join key the aligner and
viewer rely on, so it gets a direct check.
"""

from __future__ import annotations

from razbiram_listen.segment import build_core_document
from razbiram_listen.transcribe import TranscribedSegment, Transcription


def _transcription(segments: list[TranscribedSegment]) -> Transcription:
    joined = "".join(s.text for s in segments)
    return Transcription(
        text=joined.strip(), language="bg", duration=9.0, model="fake", segments=segments
    )


def test_offsets_are_correct_across_segments_with_leading_space() -> None:
    # Whisper typically emits a leading space on each segment.
    segs = [
        TranscribedSegment(text=" Днес е вторник.", start=0.0, end=2.0, words=[]),
        TranscribedSegment(text=" Утре е сряда.", start=2.0, end=4.0, words=[]),
    ]
    doc = build_core_document(_transcription(segs))

    assert doc.text == "Днес е вторник. Утре е сряда."
    assert [s.text for s in doc.sentences] == ["Днес е вторник.", "Утре е сряда."]
    # Every token's slice of the document text equals its surface → offsets exact.
    for sent in doc.sentences:
        assert doc.text[sent.start : sent.end] == sent.text
        for tok in sent.tokens:
            assert doc.text[tok.start : tok.end] == tok.text


def test_words_numbers_and_punctuation_are_classified() -> None:
    segs = [TranscribedSegment(text="Имам 3 котки.", start=0.0, end=2.0, words=[])]
    doc = build_core_document(_transcription(segs))
    kinds = {t.text: t.kind for s in doc.sentences for t in s.tokens}
    assert kinds == {"Имам": "word", "3": "number", "котки": "word", ".": "punct"}


def test_core_document_carries_no_enrichment() -> None:
    segs = [TranscribedSegment(text="Здравей.", start=0.0, end=1.0, words=[])]
    doc = build_core_document(_transcription(segs))
    assert doc.stages == ["transcription"]
    assert doc.difficulty is None
    assert doc.vocab == []
    assert all(t.lemma is None and t.band is None for s in doc.sentences for t in s.tokens)

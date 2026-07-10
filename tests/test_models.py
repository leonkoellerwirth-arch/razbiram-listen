"""Contract tests for the ListenDocument model (M1).

These are net-free and model-free: they build a tiny EnrichedDocument by hand
(no Whisper, no classla) and check that the listen extension keeps the hub
contract intact and serialises with the reserved JSON keys.
"""

from __future__ import annotations

import json

import pytest
from pydantic import ValidationError
from razbiram_nlp import EnrichedDocument
from razbiram_nlp.models import Sentence, Token

from razbiram_listen import (
    SCHEMA_VERSION,
    AudioRef,
    ListenDocument,
    ListenTimings,
    SegmentTiming,
    TokenTiming,
)


def _tiny_enriched() -> EnrichedDocument:
    """A minimal but valid EnrichedDocument: one sentence, one word token."""
    text = "Здравей."
    token = Token(text="Здравей", kind="word", start=0, end=7, lemma="здравей", upos="INTJ")
    sentence = Sentence(text=text, start=0, end=len(text), tokens=[token])
    return EnrichedDocument(
        text=text, lang="bg", stages=["segment", "morphology"], sentences=[sentence]
    )


def test_from_enriched_is_a_superset_of_the_hub_document() -> None:
    doc = _tiny_enriched()
    listen = ListenDocument.from_enriched(doc)

    # Inherited contract is preserved verbatim.
    assert listen.text == doc.text
    assert listen.lang == "bg"
    assert listen.sentences[0].tokens[0].lemma == "здравей"
    # It IS an EnrichedDocument — consumers reading the hub contract still work.
    assert isinstance(listen, EnrichedDocument)
    # schemaVersion is always declared.
    assert listen.schema_version == SCHEMA_VERSION


def test_json_uses_the_reserved_camelcase_keys() -> None:
    listen = ListenDocument.from_enriched(
        _tiny_enriched(),
        audio_ref=AudioRef(filename="sample.mp3", duration_s=1.5),
        timings=ListenTimings(
            tokens=[
                TokenTiming(token_start=0, t_start=0.0, t_end=0.9, source="word", confidence=0.8)
            ],
            segments=[SegmentTiming(sentence_index=0, t_start=0.0, t_end=0.9)],
        ),
    )
    payload = json.loads(listen.to_json())

    # The three extension keys use the exact contract names (ECOSYSTEM §2).
    assert payload["schemaVersion"] == SCHEMA_VERSION
    assert payload["audioRef"]["filename"] == "sample.mp3"
    assert payload["timings"]["tokens"][0]["source"] == "word"
    # Inherited hub fields keep their own snake_case names.
    assert payload["text"] == "Здравей."
    assert "sentences" in payload


def test_roundtrip_through_json_is_lossless() -> None:
    original = ListenDocument.from_enriched(
        _tiny_enriched(),
        audio_ref=AudioRef(filename="sample.mp3"),
        timings=ListenTimings(segments=[SegmentTiming(sentence_index=0, t_start=0.0, t_end=1.0)]),
    )
    restored = ListenDocument.model_validate_json(original.to_json())
    assert restored.to_json() == original.to_json()


def test_token_timing_join_key_matches_the_token_offset() -> None:
    doc = _tiny_enriched()
    token = doc.sentences[0].tokens[0]
    timing = TokenTiming(token_start=token.start, t_start=0.0, t_end=0.5, source="word")
    assert timing.token_start == token.start


def test_unknown_fields_are_rejected() -> None:
    with pytest.raises(ValidationError):
        AudioRef(filename="a.mp3", bitrate=320)  # type: ignore[call-arg]


@pytest.mark.parametrize("bad", [-0.1, 1.1])
def test_confidence_is_bounded_to_unit_interval(bad: float) -> None:
    with pytest.raises(ValidationError):
        TokenTiming(token_start=0, t_start=0.0, t_end=0.5, source="word", confidence=bad)

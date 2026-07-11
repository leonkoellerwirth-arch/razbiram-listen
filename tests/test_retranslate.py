"""Tests for retranslating a stored entry (hub-gated; a fake provider, no Ollama).

The key property: switching the translation language recomputes only the glosses
and preserves morphology/CEFR, tokens, timings, audioRef and schemaVersion — so
alignment stays valid and no re-transcription happens.
"""

from __future__ import annotations

import json

import pytest

pytest.importorskip("razbiram_nlp")

from razbiram_listen import enrichment  # noqa: E402


class _FakeProvider:
    name = "fake"

    def gloss_word(self, *, surface: str, lemma: str, context: str, lang: str) -> str:
        return f"{lang}:{lemma}"

    def gloss_sentence(self, *, sentence: str, lang: str) -> str:
        return f"{lang}:sentence"


def _enriched_listen_json() -> dict:
    from razbiram_listen.contract import EnrichedDocument, Gloss, Sentence, Token, VocabEntry
    from razbiram_listen.models import (
        AudioRef,
        ListenDocument,
        ListenTimings,
        SegmentTiming,
        TokenTiming,
    )

    token = Token(
        text="времето", kind="word", start=5, end=12, lemma="време", upos="NOUN", band="A2"
    )
    sentence = Sentence(
        text="Днес времето е хубаво.",
        start=0,
        end=22,
        tokens=[token],
        gloss=Gloss(lang="de", text="alt-de", provider="x"),
    )
    base = EnrichedDocument(
        text="Днес времето е хубаво.",
        lang="bg",
        stages=["segmentation", "morphology", "gloss"],
        sentences=[sentence],
        vocab=[
            VocabEntry(
                lemma="време", count=1, band="A2", gloss=Gloss(lang="de", text="w", provider="x")
            )
        ],
    )
    listen = ListenDocument.from_enriched(
        base,
        audio_ref=AudioRef(filename="a.mp3", duration_s=3.0),
        timings=ListenTimings(
            tokens=[TokenTiming(token_start=5, t_start=0.1, t_end=0.5, source="word")],
            segments=[SegmentTiming(sentence_index=0, t_start=0.0, t_end=1.0)],
        ),
    )
    return json.loads(listen.to_json())


def test_retranslate_switches_glosses_and_preserves_everything_else(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)  # isolate the .razbiram_cache
    updated = json.loads(
        enrichment.retranslate(_enriched_listen_json(), lang="en", provider=_FakeProvider())
    )

    # Glosses now English (sentence + per-word vocab).
    assert updated["sentences"][0]["gloss"]["lang"] == "en"
    assert updated["sentences"][0]["gloss"]["text"] == "en:sentence"
    assert updated["vocab"][0]["gloss"]["text"] == "en:време"

    # Language-independent analysis + alignment preserved untouched.
    tok = updated["sentences"][0]["tokens"][0]
    assert tok["lemma"] == "време" and tok["band"] == "A2"
    assert updated["timings"]["tokens"][0]["token_start"] == 5
    assert updated["audioRef"]["filename"] == "a.mp3"
    assert updated["schemaVersion"]


def test_retranslate_without_plugin_raises(monkeypatch) -> None:
    monkeypatch.setattr(enrichment, "is_available", lambda: False)
    with pytest.raises(enrichment.EnrichmentUnavailable):
        enrichment.retranslate({"text": "x", "sentences": []}, lang="en")

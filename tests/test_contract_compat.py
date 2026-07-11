"""Contract-compatibility guard — listen's copy must mirror the hub, when present.

razbiram-nlp is an optional plugin, but when it IS installed the shape of
``razbiram_listen.contract.EnrichedDocument`` must stay identical to
``razbiram_nlp.EnrichedDocument``; otherwise an emitted ``.listen.json`` would
drift from the family contract. This round-trips a fully-populated hub document
through listen's model and back and asserts byte-identical JSON — the house
evaluator principle applied to the schema copy (ECOSYSTEM §5). The whole module
is skipped when the plugin is not installed (core-only installs).
"""

from __future__ import annotations

import pytest

pytest.importorskip("razbiram_nlp")


def _hub_sample():
    """A hub EnrichedDocument exercising every field, incl. enrichment ones."""
    from razbiram_nlp import EnrichedDocument
    from razbiram_nlp.models import (
        DifficultySummary,
        Gloss,
        Sentence,
        Token,
        VocabEntry,
    )

    word = Token(
        text="Здравей",
        kind="word",
        start=0,
        end=7,
        lemma="здравей",
        upos="INTJ",
        feats={"Mood": "Imp"},
        difficulty=0.2,
        band="A1",
    )
    punct = Token(text=".", kind="punct", start=7, end=8)
    sentence = Sentence(
        text="Здравей.",
        start=0,
        end=8,
        tokens=[word, punct],
        gloss=Gloss(lang="de", text="Hallo.", provider="ollama", cached=False),
    )
    return EnrichedDocument(
        text="Здравей.",
        lang="bg",
        stages=["segmentation", "morphology", "difficulty", "vocab", "gloss"],
        sentences=[sentence],
        vocab=[VocabEntry(lemma="здравей", upos="INTJ", count=1, freq_rank=42, band="A1")],
        difficulty=DifficultySummary(
            band="A1",
            confidence=1.0,
            band_distribution={"A1": 1.0},
            mean_sentence_length=1.0,
            scored_words=1,
        ),
    )


def test_top_level_field_names_match() -> None:
    from razbiram_nlp import EnrichedDocument as HubDoc

    from razbiram_listen.contract import EnrichedDocument as ListenDoc

    assert set(HubDoc.model_fields) == set(ListenDoc.model_fields)


def test_hub_document_roundtrips_through_listen_contract() -> None:
    from razbiram_listen.contract import EnrichedDocument as ListenDoc

    hub_doc = _hub_sample()
    # extra="forbid" means an unknown hub field would raise here — that is the
    # guard: a hub-added field fails loudly until listen's copy catches up.
    listen_doc = ListenDoc.model_validate(hub_doc.model_dump())
    assert listen_doc.model_dump(mode="json") == hub_doc.model_dump(mode="json")

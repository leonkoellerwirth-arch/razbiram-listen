"""Enrichment plugin — razbiram-nlp adds glosses/CEFR/morphology when installed.

razbiram-nlp is an **optional** dependency (``pip install razbiram-listen[enrich]``).
This module is the *only* place that imports it, and always lazily, so the core
(transcribe → align → karaoke) never depends on the hub. When the hub is absent
:func:`is_available` is ``False`` and the pipeline stays in core mode.

The hub is used purely as an engine: it enriches the transcript text, and the
result is converted into a listen :class:`~razbiram_listen.contract.EnrichedDocument`
(a shape-compatible copy of the same contract). Enrichment degrades gracefully to
whatever the install supports — morphology needs the ``classla`` extra;
difficulty/vocab need the hub's ``data/``+``config/`` — sentence glosses always
survive.
"""

from __future__ import annotations

from importlib.util import find_spec

from .contract import EnrichedDocument


class EnrichmentUnavailable(RuntimeError):
    """Raised when enrichment is requested but razbiram-nlp is not installed."""


def is_available() -> bool:
    """True if the razbiram-nlp enrichment plugin is importable."""
    return find_spec("razbiram_nlp") is not None


def enrich_document(
    text: str,
    *,
    gloss_lang: str | None,
    gloss_model: str | None = None,
) -> EnrichedDocument:
    """Enrich ``text`` via the razbiram-nlp hub and return a listen document.

    Raises :class:`EnrichmentUnavailable` if the hub is not installed — callers
    should check :func:`is_available` first (the pipeline does).
    """
    if not is_available():
        raise EnrichmentUnavailable(
            "razbiram-nlp is not installed. Install the enrichment plugin with "
            "'pip install razbiram-listen[enrich]' to get glosses and CEFR."
        )
    hub_doc = _run_hub_enrich(text, gloss_lang=gloss_lang, gloss_model=gloss_model)
    # Convert the hub's EnrichedDocument into our shape-compatible copy.
    return EnrichedDocument.model_validate(hub_doc.model_dump())


def _run_hub_enrich(text: str, *, gloss_lang: str | None, gloss_model: str | None):
    """Delegate to the hub, selecting the stages the local install can run.

    Morphology needs the optional ``classla`` extra; difficulty/vocab need the
    hub's ``data/``+``config/`` (``RAZBIRAM_NLP_DATA_DIR``/``RAZBIRAM_NLP_CONFIG_DIR``
    or a hub checkout). Missing pieces degrade rather than crash.
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
        # difficulty/vocab resources aren't available in a bare install; degrade to
        # segmentation (+ morphology) + gloss so sentence glosses still survive.
        reduced = stages - {"difficulty", "vocab"}
        return enrich_text(text, gloss_lang=gloss_lang, stages=reduced, gloss_provider=provider)


def _available_stages(gloss_lang: str | None) -> set[str]:
    """The stages this install can run: morphology only if ``classla`` is present."""
    stages = {"segmentation", "difficulty", "vocab"}
    if find_spec("classla") is not None:
        stages.add("morphology")
    if gloss_lang is not None:
        stages.add("gloss")
    return stages

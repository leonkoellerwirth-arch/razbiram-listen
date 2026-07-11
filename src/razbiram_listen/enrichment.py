"""Enrichment plugin — razbiram-nlp adds glosses/CEFR/morphology when installed.

razbiram-nlp is an **optional** dependency (``pip install razbiram-listen[enrich]``).
This module is the *only* place that imports it, and always lazily, so the core
(transcribe → align → karaoke) never depends on the hub. When the hub is absent
:func:`is_available` is ``False`` and the pipeline stays in core mode.

Honest progress
---------------
Glossing a long file makes hundreds of local-LLM calls and used to look frozen.
So enrichment runs in two steps, using only hub primitives (no fork): first the
cheap non-gloss stages (segmentation → morphology → difficulty → vocab), which
tell us how many glosses are needed; then the hub's own ``apply_glosses`` with a
wrapped provider that reports ``(done, total)`` on every real LLM call — a true
"sentence X of N" signal on any machine. ``total`` counts only *uncached* calls
(``plan_glosses``), so re-runs that hit the cache report near-instant completion.

Enrichment degrades gracefully to whatever the install supports — morphology
needs the ``classla`` extra; difficulty/vocab need the hub's ``data/``+``config/``
— and sentence glosses always survive.
"""

from __future__ import annotations

from collections.abc import Callable
from importlib.util import find_spec

from .contract import EnrichedDocument

# Reports enrichment progress as (done, total) uncached local-LLM gloss calls.
ProgressFn = Callable[[int, int], None]


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
    on_progress: ProgressFn | None = None,
) -> EnrichedDocument:
    """Enrich ``text`` via the razbiram-nlp hub and return a listen document.

    ``on_progress(done, total)`` fires per uncached gloss call, for a live bar.
    Raises :class:`EnrichmentUnavailable` if the hub is not installed — callers
    should check :func:`is_available` first (the pipeline does).
    """
    if not is_available():
        raise EnrichmentUnavailable(
            "razbiram-nlp is not installed. Install the enrichment plugin with "
            "'pip install razbiram-listen[enrich]' to get glosses and CEFR."
        )
    hub_doc = _enrich_without_gloss(text, gloss_lang)
    if gloss_lang is not None:
        _gloss_with_progress(
            hub_doc, gloss_lang=gloss_lang, gloss_model=gloss_model, on_progress=on_progress
        )
    # Convert the hub's EnrichedDocument into our shape-compatible copy.
    return EnrichedDocument.model_validate(hub_doc.model_dump())


def _enrich_without_gloss(text: str, gloss_lang: str | None):
    """Run the cheap stages (no LLM). Degrades if hub data/config is missing."""
    from razbiram_nlp import enrich_text

    stages = _available_stages(gloss_lang) - {"gloss"}
    try:
        return enrich_text(text, gloss_lang=None, stages=stages)
    except FileNotFoundError:
        # difficulty/vocab resources aren't available in a bare install; drop them
        # so segmentation (+ morphology) still runs and sentence glosses survive.
        return enrich_text(text, gloss_lang=None, stages=stages - {"difficulty", "vocab"})


def _gloss_with_progress(
    doc,
    *,
    gloss_lang: str,
    gloss_model: str | None,
    on_progress: ProgressFn | None,
) -> None:
    """Apply glosses to ``doc`` in place via the hub, reporting per-call progress."""
    from razbiram_nlp.cache import GlossCache
    from razbiram_nlp.gloss import (
        GlossProvider,
        OllamaGlossProvider,
        apply_glosses,
        plan_glosses,
    )

    base: GlossProvider = (
        OllamaGlossProvider(model=gloss_model) if gloss_model else OllamaGlossProvider()
    )
    cache = GlossCache()
    total = plan_glosses(doc.sentences, doc.vocab, cache=cache, lang=gloss_lang).computed
    done = 0
    if on_progress:
        on_progress(done, total)

    def bump() -> None:
        nonlocal done
        done += 1
        if on_progress:
            on_progress(done, total)

    class _ProgressProvider(GlossProvider):
        """Wraps the real provider to count each uncached LLM call."""

        def __init__(self) -> None:
            self.name = base.name

        def gloss_word(self, *, surface: str, lemma: str, context: str, lang: str) -> str:
            result = base.gloss_word(surface=surface, lemma=lemma, context=context, lang=lang)
            bump()
            return result

        def gloss_sentence(self, *, sentence: str, lang: str) -> str:
            result = base.gloss_sentence(sentence=sentence, lang=lang)
            bump()
            return result

    apply_glosses(
        doc.sentences, doc.vocab, provider=_ProgressProvider(), cache=cache, lang=gloss_lang
    )


def _available_stages(gloss_lang: str | None) -> set[str]:
    """The stages this install can run: morphology only if ``classla`` is present."""
    stages = {"segmentation", "difficulty", "vocab"}
    if find_spec("classla") is not None:
        stages.add("morphology")
    if gloss_lang is not None:
        stages.add("gloss")
    return stages

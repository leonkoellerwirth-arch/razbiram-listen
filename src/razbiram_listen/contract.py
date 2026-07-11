"""The EnrichedDocument contract — razbiram-listen's shape-compatible copy.

razbiram-listen consumes the shared ``EnrichedDocument`` contract from the
razbiram-nlp hub (ECOSYSTEM §2/§3). But the hub is an **optional enrichment
plugin** here (``pip install razbiram-listen[enrich]``): the core — transcribe →
align → karaoke — must run with no hub installed. Since a document model is
needed even in core mode, this module holds a copy of the contract that is kept
**shape-identical** to the hub's ``razbiram_nlp.models`` (same field names, JSON
keys, defaults, and constraints).

Not a fork — a mirror, guarded against drift:
- When razbiram-nlp *is* installed, ``tests/test_contract_compat.py`` round-trips
  a hub ``EnrichedDocument`` through this model and back and asserts equality, so
  any divergence fails CI (the house evaluator principle, ECOSYSTEM §5).
- The coupling exists only because the hub ships no published JSON Schema yet
  (tracked in HANDOFF / BIBLE). This arrangement is recorded as a hub mini-ADR
  (ECOSYSTEM §6): *razbiram-nlp as an optional enrichment plugin for listen.*

Keep every change here in lock-step with ``razbiram_nlp/models.py``.
"""

from __future__ import annotations

import json
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

# The CEFR-oriented difficulty bands, from easiest to hardest. Mirrors the hub.
CEFRBand = Literal["A1", "A2", "B1", "B2", "C1", "C2"]
CEFR_ORDER: tuple[str, ...] = ("A1", "A2", "B1", "B2", "C1", "C2")

# Coarse token classes produced by segmentation, before morphology runs.
TokenKind = Literal["word", "punct", "number", "other"]


class _Frozen(BaseModel):
    """Base for value objects: forbid unknown fields so contract drift is loud."""

    model_config = ConfigDict(extra="forbid")


class Gloss(_Frozen):
    """A short, context-sensitive translation of a token or sentence."""

    lang: str = Field(description="Target language code, e.g. 'de' or 'en'.")
    text: str = Field(description="The gloss itself; short (≤ ~5 words for tokens).")
    provider: str = Field(description="Which provider produced it, e.g. 'ollama' or 'claude'.")
    cached: bool = Field(default=False, description="True if served from the local cache.")


class Token(_Frozen):
    """One token: surface form plus every annotation the pipeline attached."""

    text: str = Field(description="Surface form exactly as it appears in the source.")
    kind: TokenKind = Field(description="Coarse class from segmentation.")
    start: int = Field(ge=0, description="Character offset of the token start in the source text.")
    end: int = Field(ge=0, description="Character offset one past the token end.")

    # --- Filled by the morphology stage (None if it did not run) ---
    lemma: str | None = Field(default=None, description="Dictionary form of the word.")
    upos: str | None = Field(default=None, description="Universal POS tag, e.g. 'NOUN', 'VERB'.")
    feats: dict[str, str] = Field(
        default_factory=dict,
        description="Universal morphological features, e.g. {'Case': 'Nom', 'Definite': 'Def'}.",
    )

    # --- Filled by the difficulty stage (None if it did not run) ---
    difficulty: float | None = Field(
        default=None, ge=0.0, le=1.0, description="Per-word difficulty score in [0, 1]."
    )
    band: str | None = Field(default=None, description="Heuristic CEFR band for this word.")


class Sentence(_Frozen):
    """One sentence: its text, its tokens, and an optional sentence-level gloss."""

    text: str
    start: int = Field(ge=0)
    end: int = Field(ge=0)
    tokens: list[Token] = Field(default_factory=list)
    gloss: Gloss | None = Field(default=None, description="Whole-sentence gloss, if requested.")


class VocabEntry(_Frozen):
    """One deduplicated vocabulary item for the whole document."""

    lemma: str
    upos: str | None = Field(default=None, description="POS of the most frequent surface form.")
    count: int = Field(ge=1, description="Occurrences of this lemma in the document.")
    freq_rank: int | None = Field(
        default=None,
        ge=1,
        description="Global frequency rank (1 = most common). None if not in the frequency list.",
    )
    difficulty: float | None = Field(default=None, ge=0.0, le=1.0)
    band: str | None = Field(default=None, description="Heuristic CEFR band for this lemma.")
    gloss: Gloss | None = Field(default=None)


class DifficultySummary(_Frozen):
    """The document-level difficulty estimate and the evidence behind it."""

    band: str = Field(description="Overall heuristic CEFR band for the document.")
    confidence: float = Field(
        ge=0.0, le=1.0, description="How concentrated the word bands are around the overall band."
    )
    band_distribution: dict[str, float] = Field(
        default_factory=dict, description="Fraction of scored words in each band (sums to ~1)."
    )
    mean_sentence_length: float = Field(
        ge=0.0, description="Mean number of word tokens per sentence."
    )
    scored_words: int = Field(ge=0, description="How many word tokens the estimate is based on.")


class EnrichedDocument(_Frozen):
    """The full enrichment result — the object the frontend renders.

    A shape-compatible copy of ``razbiram_nlp.EnrichedDocument`` (see module
    docstring). In core mode only ``text``/``lang``/``stages``/``sentences`` are
    populated; the enrichment fields stay empty until the plugin fills them.
    """

    text: str = Field(description="The original input text, verbatim.")
    lang: str = Field(default="bg", description="Source language (Bulgarian).")
    stages: list[str] = Field(
        default_factory=list, description="Which pipeline stages actually ran, in order."
    )
    sentences: list[Sentence] = Field(default_factory=list)
    vocab: list[VocabEntry] = Field(default_factory=list)
    difficulty: DifficultySummary | None = Field(default=None)

    def to_json(self, *, indent: int | None = 2) -> str:
        """Serialise to a JSON string the frontend can consume directly."""
        return json.dumps(self.model_dump(mode="json"), ensure_ascii=False, indent=indent)

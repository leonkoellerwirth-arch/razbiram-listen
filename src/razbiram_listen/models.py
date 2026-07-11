"""ListenDocument — the audio-aware extension of the EnrichedDocument contract.

razbiram-listen extends the shared contract *only* through the optional fields the
ecosystem reserves for this purpose (``timings``, ``audioRef``) plus the mandatory
``schemaVersion`` (ECOSYSTEM §2). The base ``EnrichedDocument`` comes from
:mod:`razbiram_listen.contract` — a shape-compatible mirror of the razbiram-nlp
hub contract, kept in lock-step so the core runs without the hub (which is an
optional enrichment plugin); a compatibility test guards against drift.

The emitted ``.listen.json`` is therefore a superset of an EnrichedDocument:
every consumer that reads EnrichedDocument (razbiram-anki, the Studio) can read
it too, ignoring the extra fields; the Karaoke viewer additionally uses the
timings to sync text to audio.

Join model
----------
Timings reference the document by *stable keys*, never by duplicating the token
tree:

- a :class:`TokenTiming` carries ``token_start`` — the character offset of the
  token in ``EnrichedDocument.text`` (i.e. ``Token.start``) — so the viewer maps
  a timing to a token without re-tokenising;
- a :class:`SegmentTiming` carries the ``sentence_index`` into
  ``EnrichedDocument.sentences``.
"""

from __future__ import annotations

import json
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from .contract import EnrichedDocument

# SemVer of the .listen.json shape. Bump on any breaking change and record it in
# CHANGELOG.md (ECOSYSTEM §2).
SCHEMA_VERSION = "1.0.0"

# The razbiram-nlp release whose EnrichedDocument contract this build reads and
# writes. The hub does not yet stamp its own schemaVersion (tracked in HANDOFF),
# so we record the source release here for provenance.
ENRICHED_CONTRACT_SOURCE = "razbiram-nlp@v0.1.0"

# How a token's playback window was obtained: a Whisper word-level timestamp, or
# a coarser sentence/segment fallback when no word timing aligned (see align.py).
TimingSource = Literal["word", "segment"]


class _Frozen(BaseModel):
    """Base for value objects: forbid unknown fields so contract drift is loud."""

    model_config = ConfigDict(extra="forbid")


class AudioRef(_Frozen):
    """A reference to the source audio — a filename and playback metadata only.

    The repo never stores or embeds the audio bytes (Briefing §8, BYO-audio); the
    viewer resolves the file locally via a picker and matches it by ``filename``.
    """

    filename: str = Field(description="Basename of the source audio the timings refer to.")
    duration_s: float | None = Field(
        default=None, ge=0.0, description="Total audio duration in seconds, if known."
    )


class TokenTiming(_Frozen):
    """The playback window for a single token, keyed by its character offset."""

    token_start: int = Field(
        ge=0,
        description="Char offset of the token in the source text (== Token.start); the join key.",
    )
    t_start: float = Field(ge=0.0, description="Playback start, in seconds.")
    t_end: float = Field(ge=0.0, description="Playback end, in seconds.")
    source: TimingSource = Field(description="Whisper word timing, or segment-level fallback.")
    confidence: float | None = Field(
        default=None, ge=0.0, le=1.0, description="Alignment confidence in [0, 1], if scored."
    )


class SegmentTiming(_Frozen):
    """The playback window for one sentence/segment, keyed by sentence index."""

    sentence_index: int = Field(ge=0, description="Index into EnrichedDocument.sentences.")
    t_start: float = Field(ge=0.0, description="Playback start, in seconds.")
    t_end: float = Field(ge=0.0, description="Playback end, in seconds.")


class ListenTimings(_Frozen):
    """All audio timings for a document: per token and per sentence."""

    tokens: list[TokenTiming] = Field(default_factory=list)
    segments: list[SegmentTiming] = Field(default_factory=list)


class ListenDocument(EnrichedDocument):
    """An ``EnrichedDocument`` aligned to audio.

    Adds the mandatory ``schemaVersion`` plus the reserved optional extension
    fields ``audioRef`` and ``timings``. The camelCase JSON keys match the names
    the ecosystem contract reserves (ECOSYSTEM §2); all inherited fields keep the
    hub's own key names unchanged.
    """

    # Accept both the Python field name and its JSON alias on input.
    model_config = ConfigDict(populate_by_name=True)

    schema_version: str = Field(
        default=SCHEMA_VERSION,
        alias="schemaVersion",
        description="SemVer of the .listen.json shape.",
    )
    audio_ref: AudioRef | None = Field(default=None, alias="audioRef")
    timings: ListenTimings | None = Field(default=None)

    @classmethod
    def from_enriched(
        cls,
        doc: EnrichedDocument,
        *,
        audio_ref: AudioRef | None = None,
        timings: ListenTimings | None = None,
    ) -> ListenDocument:
        """Wrap a hub-produced ``EnrichedDocument`` as a ``ListenDocument``.

        This is how the pipeline (M4) attaches alignment results without
        re-deriving any enrichment: it enriches via the hub, then wraps.
        """
        return cls(**doc.model_dump(), audio_ref=audio_ref, timings=timings)

    def to_json(self, *, indent: int | None = 2) -> str:
        """Serialise to the ``.listen.json`` string using the contract's JSON keys."""
        return json.dumps(
            self.model_dump(mode="json", by_alias=True), ensure_ascii=False, indent=indent
        )

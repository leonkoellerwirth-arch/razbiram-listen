"""Core segmentation — build an EnrichedDocument from Whisper output, no hub.

razbiram-nlp is an optional enrichment plugin (``[enrich]``), so the core path
must produce a document with no hub installed. This turns a
:class:`~razbiram_listen.transcribe.Transcription` into a
:class:`~razbiram_listen.contract.EnrichedDocument` using only Whisper's own
sentence-ish segments and words: one sentence per segment, tokenised into
word/number/punctuation tokens with character offsets into the document text.

No morphology, difficulty, or glosses are produced here — those are the plugin's
job (:mod:`razbiram_listen.enrichment`). The enrichment fields simply stay empty,
which is still a valid EnrichedDocument; the karaoke viewer renders the tokens and
syncs them to audio via the aligner all the same.
"""

from __future__ import annotations

import re

from .contract import EnrichedDocument, Sentence, Token, TokenKind
from .transcribe import Transcription

# A token is a run of word characters (``\w`` matches Cyrillic letters and digits
# on ``str``) or a single non-word, non-space character (punctuation). Whitespace
# is skipped, so token spans never overlap and every ``start`` offset is unique.
_TOKEN_RE = re.compile(r"\w+|[^\w\s]")


def _classify(surface: str) -> TokenKind:
    """Coarse token class, matching the hub's segmentation kinds."""
    if surface.isdigit():
        return "number"
    if surface[0].isalnum():
        return "word"
    return "punct"


def build_core_document(transcription: Transcription) -> EnrichedDocument:
    """Build a hub-free EnrichedDocument (text + sentences + tokens) from Whisper.

    Character offsets are into :attr:`Transcription.text` — reconstructed here
    exactly as the transcriber does (segments joined, then outer-trimmed) — so a
    token's ``start`` is the same join key the aligner and viewer use.
    """
    joined = "".join(seg.text for seg in transcription.segments)
    text = joined.strip()
    lead = len(joined) - len(joined.lstrip())  # chars the outer lstrip() removed

    sentences: list[Sentence] = []
    cursor = 0  # running offset into ``joined``
    for seg in transcription.segments:
        seg_off = cursor
        cursor += len(seg.text)

        tokens: list[Token] = []
        for m in _TOKEN_RE.finditer(seg.text):
            start = seg_off + m.start() - lead
            if start < 0 or start >= len(text):
                continue  # inside the region the outer strip removed
            surface = m.group()
            tokens.append(
                Token(text=surface, kind=_classify(surface), start=start, end=start + len(surface))
            )

        sent_text = seg.text.strip()
        if not sent_text:
            continue
        s_start = max(seg_off + (len(seg.text) - len(seg.text.lstrip())) - lead, 0)
        sentences.append(
            Sentence(text=sent_text, start=s_start, end=s_start + len(sent_text), tokens=tokens)
        )

    return EnrichedDocument(
        text=text,
        lang=transcription.language or "bg",
        stages=["transcription"],
        sentences=sentences,
    )

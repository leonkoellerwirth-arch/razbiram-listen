"""Alignment stage — the quality heart of razbiram-listen (M3).

Maps Whisper word timings (:class:`~razbiram_listen.transcribe.Transcription`)
onto the razbiram tokens of an ``EnrichedDocument``, producing the
:class:`~razbiram_listen.models.ListenTimings` the Karaoke viewer plays back.

Why not a character-offset join?
--------------------------------
When the document text is exactly the Whisper transcript, token offsets line up
perfectly — but the transcript-edit mode (M7) lets a user change a word and
re-enrich, after which offsets diverge. So alignment is done on **content**, not
positions: both sides are compared by a *normalised* surface form (lower-cased,
outer punctuation stripped), which is case- and punctuation-tolerant as the
briefing (§2, step 3) requires.

The algorithm
-------------
Both token and word streams are in the same reading order. We walk them with a
two-pointer greedy matcher and a small look-ahead window that resynchronises
across the usual drift — Whisper dropping a word, or razbiram splitting one
token where Whisper kept two together:

- equal normalised forms → the token takes the word's ``[start, end]`` window
  (``source="word"``);
- a token with no matching word falls back to its **sentence's** segment window
  (``source="segment"``);
- sentences with no matched words get a segment window interpolated from their
  nearest matched neighbours.

``AlignmentStats.coverage`` (matched ÷ total word tokens) is the regression
signal the Golden-Set asserts on.
"""

from __future__ import annotations

import re
from collections import defaultdict
from dataclasses import dataclass

from razbiram_nlp import EnrichedDocument

from .models import ListenTimings, SegmentTiming, TokenTiming
from .transcribe import TranscribedWord, Transcription

# Token kinds that correspond to a spoken word and therefore carry a timing.
# Punctuation is never highlighted or seeked to, so it gets no timing.
_TIMED_KINDS = frozenset({"word", "number"})

# How far ahead to look when the two streams drift out of step.
_LOOKAHEAD = 3

# Strip leading/trailing non-word characters; ``\w`` matches Cyrillic and digits
# on ``str`` patterns, so this keeps letters/numbers and drops outer punctuation.
_OUTER_PUNCT = re.compile(r"^\W+|\W+$")


def _norm(surface: str) -> str:
    """Normalised form for matching: outer punctuation stripped, lower-cased."""
    return _OUTER_PUNCT.sub("", surface).lower()


@dataclass(frozen=True)
class AlignmentStats:
    """How well the Whisper timings covered the document's word tokens."""

    total_word_tokens: int
    matched_word_tokens: int

    @property
    def coverage(self) -> float:
        """Fraction of word tokens matched to a real Whisper word, in [0, 1]."""
        if self.total_word_tokens == 0:
            return 1.0
        return self.matched_word_tokens / self.total_word_tokens


@dataclass(frozen=True)
class AlignmentResult:
    """The timings plus the alignment quality stats."""

    timings: ListenTimings
    stats: AlignmentStats


def _ahead(seq: list[str], start: int, target: str, window: int) -> int | None:
    """Index of ``target`` in ``seq[start : start + window]``, or None."""
    for k in range(start, min(len(seq), start + window)):
        if seq[k] == target:
            return k
    return None


def align(doc: EnrichedDocument, transcription: Transcription) -> AlignmentResult:
    """Align Whisper word timings onto the document's tokens.

    Parameters
    ----------
    doc:
        The enriched transcript (tokens come from ``doc.sentences[*].tokens``).
    transcription:
        The Whisper output whose word timings are mapped onto those tokens.
    """
    # Flatten timed tokens, remembering which sentence each belongs to.
    word_tokens: list[tuple[int, object]] = [
        (si, tok)
        for si, sent in enumerate(doc.sentences)
        for tok in sent.tokens
        if tok.kind in _TIMED_KINDS
    ]
    ntoks = [_norm(tok.text) for _, tok in word_tokens]

    # Drop Whisper "words" that are pure punctuation (normalise to empty).
    norm_words: list[tuple[str, TranscribedWord]] = [
        (n, w) for w in transcription.words if (n := _norm(w.text))
    ]
    nwords = [n for n, _ in norm_words]

    matches = _match(ntoks, nwords, norm_words, word_tokens)

    # Per-sentence windows from the matched words (min start … max end).
    matched_windows: dict[int, tuple[float, float]] = {}
    per_sentence: dict[int, list[tuple[float, float]]] = defaultdict(list)
    for si, tok in word_tokens:
        w = matches.get(tok.start)
        if w is not None:
            per_sentence[si].append((w.start, w.end))
    for si, wins in per_sentence.items():
        matched_windows[si] = (min(a for a, _ in wins), max(b for _, b in wins))

    windows = _fill_gaps(matched_windows, len(doc.sentences))

    # Token timings: matched → word window; unmatched → sentence window fallback.
    token_timings: list[TokenTiming] = []
    for si, tok in word_tokens:
        w = matches.get(tok.start)
        if w is not None:
            token_timings.append(
                TokenTiming(
                    token_start=tok.start,
                    t_start=w.start,
                    t_end=w.end,
                    source="word",
                    confidence=w.probability,
                )
            )
        elif si in windows:
            start, end = windows[si]
            token_timings.append(
                TokenTiming(token_start=tok.start, t_start=start, t_end=end, source="segment")
            )
    token_timings.sort(key=lambda t: t.token_start)

    segment_timings = [
        SegmentTiming(sentence_index=si, t_start=start, t_end=end)
        for si, (start, end) in sorted(windows.items())
    ]

    stats = AlignmentStats(
        total_word_tokens=len(word_tokens),
        matched_word_tokens=len(matches),
    )
    return AlignmentResult(
        timings=ListenTimings(tokens=token_timings, segments=segment_timings),
        stats=stats,
    )


def _match(
    ntoks: list[str],
    nwords: list[str],
    norm_words: list[tuple[str, TranscribedWord]],
    word_tokens: list[tuple[int, object]],
) -> dict[int, TranscribedWord]:
    """Two-pointer greedy match with look-ahead resync.

    Returns a map from ``token.start`` to the Whisper word it matched.
    """
    matches: dict[int, TranscribedWord] = {}
    i = j = 0
    while i < len(ntoks) and j < len(nwords):
        if ntoks[i] == nwords[j]:
            matches[word_tokens[i][1].start] = norm_words[j][1]
            i += 1
            j += 1
            continue
        # Drift: is this token a Whisper word just ahead (Whisper inserted words),
        # or is this word a token just ahead (razbiram split an extra token)?
        aj = _ahead(nwords, j + 1, ntoks[i], _LOOKAHEAD)
        ai = _ahead(ntoks, i + 1, nwords[j], _LOOKAHEAD)
        if aj is not None and (ai is None or (aj - j) <= (ai - i)):
            j = aj  # skip the surplus Whisper words
        elif ai is not None:
            i = ai  # leave the surplus tokens unmatched
        else:
            # Unresolved: treat as a substitution and keep both streams moving.
            i += 1
            j += 1
    return matches


def _fill_gaps(
    matched_windows: dict[int, tuple[float, float]], n_sentences: int
) -> dict[int, tuple[float, float]]:
    """Interpolate a window for sentences with no matched words.

    Only sentences *between* two matched neighbours are filled (from the previous
    sentence's end to the next sentence's start); a leading/trailing run with no
    match on one side is left without a segment window rather than inventing a
    degenerate zero-length one.
    """
    windows = dict(matched_windows)
    for si in range(n_sentences):
        if si in matched_windows:
            continue
        prev = next((k for k in range(si - 1, -1, -1) if k in matched_windows), None)
        nxt = next((k for k in range(si + 1, n_sentences) if k in matched_windows), None)
        if prev is not None and nxt is not None:
            windows[si] = (matched_windows[prev][1], matched_windows[nxt][0])
    return windows

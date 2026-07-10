"""Golden-Set for the alignment stage (M3) — the repo's core quality gate.

Each ``tests/golden/*.json`` case is hand-verified: a list of razbiram tokens, a
list of Whisper words with timings, and the exact expected token→timing mapping
plus coverage. The loader builds an ``EnrichedDocument`` and a ``Transcription``
from the case (deriving character offsets so the fixtures stay readable), runs
``align``, and asserts the result. Any change to ``align.py`` must keep every
case green (ECOSYSTEM §5).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from razbiram_nlp import EnrichedDocument
from razbiram_nlp.models import Sentence, Token

from razbiram_listen.align import align
from razbiram_listen.transcribe import TranscribedSegment, TranscribedWord, Transcription

GOLDEN_DIR = Path(__file__).parent / "golden"
CASES = sorted(GOLDEN_DIR.glob("*.json"))


def _build_document(case: dict[str, Any]) -> EnrichedDocument:
    """Assemble an EnrichedDocument, laying out tokens into text with real offsets.

    Spacing rule: word/number/other tokens are space-separated; punctuation
    attaches to the preceding token — enough to produce natural Bulgarian text
    and unique character offsets (the token identity key).
    """
    pieces: list[str] = []
    pos = 0
    sentences: list[Sentence] = []
    first = True
    spans: list[tuple[int, int]] = []  # (start, end) per sentence

    for sent in case["sentences"]:
        tokens: list[Token] = []
        sent_start: int | None = None
        for tok in sent["tokens"]:
            surface, kind = tok["text"], tok["kind"]
            if not first and kind != "punct":
                pieces.append(" ")
                pos += 1
            start = pos
            pieces.append(surface)
            pos += len(surface)
            tokens.append(Token(text=surface, kind=kind, start=start, end=pos))
            if sent_start is None:
                sent_start = start
            first = False
        assert sent_start is not None
        spans.append((sent_start, pos))
        sentences.append(Sentence(text="", start=sent_start, end=pos, tokens=tokens))

    text = "".join(pieces)
    # Backfill each sentence's text now that the full string exists.
    sentences = [
        s.model_copy(update={"text": text[span[0] : span[1]]})
        for s, span in zip(sentences, spans, strict=True)
    ]
    return EnrichedDocument(text=text, lang="bg", stages=["segment"], sentences=sentences)


def _build_transcription(case: dict[str, Any]) -> Transcription:
    words = [
        TranscribedWord(
            text=w["text"], start=w["start"], end=w["end"], probability=w.get("probability")
        )
        for w in case["whisper_words"]
    ]
    end = words[-1].end if words else 0.0
    segment = TranscribedSegment(
        text=" ".join(w.text for w in words),
        start=words[0].start if words else 0.0,
        end=end,
        words=words,
    )
    return Transcription(
        text=" ".join(w.text for w in words),
        language="bg",
        duration=end,
        model="golden",
        segments=[segment],
    )


def _token_start_by_text(doc: EnrichedDocument) -> dict[str, int]:
    """Map each timed token's surface to its char offset (fixtures keep them unique)."""
    starts: dict[str, int] = {}
    for sent in doc.sentences:
        for tok in sent.tokens:
            if tok.kind in {"word", "number"}:
                assert tok.text not in starts, f"duplicate token text in fixture: {tok.text}"
                starts[tok.text] = tok.start
    return starts


@pytest.mark.parametrize("case_path", CASES, ids=[p.stem for p in CASES])
def test_golden_alignment(case_path: Path) -> None:
    case = json.loads(case_path.read_text(encoding="utf-8"))
    doc = _build_document(case)
    transcription = _build_transcription(case)

    result = align(doc, transcription)
    expected = case["expected"]

    assert result.stats.coverage == pytest.approx(expected["coverage"])

    starts = _token_start_by_text(doc)
    produced = {t.token_start: t for t in result.timings.tokens}

    for exp in expected["token_timings"]:
        start = starts[exp["text"]]
        assert start in produced, f"no timing produced for token {exp['text']!r}"
        got = produced[start]
        assert got.source == exp["source"], f"{exp['text']}: source"
        assert got.t_start == pytest.approx(exp["t_start"]), f"{exp['text']}: t_start"
        assert got.t_end == pytest.approx(exp["t_end"]), f"{exp['text']}: t_end"

    got_segments = {s.sentence_index: s for s in result.timings.segments}
    for exp in expected["segments"]:
        si = exp["sentence_index"]
        assert si in got_segments, f"no segment timing for sentence {si}"
        assert got_segments[si].t_start == pytest.approx(exp["t_start"])
        assert got_segments[si].t_end == pytest.approx(exp["t_end"])


def test_golden_set_is_non_trivial() -> None:
    # Guard against an empty glob silently passing the suite.
    assert len(CASES) >= 5

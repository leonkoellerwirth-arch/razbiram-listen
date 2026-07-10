# HANDOFF.md — razbiram-listen

Session-to-session hand-offs. Public — no business internals. Newest first.

---

## Session 1 — M3 (align, the core)

### Done
- `align.py`: `align(doc, transcription) -> AlignmentResult` (`ListenTimings` +
  `AlignmentStats`). Content-based (not char-offset) so it survives transcript
  edits (M7): order-preserving two-pointer match on **normalised** surfaces
  (lower-cased, outer punctuation stripped → case/punct tolerant), with a
  look-ahead (=3) resync for Whisper insertions/deletions. Unmatched word tokens
  fall back to their sentence window (`source="segment"`); gap sentences are
  interpolated from matched neighbours. Punct tokens carry no timing by design.
- **Golden-Set:** `tests/golden/*.json` (7 hand-verified cases: clean 1:1,
  inline punctuation, case-insensitivity, dropped word, extra/filler word,
  whole-sentence gap interpolation, number token) + `test_align_golden.py`.
  `AlignmentStats.coverage` is the regression signal. **All green** (21 tests
  total, 1 slow deselected). ruff + format clean.

### Hub-check record (ECOSYSTEM §3)
- No hub equivalent for audio alignment. Reused hub types only: `EnrichedDocument`,
  `Token`, `Sentence`. `ListenTimings`/`TokenTiming`/`SegmentTiming` are the M1
  models. Nothing reimplemented.

### Design note
- Matching is on content, not character offsets, on purpose: it keeps alignment
  correct after the M7 transcript-edit re-enrich, where token offsets diverge
  from the original Whisper text. Fallbacks degrade gracefully (segment window).

### Next (M4 — pipeline + CLI)
- `pipeline.py`: transcribe → `razbiram_nlp.enrich_text(text, gloss_lang=…)` →
  `align` → `ListenDocument.from_enriched(doc, audio_ref=…, timings=…)` →
  `.listen.json`. Wire `cli.py` `process --audio --gloss --out`. Keep the real
  enrich/whisper behind `slow`; unit-test the orchestration with fakes.

---

## Session 1 — M2 (transcribe)

### Done
- `transcribe.py`: `Transcriber` wrapping faster-whisper with word-level
  timestamps always on; faster-whisper types mapped to our own value objects
  (`Transcription`/`TranscribedSegment`/`TranscribedWord`) at the boundary so
  `align.py` won't depend on faster-whisper. Model is **injectable** (fake in
  units); `faster_whisper` imported lazily inside the loader. rich progress bar.
- Tests: 7 mocked unit tests + 1 real `slow` test (synthesises a tone WAV, runs
  the real `tiny` model — verified locally, 6s). ruff + pytest green (13 unit /
  1 slow).

### Hub-check record (ECOSYSTEM §3)
- Transcription has **no hub equivalent** (the hub has no audio concept);
  faster-whisper is the external engine. Nothing reimplemented.

### Next (M3 — align, the core)
- `align.py`: map `Transcription.words` (Whisper timings) onto the razbiram
  tokens in the EnrichedDocument. Normalised text match, punctuation/case
  tolerant; segment-timing fallback on mismatch. **Golden-Set** of 5–8 hand-
  verified cases — do not advance to M4 until green.

---

## Session 1 — M0 + M1 (repo bootstrap, models, scaffold, CI)

### Done
- **M0:** `CLAUDE.md` created, anchored to the binding ECOSYSTEM standard.
  Git initialised, wired to `origin`
  (`github.com/leonkoellerwirth-arch/razbiram-listen`), local `main` based on the
  existing remote commit.
- **Licence:** replaced the repo's default **GPL-3** with **MIT** (ECOSYSTEM
  Zonen-Tabelle / Briefing §3). [D1]
- **Hub tag:** created and pushed **`v0.1.0`** on razbiram-nlp so this repo can
  pin a reproducible dependency. [D2]
- **M1:** `pyproject.toml` (hub pinned `@v0.1.0`), `ListenDocument` model
  (`src/razbiram_listen/models.py`), package `__init__`, CLI scaffold, contract
  tests (`tests/test_models.py`), CI (`ruff + pytest`, net-free), `.gitignore`,
  `.env.example`, `BIBLE.md`, `CHANGELOG.md`, `examples/SOURCES.md`, README
  skeleton.

### Hub-check record (mandatory before new modules — ECOSYSTEM §3 / CLAUDE.md #1)
- **Reused, not reimplemented:** `EnrichedDocument`, `Token`, `Sentence` imported
  from `razbiram_nlp`. razbiram-nlp core deps are light (pydantic, pyyaml, click,
  rich); the heavy `classla` morphology model is an optional extra loaded lazily,
  so importing the contract keeps CI fast and net-free.
- **New here (no hub equivalent):** audio timings + audio reference —
  `TokenTiming`, `SegmentTiming`, `ListenTimings`, `AudioRef`, `ListenDocument`.
  These are genuinely listen-specific (the hub has no audio concept).

### Contract gaps found in the hub (raise as ADRs, ECOSYSTEM §6)
1. **No `schemas/` JSON Schema** — ECOSYSTEM §2 references
   `schemas/enriched-document.vN.json`; it does not exist yet. We consume the
   Pydantic model directly and pin the hub tag.
2. **No `schemaVersion` on `EnrichedDocument`** — the base contract carries no
   version field. `ListenDocument` declares its own (`schemaVersion=1.0.0`) and
   records the hub source in `ENRICHED_CONTRACT_SOURCE`.
3. **ECOSYSTEM doc is untracked in the hub** — it lives at
   `razbiram-nlp/docs/razbiram-ECOSYSTEM.md` (not committed; filename differs from
   the `ECOSYSTEM.md` the remote-fallback URL expects). The raw-GitHub fallback
   URL in CLAUDE.md will not resolve until the hub commits it as
   `docs/ECOSYSTEM.md`. **Flagged for the author.**

### Next (M2 — transcribe)
- `transcribe.py`: faster-whisper wrapper, word-level timestamps, progress via
  `rich`. Import faster-whisper lazily inside functions so unit tests stay
  model-free; mock the model in unit tests, add exactly one real `slow` test.

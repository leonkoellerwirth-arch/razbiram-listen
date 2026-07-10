# HANDOFF.md — razbiram-listen

Session-to-session hand-offs. Public — no business internals. Newest first.

---

## Session 1 — M5 (Viewer MVP)

### Done
- `viewer/` — Vite + **vanilla TypeScript** (light, per briefing), local-first
  (file pickers, no upload/server/telemetry). Modules: `loadListen` (parse +
  shape-check), `sync` (pure active-token/-sentence lookup), `cefr` (band→class),
  `player` (audio + A–B loop + rate), `popover`, `karaoke` (render + highlight +
  click-to-seek + auto-scroll), `main` (wiring, tempo, loop, dark toggle).
- **Design identity reused** from the family (razbiram-anki/Studio): tokens +
  CEFR scale + node-mark + wordmark, as self-contained CSS (no Tailwind).
- Tests: 11 unit tests (sync/cefr/loadListen) via vitest. `npm run build`
  (tsc + vite) is clean. **CI:** new `viewer` job (build + tests).

### Hub-check / Rule-of-Three note (ECOSYSTEM §3)
- Three viewers now share the design tokens + CEFR scale (Studio, anki, listen).
  **Rule of Three is met** → extracting a shared `tokens.css` / `viewer-core`
  (badge, popover, token rendering) is now a live **ADR candidate** for the hub.
  For M5 the tokens were copied with attribution (as anki did), not yet extracted.

### Not covered here (by design)
- The bundled demo asset (own recorded audio + its `sample.listen.json`) is **M7**.
  Until then the viewer is exercised BYO: `razbiram-listen process` your own audio,
  then load both files.

### Next (M6 — Seed-Export)
- In the viewer: a ＋ on each word collects vocabulary; an export button produces
  (a) a razbiram Seed JSON and (b) a razbiram-anki-compatible EnrichedDocument
  subset. Roundtrip test through to a razbiram-anki deck.

---

## Session 1 — M4 (pipeline + CLI)

### Done
- `pipeline.py`: `process_audio()` wires transcribe (M2) → `razbiram_nlp.enrich_text`
  (hub, reused not reimplemented) → `align` (M3) → `ListenDocument.from_enriched`
  with `AudioRef` (filename + duration only — never the audio). Returns a
  `ProcessResult` (document + `AlignmentStats` + language/duration). Transcribe and
  enrich are **injectable seams** for net-free tests; real ones built lazily.
- `cli.py`: `razbiram-listen process --audio --out --gloss --model --language`,
  writes `.listen.json`, prints coverage; warns on <50% coverage.
- Tests: 3 net-free orchestration tests (fake transcriber + fake/spy enrich) + 1
  real `slow` end-to-end (real Whisper `tiny` + hub segmentation only, no classla)
  — verified locally. 24 unit tests green, ruff + format clean.

### Hub-check record (ECOSYSTEM §3)
- Enrichment delegated to hub `enrich_text` (not reimplemented). Only transcribe +
  align + assembly are ours. `enrich_text(text, *, gloss_lang=…, stages=…)`.

### Milestone note
- End-to-end MP3 → `.listen.json` now works. First real CLI run downloads the
  Whisper model and (for morphology/gloss) the classla model — expected, documented.

### Next (M5 — Viewer MVP)
- Vite app under `viewer/`: load `.listen.json` + local audio (file picker, no
  upload), karaoke sync (active word highlight, click-to-seek), hover popover
  (lemma/POS/gloss/CEFR badge with the ecosystem colour scale), tempo + A-B loop,
  dark mode. Add the viewer build-check to CI.

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

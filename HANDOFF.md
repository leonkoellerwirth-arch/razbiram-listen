# HANDOFF.md — razbiram-listen

Session-to-session hand-offs. Public — no business internals. Newest first.

---

## Session 1 — M6 (Seed-Export) + §8 scoping

### Governance (BIBLE D6)
- **Briefing §8 scoped** by author-authorised amendment: a **user-supplied direct
  audio-URL / podcast RSS enclosure** import is now allowed; **streaming/DRM
  platform scraping (YouTube/Spotify/…) stays forbidden.** Recorded in the briefing
  §8 addendum, `CLAUDE.md` §5, and BIBLE D5/D6. Family-wide → **hub ADR candidate**.
- **Approved-but-not-yet-built feature:** a `--url`/paste import for open direct
  audio (podcast RSS enclosure or direct file the user has rights to) — fetches
  only that one named open file, transcribes locally. To build after M6.

### Done (M6)
- `viewer/src/seed.ts`: `SeedBasket` (dedupe by lemma) + `toRazbiramSeed` +
  `toCrowdAnkiDeck` (front = lemma, back = gloss; stable FNV-1a guids).
- Popover is now interactive (hover-bridge) with a ＋/✓ collect button; a sticky
  **seed bar** shows the count and exports both formats (download, no upload).
- Tests: `seed.test.ts` (6) incl. a **roundtrip** asserting the deck.json passes a
  mirror of razbiram-anki's `loadDeckJson` shape check. 17 viewer tests green,
  build clean.

### Roundtrip note
- The roundtrip is asserted against a *mirror* of razbiram-anki's CrowdAnki check.
  A stronger cross-repo check (feed the exported deck.json into razbiram-anki's
  `convertFile`) is available if we want it.

### Next (M7 — Politur)
- Own recorded Bulgarian example under `examples/sample-audio/` + its committed
  `sample.listen.json` + `SOURCES.md`; GIF/screenshots (light+dark); README polish;
  transcript-edit mode; fresh-clone acceptance. Then the approved open-URL import.

---

## Session 1 — M5.1 (Studio-style reading view) + policy note

### Policy decision (BIBLE D5)
- A "paste a YouTube/stream link → tool fetches it" request was **declined** —
  violates Briefing §8.1/§8.3 (no scraping, no download feature; local-only),
  platform ToS, and copyright. BYO-audio is the point. Compliant answer: drag &
  drop + a nicer reading UI, plus *own* local TTS to generate throwaway demo audio.

### Done
- Reworked the viewer reading area into a **Studio-style** view: per-sentence rows
  with a round **Listen** button (seek + play), a global **Show translation**
  toggle (sentence gloss), an overall **CEFR badge** header (doc estimate or the
  hardest word band), and language direction. Word-level karaoke highlight,
  click-to-seek, and auto-scroll retained.
- **Drag & drop** onto the loader card (routes .json / audio by type).
- Viewer build clean, 11 vitest tests still green.
- **Local demo (not committed):** `examples/_demo/` — own Bulgarian A2 text →
  macOS `say` (Daria bg_BG) → real pipeline (Whisper small, 73% word coverage) →
  `demo.listen.json` with own lemma/POS/CEFR + German glosses. `examples/_demo/`
  is git-ignored (TTS audio + throwaway). Lets the viewer be tested immediately.

### Next
- Finish M5 polish or proceed to **M6 — Seed-Export** (＋ per word → razbiram Seed
  JSON + razbiram-anki-compatible EnrichedDocument subset; roundtrip test).
- M7 ships the real own-recorded example under `examples/sample-audio/`.

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

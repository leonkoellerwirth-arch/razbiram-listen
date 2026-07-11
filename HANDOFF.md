# HANDOFF.md — razbiram-listen

Session-to-session hand-offs. Public — no business internals. Newest first.

---

## ▶ Resume here (current state)

**Released v0.1.0 → v0.2.0 (nlp optional plugin) → v0.3.0 (queue + local library).
Now v0.4.0 — translation as a switchable layer (default English; re-translate a
saved entry to DE/EN with no re-transcription) — built & verified (backend + real
Ollama via curl; viewer builds), committed on `main`.** Gate green. **Open step:
owner's browser check of the language-switch UI, then cut the v0.4.0 tag + release.**

- **What changed (0.3.0, BIBLE D8):** large audio runs as a **background job**
  (studio `POST /jobs` → bounded worker pool, default 2, `RAZBIRAM_LISTEN_WORKERS`),
  shown in a **queue panel** beside the reader; drop several → parallel. Results are
  **saved to a local library** (`$RAZBIRAM_LISTEN_HOME`/`~/.razbiram-listen`), audio
  kept for **one-click replay** (deletable per entry; transcript stays). Audio is
  **range-served** (206) so seeking works on big files. New: `library.py`, `jobs.py`,
  server endpoints (`/jobs`, `/library/...`), viewer `api.ts`/`queue.ts` + two-column
  layout. Uploads stream to disk in chunks. Verified via curl (submit→done→library,
  ranged 206, delete/remove-audio, traversal guard) + net-free unit tests.
- **Not yet verified by me:** the browser interaction (drag-drop, live queue,
  auto-open, seeking) — a live studio server is running for the owner to confirm.
- **What changed (0.2.0):** the core runs with **no razbiram-nlp installed**;
  `razbiram-nlp` is the optional `[enrich]` extra; `razbiram_listen.contract` is a
  drift-guarded copy of `EnrichedDocument`; enrichment is opt-in with honest
  "sentence X of N" progress. **BIBLE D7** + hub **ADR 005** (filed, hub `618e0f0`).
- **Try it:** `razbiram-listen studio` → drop audio → it queues, processes in the
  background, saves to the library, and replays with one click.
- **Next milestone — M7 (Politur):** own recorded Bulgarian example under
  `examples/sample-audio/` + committed `sample.listen.json` + `SOURCES.md`;
  GIF/screenshots (light+dark); **transcript-edit mode** in the viewer (the aligner
  is already content-based so it re-fits after edits); fresh-clone acceptance.
  Transcript quality on hard audio (Whisper `small`) is the known limiter — a
  selectable larger model is part of M7.
- **Deferred follow-ups:** package `viewer/dist` for a real pip install (studio
  serves it from the repo layout today); ask the hub to ship a JSON Schema +
  `schemaVersion` (would replace listen's hand-kept `contract.py`); "process another
  file" reset in studio.

---

## Session 4 — Translation as a switchable layer; default English (v0.4.0)

### Why
- Owner: transcription is expensive but separable from translation. Default should be
  **English**, and the user must be able to **choose DE/EN later** on an already-
  transcribed file — "später nur übersetzung" — without re-transcribing.

### Key insight
- Morphology/CEFR/lemma are **language-independent**; only glosses depend on the
  target language. So re-translating recomputes only sentence + word glosses on the
  existing structure → tokens/timings/audioRef/schemaVersion preserved, alignment
  intact, no re-Whisper. (BIBLE D9.)

### Done (v0.4.0)
- **Backend:** `enrichment.retranslate(document, lang, …)` (sets aside listen ext
  fields, re-glosses sentences + vocab via hub `apply_glosses`, re-attaches ext);
  `jobs.py` gains a "translate" job kind (`submit_translate`, worker dispatch, a
  failed translate never touches the entry); `POST /library/<id>/translate`; meta
  tracks `langs` + `glossLang`. Tests: `test_retranslate.py`, translate-job test.
- **Frontend:** studio default → English; reader language switch (EN/DE) queues a
  translate job and reopens the entry when done; `api.translateEntry`; `pendingOpen`
  map reopens both process + translate jobs.
- **Verified end-to-end** (curl + Ollama): process demo → English, then translate the
  same entry → German; glosses switch while lemma/band, all 14 timings and audioRef
  are preserved; `meta.langs = ["de","en"]`.

### Open
- Owner's browser check of the language-switch UI, then cut v0.4.0.

---

## Session 3 — Background job queue + persistent local library (v0.3.0)

### Why
- Owner: audio files can be huge (a film). The synchronous `/process` (browser holds
  the connection 30+ min) is wrong for that. Want a **queue** beside the main panel,
  background jobs with status, and **local persistence** so results replay any time.
- Decisions: **keep the audio** in the library (one-click replay, deletable) and
  process **in parallel** (bounded worker pool).

### Done (plan: `.claude/plans/glittery-exploring-whistle.md`)
- **Backend:** `library.py` (on-disk store, traversal-guarded, hasAudio), `jobs.py`
  (JobManager, bounded pool, chunked upload streaming, per-job progress → library),
  `server.py` endpoints (`POST /jobs`, `GET /jobs`, `GET /library`,
  `GET /library/<id>/result|audio` with **HTTP Range 206**, `DELETE`). Net-free tests
  (`test_library.py`, `test_jobs.py`; parallelism proven via a barrier).
- **Frontend:** two-column layout (reader + queue/library sidebar), `api.ts`,
  `queue.ts` (pure helpers + renderers, `queue.test.ts`), `main.ts` submit→jobs,
  poll, auto-open, `openLibraryItem` via range-served audio. Object-URL guard.
- **Verified** (curl + unit): submit→done→library, ranged 206, delete/remove-audio,
  traversal guard, parallel workers. Gate green (43+ py, 22 viewer tests).

### Open
- Browser visual test (drag-drop, live queue, auto-open, seeking) by the owner, then
  cut v0.3.0. Follow-ups: resume interrupted jobs after restart; per-file "keep audio"
  choice (currently always keep); library search/rename.

---

## Session 2 — razbiram-nlp as an optional enrichment plugin (v0.2.0)

### Why
- Owner: the core value is a **clean transcript + time-accurate alignment**; nlp
  already enriches brilliantly, so the two should combine "like an adapter/plugin".
  On a real 4-min file the enrich stage looked frozen ("als nichts passiert") and the
  hub was a hard dependency even for the transcript-only path.

### Done (4 phases, each gate-green + verified)
1. **Decouple** — `contract.py` (shape-compatible copy, drift-guarded by
   `test_contract_compat.py`), `segment.build_core_document` (hub-free doc from
   Whisper), `enrichment.py` (only hub importer), pipeline `enrich=False` default.
   `razbiram-nlp` → `[enrich]` extra. Verified: with the hub hidden, core emits a
   valid `.listen.json` at 100% coverage; enrich request raises a clear error.
2. **Honest progress** — enrich the cheap stages first, then `apply_glosses` with a
   wrapped provider reporting `(done, total)` via `plan_glosses`. Verified 0/8→8/8
   against Ollama (aya-expanse:8b), correct glosses + A2 band + morphology.
3. **Surface it** — CLI `--enrich` (+ guard + progress + mode line); server `/health`
   `enrichAvailable`, `/process` opt-in; studio default core, translation gated on
   availability, progress bar maps the real fraction (indeterminate → honest %).
   Verified via curl: core `/process` has no enrich stage; enrich streams fractions.
4. **Governance/docs** — BIBLE D7, ADR 005 draft, README (plugin model), CHANGELOG
   0.2.0, CI split into core (hub-free) + enrich (contract guard) jobs, version bump.

### Hub-check record (ECOSYSTEM §3)
- No reimplementation: enrichment uses hub `enrich_text`/`apply_glosses`/`plan_glosses`.
  `contract.py` mirrors `razbiram_nlp/models.py` (mirror, not fork — CI-guarded).

### Next
- Cut v0.2.0 release; file ADR 005 in the hub; then M7 (own example + transcript-edit).

---

## Session 1 — Studio mode (one-step, no CLI)

### Why
- Users found "get audio → run a CLI with hardcoded filenames → load two files"
  far too technical. The browser can't run Whisper/classla/Ollama, so a one-step
  in-browser flow needs a **local companion process** — but the user must see none
  of it.

### Done
- `server.py`: `razbiram-listen studio` starts a stdlib `ThreadingHTTPServer` on
  127.0.0.1 that serves the built viewer and exposes `POST /process` (audio bytes
  in → newline-delimited JSON progress stream → final `.listen.json`) and
  `GET /health` (advertises local Ollama models; auto-picks a multilingual one).
- Pipeline/transcribe gained progress hooks: `Transcriber.transcribe(on_progress=)`
  and `process_audio(on_event=)` emit `transcribe%/enrich/align/done`.
- Viewer: when `/health` responds it enters **studio mode** — a single dropzone,
  a translation-language select, and a live progress bar; drop → `fetch` streams
  progress → auto-renders. Falls back to the manual two-file loader with no server
  (e.g. the vite dev server). Audio plays from the browser's object URL; only the
  bytes go to localhost.
- Verified end-to-end via curl: `/health`, static serve, and a real `gloss=de`
  run streaming to a translated result (100% coverage). 43 Python + 17 viewer
  tests green; server helpers unit-tested.

### Known follow-ups
- Packaging: the server serves `viewer/dist` from the repo layout; a real pip
  install needs the built viewer bundled as package data (or `studio` should build
  it). For difficulty/vocab CEFR, the server env still needs
  `RAZBIRAM_NLP_DATA_DIR`/`RAZBIRAM_NLP_CONFIG_DIR` (graceful-degrades otherwise).
- After a result, "process another file" currently means reload — add a reset.

### Next (M7 — Politur)
- Own recorded example under `examples/sample-audio/` + committed sample; GIF/
  screenshots; README polish; transcript-edit mode; fresh-clone acceptance.

---

## Session 1 — Viewer load-state guidance (UX fix)

### Problem
- A user who loaded only the audio saw the player but nothing else, with **no hint**
  that a `.listen.json` (transcript+translation) is required and that the viewer
  does not transcribe itself. "We were blind."

### Done
- `refreshLoadState()` in the viewer now always reports state: **audio-only** →
  explains the viewer doesn't transcribe and shows the exact copy-pasteable
  `razbiram-listen process --audio "<name>" --gloss de --gloss-model aya-expanse:8b
  --out "<name>.listen.json"` command; **transcript-only** → asks for the audio;
  **both** → starts. Player/reader/seed stay hidden until both are present.
- Verified a real file end-to-end: a user-provided local `.m4a` (3 min, from their
  own ytscapper tool) → `process` → `.listen.json` with 25 sentences, 99% coverage,
  C1, all sentences translated to German. Confirms the combined workflow (their tool
  fetches the local audio, razbiram does transcript+translation+karaoke).

### Open idea (proposed, not built): companion `serve` for live progress
- The real "drop audio → watch it transcribe → read" flow needs a **local**
  companion (`razbiram-listen serve`): the viewer posts the audio to a localhost
  server that runs `process` with a streamed progress bar, then loads the result.
  Local-first (no cloud). A candidate next milestone if we want zero-CLI UX.

---

## Session 1 — Full local glossing wired (classla + Ollama)

### Done (closes the gaps from the previous note)
- CLI: `--gloss-model` (e.g. `aya-expanse:8b`) → `process_audio(gloss_model=…)` →
  `OllamaGlossProvider(model=…)`.
- `pipeline._available_stages()` selects stages by what's installed: morphology only
  if `classla` is importable; a `FileNotFoundError` (missing hub data/config) drops
  difficulty/vocab and retries, so `process` never crashes — sentence glosses always
  survive. `--gloss-model` + stage-selection unit-tested (41 Python tests green).
- `classla` installed + BG model present → **full pipeline verified end-to-end**:
  Whisper small + classla morphology + difficulty/vocab + Ollama gloss, 100%/73%
  coverage, proper lemma/POS/CEFR (времето→време NOUN A2; е→съм AUX A1) and real
  German sentence translations.
- Demo (`examples/_demo/`, git-ignored) regenerated with morphology → proper
  lemmas/POS/CEFR + real translations.
- Docs: README "Glosses & CEFR — fully local" + `.env.example`
  (`RAZBIRAM_NLP_DATA_DIR`/`RAZBIRAM_NLP_CONFIG_DIR`).

### Hub follow-up (ADR/issue candidate)
- The hub wheel doesn't ship `data/`+`config/`, so difficulty/vocab need env vars
  pointing at a checkout. Cleanest fix is on the hub side (package the data). Filed
  as a note for the hub.

### Next (M7 — Politur)
- Own recorded example under `examples/sample-audio/` + committed
  `sample.listen.json` + `SOURCES.md`; GIF/screenshots; README polish; transcript-
  edit mode; fresh-clone acceptance.

---

## Session 1 — Local translation verified; viewer gloss-lookup fix

### Verified
- **Fully local translation works** via Ollama (`aya-expanse:8b`, multilingual):
  `enrich_text(text, gloss_lang="de", stages={segmentation,difficulty,vocab,gloss})`
  → correct German sentence glosses + per-word glosses + CEFR bands in ~10s, **no
  classla**. classla (morphology) would sharpen lemma/band; without it they're
  frequency-based approximations. Local demo (`examples/_demo/`) regenerated with
  real Ollama translations (git-ignored).
- Viewer: gloss lookup now keys case-insensitively and falls back to the surface
  form, so word glosses show whether or not morphology ran. Build + 17 tests green.

### Integration gaps found (for `razbiram-listen process --gloss de` out-of-box)
1. **Default gloss model is `llama3.1`** (razbiram-nlp `OllamaGlossProvider`); users
   may have other models. → add a CLI `--gloss-model` (and/or `--gloss-provider`).
2. **difficulty/vocab need the hub's `data/` + `config/`**, which the installed
   wheel does not ship → they fail unless `RAZBIRAM_NLP_DATA_DIR` /
   `RAZBIRAM_NLP_CONFIG_DIR` point at a hub checkout. → document, or ask the hub to
   package the data (hub issue), or degrade gracefully (skip difficulty/vocab).
3. **morphology needs the `classla` extra** (heavy) — optional; segmentation-only
   still yields sentence + word glosses.

### Next
- Small: wire `--gloss-model` into the CLI + document the data/config env vars.
- Then M7 polish.

---

## Session 1 — Open-URL import (the §8-scoped feature)

### Done
- `sources.py`: `fetch_audio(url, dest_dir, *, fetch=…, episode=…)` imports **one**
  open source — a direct audio URL or a podcast **RSS enclosure**. Guardrails:
  `guard_url` blocks non-http schemes and a **denylist of streaming/DRM hosts**
  (YouTube/Spotify/SoundCloud/…); the final URL is re-checked **after redirects**;
  platform/HTML pages are refused (never resolved to media). The HTTP GET is one
  injectable seam (`_default_fetch`, size/time-capped), so all decision logic is
  net-free tested.
- CLI: `process` gains `--url` + `--episode`; `--audio`/`--url` are mutually
  exclusive. Fetched audio lands next to `--out` (stays local for the viewer).
- Tests: `test_sources.py` (10) — platform blocks, scheme blocks, classification,
  enclosure pick/index, direct-audio fetch, RSS→enclosure fetch, HTML refusal,
  redirect-to-blocked refusal. **40 Python tests green**, ruff + format clean.
  Real fetch verified over a local `http.server` (downloaded the demo mp3).

### Hub-check (ECOSYSTEM §3)
- Stdlib only (urllib + ElementTree) — no new deps, nothing in the hub to reuse.

### Next (M7 — Politur)
- Own recorded example under `examples/sample-audio/` + committed
  `sample.listen.json` + `SOURCES.md`; GIF/screenshots; README polish; transcript-
  edit mode; fresh-clone acceptance.

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

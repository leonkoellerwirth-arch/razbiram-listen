# Changelog

All notable changes to razbiram-listen. Format: [Keep a Changelog](https://keepachangelog.com/),
SemVer. The `.listen.json` document shape is versioned separately via
`schemaVersion` (see `SCHEMA_VERSION` in `models.py`).

## [Unreleased]

### Added
- **Reader redesign for long content (three-zone shell).** The studio is now a
  fixed `topbar / content / player` shell that never scrolls away: a left **spine**
  (transcript search · time-based jump marks · a position rail), a centre **reading
  spotlight** (the active sentence is full-opacity and larger, neighbours dim by
  distance, auto-centred), a **persistent player bar** (play · time · scrubber ·
  loop · tempo), **one** unified language control (EN/DE/off) replacing the two old
  pickers, and the queue/library moved into a **slide-over drawer** so the reader
  gets full width. Thousands of sentences stay smooth via `content-visibility`.
  Keeps the razbiram.com theme verbatim (tokens, fonts, the existing `--band-*`
  CEFR badge colours). Design direction by a Fable-5 pass, owner-approved.
- **Cancel a running or queued job** — active jobs in the queue get a ✕;
  `DELETE /jobs/<id>` cancels cooperatively (a running job aborts at its next
  progress step, the aborted upload is discarded). Net-free tested.

## [0.4.0] — 2026-07-11

Translation becomes a switchable layer, not a one-shot choice at drop time.

### Added
- **Translate a saved entry later, to German or English, without re-transcribing.**
  The reader has a language switch (EN/DE); changing it queues a lightweight
  re-gloss job that reuses the stored transcript. Because morphology/CEFR/lemma are
  language-independent, only the sentence + word **glosses** are recomputed — tokens,
  timings, `audioRef` and `schemaVersion` are preserved, so the karaoke alignment
  stays valid and no Whisper pass runs again. The entry remembers which languages it
  has (`meta.langs`); switching back is cache-fast.
- Endpoint `POST /library/<id>/translate?lang=en|de&model=…` (a queued "translate"
  job; 409 without the plugin, 404 for a missing entry). `enrichment.retranslate()`
  + net-free tests (field preservation with a fake provider; job dispatch).

### Changed
- **The studio default is now English** (was "nur Transkript"): a plain drop
  transcribes and translates to English (full analysis + CEFR). "nur Transkript" and
  "Deutsch" remain in the dropdown.

## [0.3.0] — 2026-07-11

Large audio (a film) no longer means a fragile 30-minute open connection: the studio
runs **background jobs** with a **queue panel** and a **persistent local library** you
can replay any time.

### Added
- **Background job queue.** The studio submits each drop as a job (`POST /jobs`) run by
  a bounded worker pool (default 2, `RAZBIRAM_LISTEN_WORKERS`); a right-hand panel shows
  live per-job progress. Drop several files → they process **in parallel**; a short one
  auto-opens when done, a long one keeps running in the background.
- **Persistent local library.** Every result is saved under `$RAZBIRAM_LISTEN_HOME`
  (default `~/.razbiram-listen`) — the transcript **and** the audio — and is replayable
  with one click, no re-dropping. Delete an entry or just its audio to reclaim space
  (the transcript stays). Local-first: no upload, no cloud (BIBLE D8).
- Audio is **range-served** (`GET /library/<id>/audio`, HTTP 206) so seeking works in
  large files. New endpoints: `POST /jobs`, `GET /jobs`, `GET /library`,
  `GET /library/<id>/result|audio`, `DELETE /library/<id>[/audio]`. Ids are
  path-traversal-guarded; uploads stream to disk in chunks (never a multi-GB body in
  memory). `library.py` + `jobs.py` are net-free unit-tested (parallelism proven).

### Changed
- The studio viewer is now a **two-column layout** (reader + queue/library sidebar),
  collapsing to one column on narrow screens. It submits to `/jobs` instead of the
  legacy streaming `/process` (which still works).

## [0.2.0] — 2026-07-11

razbiram-nlp becomes an **optional enrichment plugin**: the core (transcript +
timing + karaoke) runs with nothing else installed, and glosses/CEFR light up when
the plugin is present — "the two tools help each other."

### Changed
- **razbiram-nlp is now the optional `[enrich]` extra**, not a required dependency.
  `pip install razbiram-listen` gives the full synced-transcript karaoke with no
  hub; `pip install "razbiram-listen[enrich]"` adds glosses/CEFR/morphology.
- **Enrichment is opt-in everywhere.** CLI gains `--enrich/--no-enrich` (off by
  default; `--gloss` implies it) with a clear message when the plugin is missing.
  The studio defaults to "nur Transkript (schnell)"; Deutsch/English are offered
  only when the plugin + a local LLM are available (`/health` reports it).

### Added
- **Honest "sentence X of N" progress** during glossing. Enrichment runs the cheap
  stages first, then applies glosses via the hub's `apply_glosses` with a wrapped
  provider reporting `(done, total)` per uncached LLM call (`plan_glosses`). The
  studio bar maps the real fraction (indeterminate while analysing, then honest %),
  replacing the fixed 75% that looked frozen.
- **`razbiram_listen.contract`** — a shape-compatible, drift-guarded copy of the
  `EnrichedDocument` contract so the core builds documents without the hub;
  `test_contract_compat.py` round-trips a hub document through it when the plugin is
  installed. **`segment.build_core_document`** builds a document straight from
  Whisper. **`razbiram_listen.enrichment`** is the only module importing the hub.

### Governance
- Recorded as **BIBLE D7** and hub **ADR 005** (draft:
  `docs/hub-adr-005-nlp-optional-plugin.md`). This is a mirror of the family
  contract, not a fork — guarded by CI until the hub publishes a JSON Schema.

## [0.1.0] — 2026-07-11

First tagged release: the end-to-end studio works — drop a local Bulgarian audio
file in the browser and read it, word by word, synced to the audio. Local-first
and BYO-audio. razbiram-nlp enrichment (glosses/CEFR) is used when available; the
core (transcript + time-accurate alignment + karaoke) stands on its own.

### Added
- **M1 — Models + scaffold.** `ListenDocument` (an `EnrichedDocument` extended
  with `timings` and `audioRef`), `schemaVersion` 1.0.0, package scaffold,
  contract tests, net-free CI (ruff + pytest), project docs.
- **M2 — Transcribe.** `Transcriber`, a faster-whisper wrapper with word-level
  timestamps, an injectable model seam (mocked in unit tests), a rich progress
  bar, and one real `slow` test. faster-whisper is imported lazily so imports and
  the net-free suite stay cheap.
- **M3 — Align (core).** `align()` maps Whisper word timings onto razbiram tokens
  via an order-preserving, normalised (case/punctuation-tolerant) two-pointer
  match with look-ahead resync; unmatched tokens fall back to their sentence
  window, and gap sentences are interpolated. Exposes an `AlignmentStats.coverage`
  quality metric, guarded by a 7-case **Golden-Set**.
- **M4 — Pipeline + CLI.** `process_audio()` orchestrates transcribe → hub
  `enrich_text` → align → `ListenDocument`, with injectable transcribe/enrich
  seams for net-free tests. `razbiram-listen process --audio … --gloss … --out …`
  writes the `.listen.json` and reports alignment coverage. Verified end to end
  (real Whisper tiny + real hub segmentation) in a `slow` test.
- **M5 — Viewer MVP.** A Vite + vanilla-TypeScript `viewer/` (no upload, no
  server): loads a `.listen.json` + local audio, karaoke sync (active-word
  highlight, click-to-seek, auto-scroll), hover popover (lemma · POS · gloss ·
  CEFR badge on the family colour scale), tempo (0.5×–1.5×), A–B sentence loop,
  dark mode. Pure sync/CEFR/loader logic is unit-tested; the viewer build + tests
  are a CI job. Studio-style reading rows (per-sentence Listen, Show-translation,
  CEFR header) and drag-and-drop loading followed.
- **M6 — Seed-Export.** The word popover gains a ＋ to collect vocabulary into a
  deduplicated basket; a sticky seed bar exports it two ways — a **razbiram Seed
  JSON** and a **CrowdAnki `deck.json`** (razbiram-anki-compatible, front = lemma
  / back = gloss). Roundtrip-tested against razbiram-anki's own deck shape check.

- **Studio mode — one-step, no CLI.** `razbiram-listen studio` starts a local
  server (127.0.0.1 only) that serves the viewer and does the work: drag an audio
  file into the browser and it is transcribed + translated with a **live progress
  bar**, then shown — no `.listen.json` to juggle, no flags to type. The audio
  plays from the browser's own object URL; only its bytes go to localhost. The
  server auto-detects a local Ollama gloss model. `process` remains for scripting.
- **Viewer load guidance.** The viewer now always says what's missing: loading
  only audio explains that it does not transcribe itself and shows the exact
  `razbiram-listen process …` command to generate the `.listen.json`; loading only
  the transcript asks for the audio. No more silent "player but nothing happens".
- **Local glossing wired up.** `process --gloss de --gloss-model aya-expanse:8b`
  runs fully local (Ollama); stages degrade gracefully to what the install has —
  morphology needs the optional `classla` extra, difficulty/vocab need the hub's
  `data/`+`config/` (`RAZBIRAM_NLP_DATA_DIR`/`RAZBIRAM_NLP_CONFIG_DIR`), and without
  either you still get sentence translations. Verified end-to-end (Whisper +
  classla + Ollama).
- **Open-URL import.** `process --url <direct-audio | podcast-RSS>` (with
  `--episode N`) fetches one open source the user has rights to and transcribes it
  locally; `--audio`/`--url` are mutually exclusive. A host **denylist actively
  refuses streaming/DRM platforms** (YouTube, Spotify, SoundCloud, …), re-checked
  after redirects, and platform/HTML pages are never resolved to media. Decision
  logic is net-free unit-tested; the real fetch is a single injectable seam.

### Policy
- **Briefing §8 scoped (author-authorised amendment):** importing a user-supplied
  **direct audio-file URL / podcast RSS enclosure** is allowed; **streaming/DRM
  platform scraping (Spotify, YouTube, …) stays forbidden.** Recorded in the
  briefing §8 addendum, `CLAUDE.md`, and BIBLE D6.

### Contract
- `.listen.json` **schemaVersion 1.0.0** — superset of the razbiram-nlp
  `EnrichedDocument` read against `razbiram-nlp@v0.1.0`.

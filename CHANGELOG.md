# Changelog

All notable changes to razbiram-listen. Format: [Keep a Changelog](https://keepachangelog.com/),
SemVer. The `.listen.json` document shape is versioned separately via
`schemaVersion` (see `SCHEMA_VERSION` in `models.py`).

## [Unreleased]

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

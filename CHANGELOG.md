# Changelog

All notable changes to razbiram-listen. Format: [Keep a Changelog](https://keepachangelog.com/),
SemVer. The `.listen.json` document shape is versioned separately via
`schemaVersion` (see `SCHEMA_VERSION` in `models.py`).

## [Unreleased]

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
  are a CI job.

### Contract
- `.listen.json` **schemaVersion 1.0.0** — superset of the razbiram-nlp
  `EnrichedDocument` read against `razbiram-nlp@v0.1.0`.

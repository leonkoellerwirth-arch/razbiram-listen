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

### Contract
- `.listen.json` **schemaVersion 1.0.0** — superset of the razbiram-nlp
  `EnrichedDocument` read against `razbiram-nlp@v0.1.0`.

# BIBLE.md — razbiram-listen

Stable decisions and principles for this repo. Public — no business internals.
Binding foundation: [`../razbiram-nlp/docs/razbiram-ECOSYSTEM.md`](../razbiram-nlp/docs/razbiram-ECOSYSTEM.md)
(see `CLAUDE.md`).

## Identity
razbiram-listen is the **audio entry gate** of the razbiram ecosystem: Whisper
transcription → alignment → a synced Karaoke viewer. It consumes and produces the
shared `EnrichedDocument` contract, extended with audio timings.

## Principles (stable)
1. **BYO-audio only.** The tool processes audio the user already has. No download,
   no catalogue, no scraping, no lyrics/subtitle endpoints — ever (Briefing §8).
2. **Consume the contract, never fork it.** `EnrichedDocument` is imported from
   the razbiram-nlp hub. `ListenDocument` extends it only through the reserved
   optional fields `timings` and `audioRef`, plus mandatory `schemaVersion`.
3. **Alignment is the quality heart.** It gets a Golden-Set regression suite
   (M3). Nothing built on top advances until the Golden cases are green.
4. **Local-first & private.** No server upload, no telemetry, no cloud requirement.
5. **Small and excellent.** Type hints, docstrings, ruff + pytest green,
   Conventional Commits, CI net-free.

## Decisions (chronological)
- **D1 — Licence: MIT.** Per ECOSYSTEM Zonen-Tabelle and Briefing §3 (tools are
  true open source). The GitHub repo was initialised with GPL-3 by default; that
  was replaced with MIT.
- **D2 — nlp dependency pinned to a tag.** `razbiram-nlp @ git+…@v0.1.0`. The hub
  had no tags; `v0.1.0` was created and pushed on the hub so consumers can pin a
  reproducible version (ECOSYSTEM §3).
- **D3 — Timings join by stable key, not by duplicating the token tree.**
  `TokenTiming.token_start` == `Token.start` (char offset); `SegmentTiming` keys
  on `sentence_index`. Keeps the contract un-forked and the viewer join trivial.
- **D4 — `schemaVersion` starts at `1.0.0`** for the `.listen.json` shape;
  `ENRICHED_CONTRACT_SOURCE` records the hub release we read against
  (`razbiram-nlp@v0.1.0`) until the hub stamps its own version (see HANDOFF).
- **D5 — No YouTube/streaming scraping.** A "paste a YouTube link → fetch &
  process" feature was refused: violates §8.1/§8.3, platform ToS, copyright.
  *(Scope refined by D6; the YouTube/streaming refusal stands.)*
- **D6 — §8 scoped: open direct-URL import allowed, platform scraping forbidden.**
  Author-authorised amendment (2026-07-10). Importing a **user-supplied direct
  audio-file URL or podcast RSS enclosure** the user has rights to **is allowed**
  (the tool fetches only that one named open file, like a podcast app). **Still
  forbidden:** Spotify/YouTube/Musixmatch and any streaming/DRM platform,
  caption/transcript endpoints, DRM circumvention, resolving platform pages to
  media, catalogue integration, "how to rip X" guides. *Open direct file: yes.
  Platform: no.* The URL-import is an approved feature (built after M6). Because §8
  is family-wide (ECOSYSTEM §7), this scoping is a hub-ADR candidate. See the §8
  amendment in `CLAUDE-CODE-BRIEFING-razbiram-listen.md`.

## Open ADR candidates (raise in the hub, ECOSYSTEM §6)
- Hub should ship `schemas/enriched-document.vN.json` and a `schemaVersion` field
  on `EnrichedDocument` (currently neither exists).
- `viewer-core` extraction (Studio ↔ Karaoke) only when Rule of Three triggers.

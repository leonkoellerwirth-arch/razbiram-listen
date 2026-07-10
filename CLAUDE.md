# CLAUDE.md — razbiram-listen

> **Read this before doing any work in this repo.** It is the local anchor; the
> binding foundation is the ecosystem standard below, which takes precedence
> wherever this file or any single briefing disagrees with it.

## Binding foundation (read first, every session)

The ecosystem standard is **mandatory** and wins on any conflict:

- **Primary (local):** [`../razbiram-nlp/docs/razbiram-ECOSYSTEM.md`](../razbiram-nlp/docs/razbiram-ECOSYSTEM.md)
  *(the briefing calls this `ECOSYSTEM.md`; the file on disk is `razbiram-ECOSYSTEM.md`).*
- **Remote fallback:** <https://raw.githubusercontent.com/leonkoellerwirth-arch/razbiram-nlp/main/docs/ECOSYSTEM.md>

Also binding for this repo specifically: `CLAUDE-CODE-BRIEFING-razbiram-listen.md`
(in this folder). Its **Section 8 (legal guardrails) is non-negotiable and wins
over any feature wish.**

razbiram-nlp is the **hub / source of truth**. This repo is the audio entry gate:
Whisper → timings → Karaoke viewer. It consumes and produces the shared
`EnrichedDocument` contract (extended with timings).

## Non-Negotiables

### 1. Never reimplement what razbiram-nlp already provides
- razbiram-nlp is imported as a **pip dependency**, never copied
  (`from razbiram_nlp import enrich_text, EnrichedDocument`). See ECOSYSTEM §3.
- **Before writing any new module,** explicitly check whether the function
  already exists in the hub (grep / module list) and **record the result in
  `HANDOFF.md`**. Rule of Three before extracting anything shared.

### 2. Consume the EnrichedDocument schema from the hub; declare `schemaVersion`
- The contract lives in `razbiram-nlp` (Pydantic models in
  `src/razbiram_nlp/models.py`, plus the generated JSON Schema the hub publishes
  under `schemas/enriched-document.vN.json`). Import it; do not fork it.
- `ListenDocument` **extends** `EnrichedDocument` only through defined optional
  fields (`timings`, `audioRef`) — never a parallel format. Extension proposals
  go to the hub as a mini-ADR (ECOSYSTEM §6).
- Every emitted `.listen.json` **declares `schemaVersion`**.
- *Hub gap to track (see `HANDOFF.md`):* the hub currently ships neither a
  `schemas/` JSON Schema nor a `schemaVersion` field on `EnrichedDocument`.
  Until it does, we pin the nlp dependency by version and record the contract
  version we read against.

### 3. Corporate Identity — exactly per ECOSYSTEM §4
- **CEFR colour scale (identical everywhere):** A1 `#22c55e` · A2 `#84cc16` ·
  B1 `#eab308` · B2 `#f97316` · C1 `#ef4444` · C2 `#b91c1c`.
- README skeleton, design tokens, hover-popover / badge shapes, dark mode
  (mandatory), and the author line — **exactly** as specified in ECOSYSTEM §4.
- Author line: *Built by [Leon Köllerwirth Hlihel](https://leon-koellerwirth.com)
  — AI governance & agentic engineering in regulated environments.*
- README/code in English; teacher docs additionally German (`*.de.md`);
  learning examples in Bulgarian (verified correct).

### 4. House methodology (ECOSYSTEM §5)
- **Evaluator principle:** Alignment is this repo's core heuristic → it gets a
  **Golden-Set** regression test (5–8 own audio snippets, hand-verified token
  mapping). The README names it as a methodology feature.
- Keep `BIBLE.md` (stable decisions) + `HANDOFF.md` (session hand-offs) current;
  both are public — no business internals, read before every commit.
- **Conventional Commits** (`feat:`, `fix:`, `docs:`, `test:`).
- **ruff + pytest green**; CI is net-free (real Whisper/LLM only as `slow`
  local tests). Viewer build-check in CI. Type hints + docstrings, no dead code,
  "small and excellent".

### 5. Legal guardrails — Briefing §8, ABSOLUTE
- **No scraping, no unofficial endpoints.** No code that fetches/parses lyrics,
  subtitles, or transcripts from Spotify, YouTube, Musixmatch, etc. — not in
  examples, comments, roadmap code, or tests.
- **No third-party content in the repo.** No song lyrics, no commercial podcast
  clips, no foreign translations.
- **BYO-audio only.** The tool processes what the user provides locally: no
  download feature, no catalogue integration, no "how to get the audio" guides.
- **Example assets are own-recording or explicitly CC-licensed only**, with
  `examples/SOURCES.md` (source, licence, link) — mandatory.
- **Local-first & private:** no server upload, no telemetry, no cloud
  requirement. LLM glosses via local Ollama (Anthropic provider optional and
  clearly labelled). Spotify, if ever, is roadmap-only, official Web API,
  metadata only — never text content.

## Milestones (build in order — Briefing §6)
M1 models+scaffold+CI · M2 transcribe (faster-whisper, mocked tests + 1 slow) ·
M3 align (core + Golden-Set; don't advance until green) · M4 pipeline+CLI ·
M5 viewer MVP · M6 seed-export (both formats, roundtrip to razbiram-anki) ·
M7 polish (own example audio, GIF, README, transcript-edit mode, fresh-clone
acceptance). **MVP scope-freeze:** local files, Bulgarian, glosses de/en.

## Licence
**MIT** (per ECOSYSTEM Zonen-Tabelle and Briefing §3) — like razbiram-anki.

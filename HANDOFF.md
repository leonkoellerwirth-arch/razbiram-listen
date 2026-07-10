# HANDOFF.md — razbiram-listen

Session-to-session hand-offs. Public — no business internals. Newest first.

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

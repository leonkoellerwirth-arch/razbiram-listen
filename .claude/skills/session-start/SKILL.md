---
description: Open a work session on razbiram-listen — reconstruct the exact project state from the deterministic scripts and repo memory (BIBLE.md, HANDOFF.md) before changing anything, so work continues without drift. Counterpart to session-end. Trigger: "session-start", "continue", "where were we", "new session", "catch me up", "weiter", start of a work session.
allowed-tools: Bash, Read, Grep, Glob
---

Reconstruct the exact state **before** writing or changing anything. Goal: **no drift from the project or the razbiram family standard.**

**Step 0 — Family constitution (precedence).**
Read `../razbiram-nlp/docs/razbiram-ECOSYSTEM.md` (remote fallback:
`https://raw.githubusercontent.com/leonkoellerwirth-arch/razbiram-nlp/main/docs/ECOSYSTEM.md`)
— it outranks any single briefing and this repo's docs where they diverge. Then
`CLAUDE.md` (this repo's operating rules + the non-negotiable legal guardrails §5).

**Step 1 — Deterministic truth (scripts, no AI):**
- `./scripts/state.sh` — branch, HEAD, uncommitted/unpushed, Python & viewer LoC, pytest/vitest counts.
- `./scripts/gate.sh` — the hard quality gate (must be PASS to build on).
- `./scripts/secure.sh` — is everything committed & pushed?

**Step 2 — Repo memory (in this order):**
- `HANDOFF.md` — read the **“▶ Resume here” block + the top (newest) entry** in full: Done / Decided / Open-blocked / Next / Continuity warnings.
- `BIBLE.md` — the principles and the **Decisions register** (D1…): every open item, especially **D6 (§8 scope)**.
- If the next task is unclear, skim the newest persistent memory note.

**Step 3 — Brief the user (short, concrete):**
1. **Where we are** — numbers from `state.sh` + gate/secure status (green/red).
2. **Last done** — from the newest HANDOFF entry / “Resume here”.
3. **Blocking decisions** — any open decision that blocks the next task; clear it with the owner first.
4. **Next** — the concrete next step (HANDOFF “Next”; currently **M7 — Politur**).
5. **Continuity warnings** (invariants that must not break):
   - **§8 / BIBLE D6 — no platform scraping.** BYO-audio; `process --url` accepts open direct-file/podcast-RSS only; never build YouTube/Spotify ingestion, not even a glue script. Transcribing a *local* file is always fine (Whisper is the core).
   - **Consume the hub contract, don't fork it** — `EnrichedDocument` from razbiram-nlp; declare `schemaVersion`; check the hub before writing a new module.
   - **Local-first** — no upload/telemetry; glosses via local Ollama (`aya-expanse:8b`).
   - **CEFR scale & design tokens** identical to the family; dark mode mandatory.
   - **Alignment Golden-Set must stay green** (M3) before building on it.
   - **One-step, non-technical UX** is the direction (`razbiram-listen studio`); never leave the user “blind”.
   - **The owner decides scope — execute, don't over-ask.**

**Rule:** Don't start substantive work while a blocking decision is open. If `gate.sh` fails or `secure.sh` reports unsaved/unpushed work, fix that first. End the session with **session-end**.

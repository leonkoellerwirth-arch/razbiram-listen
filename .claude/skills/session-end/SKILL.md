---
description: Close a work session on razbiram-listen — save the repo memory, pass the hard gate, and commit & push everything so nothing is forgotten and nothing is left half-done. Counterpart to session-start. Trigger: "session-end", "session-stop", "wrap up", "end session", "done for today", "close the session", "sauber abschließen", end of a work session.
allowed-tools: Bash, Read, Write, Edit, Grep, Glob
---

Close the session so the next one (via session-start) continues **without drift, without loss, and without a half-finished hand-off**. Do not skip a step; actually run each one.

**Step 1 — Inventory.**
- `git status --short` — what is open? Nothing should be left unintentionally.
- **Stop background processes you started** (`razbiram-listen studio`, the vite dev server). Leave the owner's own processes running.
- If product source changed and something is now unverified, drive it (or state explicitly what is still unverified).

**Step 2 — Update canon & continuity.**
- `BIBLE.md` — record decisions made this session; add/tick Decisions-register (D…) items. Decisions live in the file, not just the chat.
- `CHANGELOG.md` — note user-facing changes.
- **★ Rescue chat threads (mandatory, or they are lost):** any idea, owner input, or half-formed plan that exists only in this conversation and in **no file** yet goes into the HANDOFF entry (Open/Next). Preserve, don't invent.
- **Persistent memory:** if a durable, non-repo fact emerged (a setup detail, a lasting preference, a boundary decision), write/update it under the memory dir and add a one-line pointer in `MEMORY.md`.

**Step 3 — Hard gate.**
- `./scripts/gate.sh` — **must print GATE: PASS** (ruff + pytest + viewer build + vitest). Fix any failure first.

**Step 4 — Write the repo memory.**
- `./scripts/session-snapshot.sh` and prepend its block to the **top** of `HANDOFF.md` (newest first); keep the **“▶ Resume here”** block current (state + next).
- Fill the `_(fill in)_` lines with what really happened: **Done · Decided · Open/blocked · Next · Continuity warnings**. Concrete and honest — `state.sh` is the truth.

**Step 5 — Secure (git).**
- Commit granularly (Conventional Commits: feat/fix/docs/chore/test…) with the family commit trailers. Document what and why.
- `git push origin main`.
- `./scripts/secure.sh` — **must report "all saved".**

**Step 6 — Hand off.**
Short closing note: state (numbers), what was saved, what is next (M7), which decisions block the next session, and any background process you stopped.

**Rule:** the session is done only when `gate.sh` is PASS, `secure.sh` says "all saved", and the newest `HANDOFF.md` / “▶ Resume here” reflects reality. Invent nothing, hide nothing, leave nothing uncommitted.

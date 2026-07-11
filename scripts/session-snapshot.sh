#!/usr/bin/env bash
#
# Emit a HANDOFF.md entry template. Fill the _(fill in)_ lines with what really
# happened, then prepend the block to the TOP of HANDOFF.md (newest first) and
# keep the "▶ Resume here" block current.
#
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."

branch="$(git rev-parse --abbrev-ref HEAD 2>/dev/null || echo main)"
today="$(date +%Y-%m-%d)"

cat <<EOF
## ${today} — branch ${branch}

**Done:**
- _(fill in — concrete, live-verified)_

**Decided (see BIBLE decisions register):** _(fill in — decisions go in the file, not just chat)_

**Open / blocked:**
- _(fill in — including any chat-only idea not yet in a file)_

**Next:** _(fill in — the concrete next step)_

**Continuity warnings:** _(fill in — invariants that must not break: §8/D6 no scraping · hub contract · local-first)_

---
EOF

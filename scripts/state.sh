#!/usr/bin/env bash
#
# Deterministic project state — no AI, just facts. Read at session-start.
#
set -uo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."

echo "=== razbiram-listen state ==="
echo "branch:       $(git rev-parse --abbrev-ref HEAD 2>/dev/null || echo '?')"
echo "HEAD:         $(git rev-parse --short HEAD 2>/dev/null || echo '?')  $(git log -1 --pretty=%s 2>/dev/null || true)"
echo "uncommitted:  $(git status --porcelain 2>/dev/null | wc -l | tr -d ' ') file(s)"
if git rev-parse --abbrev-ref '@{u}' >/dev/null 2>&1; then
  echo "unpushed:     $(git rev-list --count '@{u}'..HEAD 2>/dev/null || echo '?') commit(s)"
else
  echo "unpushed:     (no upstream tracked)"
fi

py_loc="$(find src -type f -name '*.py' 2>/dev/null | xargs wc -l 2>/dev/null | tail -1 | awk '{print $1}')"
echo "python LoC:   ${py_loc:-0}  (src/razbiram_listen)"
if [ -x .venv/bin/python ]; then
  pp="$(.venv/bin/python -m pytest -q 2>&1 | grep -oE '[0-9]+ passed' | grep -oE '[0-9]+' | head -1 || true)"
  echo "pytest:       ${pp:-?} passed (net-free; slow tests excluded)"
else
  echo "pytest:       (.venv missing — python3.11 -m venv .venv && .venv/bin/pip install -e '.[dev]')"
fi

vw_loc="$(find viewer/src -type f -name '*.ts' ! -name '*.test.ts' 2>/dev/null | xargs wc -l 2>/dev/null | tail -1 | awk '{print $1}')"
echo "viewer LoC:   ${vw_loc:-0}  (viewer/src)"
if [ -d viewer/node_modules ]; then
  vp="$( (cd viewer && npx vitest run 2>&1) | grep -oE 'Tests[[:space:]]+[0-9]+ passed' | grep -oE '[0-9]+' | head -1 || true)"
  echo "vitest:       ${vp:-?} passed"
else
  echo "vitest:       (viewer/node_modules missing — cd viewer && npm ci)"
fi

echo "milestones:   M1–M6 + open-URL import + studio mode done · next: M7 (polish)"

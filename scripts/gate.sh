#!/usr/bin/env bash
#
# The hard quality gate. Must print "GATE: PASS" before building on a state.
#   ./scripts/gate.sh   → ruff (check+format) + pytest (net-free) + viewer build + vitest
#
set -uo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."
fail=0

if [ -x .venv/bin/ruff ]; then
  echo "→ ruff check + format --check"
  if ! ( .venv/bin/ruff check . && .venv/bin/ruff format --check . ) >/tmp/rzl_gate_ruff.log 2>&1; then
    echo "  RUFF FAILED:"; tail -25 /tmp/rzl_gate_ruff.log; fail=1
  fi
  echo "→ pytest (net-free)"
  if ! .venv/bin/python -m pytest -q >/tmp/rzl_gate_pytest.log 2>&1; then
    echo "  PYTEST FAILED:"; tail -25 /tmp/rzl_gate_pytest.log; fail=1
  fi
else
  echo "  .venv missing — python3.11 -m venv .venv && .venv/bin/pip install -e '.[dev]'" >&2
  fail=1
fi

if [ -d viewer/node_modules ]; then
  echo "→ viewer build (tsc + vite build)"
  if ! ( cd viewer && npm run build ) >/tmp/rzl_gate_vbuild.log 2>&1; then
    echo "  VIEWER BUILD FAILED:"; tail -25 /tmp/rzl_gate_vbuild.log; fail=1
  fi
  echo "→ viewer tests (vitest)"
  if ! ( cd viewer && npm test ) >/tmp/rzl_gate_vtest.log 2>&1; then
    echo "  VIEWER TESTS FAILED:"; tail -25 /tmp/rzl_gate_vtest.log; fail=1
  fi
else
  echo "  viewer/node_modules missing — cd viewer && npm ci" >&2
  fail=1
fi

if [ "$fail" = 0 ]; then echo "GATE: PASS"; else echo "GATE: FAIL"; exit 1; fi

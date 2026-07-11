#!/usr/bin/env bash
#
# Is everything committed and pushed? Prints "all saved" or what is still open.
#
set -uo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."

dirty="$(git status --porcelain 2>/dev/null | wc -l | tr -d ' ')"
ahead=0
if git rev-parse --abbrev-ref '@{u}' >/dev/null 2>&1; then
  ahead="$(git rev-list --count '@{u}'..HEAD 2>/dev/null || echo 0)"
fi

if [ "$dirty" = 0 ] && [ "$ahead" = 0 ]; then
  echo "all saved"
else
  echo "NOT saved: $dirty uncommitted file(s), $ahead unpushed commit(s)"
  [ "$dirty" != 0 ] && git status --short
  exit 1
fi

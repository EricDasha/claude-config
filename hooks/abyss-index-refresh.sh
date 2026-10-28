#!/usr/bin/env bash
# abyss PostToolUse bridge for Claude Code on Windows.
#
# Refreshes the index after every Edit/Write so the next PreToolUse card reflects
# the file's CURRENT state. `abyss hook pre-edit` is read-only by design, so
# without this the architecture/hotspot data goes stale the moment you edit.
#
# Runs synchronously: Claude Code kills the hook's whole process group when the
# hook returns, so a backgrounded refresh never completes.
#
# Opt-in gate: the session-init hook drops `.code-abyss/.hook-enabled` only
# after confirming the repo ignores `.code-abyss/`.

set -uo pipefail

ABYSS="$(command -v abyss 2>/dev/null || true)"
for cand in "${HOME}/.code-abyss/bin/abyss.exe" "${HOME}/.code-abyss/bin/abyss" "${APPDATA:-}/npm/node_modules/@code-abyss/cli/bin/abyss-bin.exe"; do
  [ -x "$cand" ] && { ABYSS="$cand"; break; }
done
[ -z "$ABYSS" ] && exit 0

[ -f .code-abyss/.hook-enabled ] || exit 0

IFS= read -r -d '' PAYLOAD || true
[ -z "$PAYLOAD" ] && exit 0

RAW="${PAYLOAD#*\"file_path\":\"}"; RAW="${RAW%%\"*}"
CWD="${PAYLOAD#*\"cwd\":\"}";        CWD="${CWD%%\"*}"
[ -z "$RAW" ] || [ "$RAW" = "$PAYLOAD" ] && exit 0

REL="${RAW//\\\\\\\\//}"
REL="${REL//\\\\//}"
ROOT="${CWD//\\\\\\\\//}"
ROOT="${ROOT//\\\\//}"
ROOT="${ROOT%/}"

if [ -n "$ROOT" ]; then
  case "${REL,,}" in
    "${ROOT,,}/"*) REL="${REL:${#ROOT}+1}" ;;
  esac
fi

case "$REL" in
  [A-Za-z]:/*|/*) exit 0 ;;
  "") exit 0 ;;
esac

printf '{"tool_name":"Edit","tool_input":{"file_path":"%s"}}' "$REL" \
  | "$ABYSS" hook post-edit >/dev/null 2>&1

exit 0

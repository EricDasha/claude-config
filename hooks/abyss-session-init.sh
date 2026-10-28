#!/usr/bin/env bash
# abyss SessionStart bridge for Claude Code on Windows.
#
# Builds or refreshes the code index when a session starts, so the first
# PreToolUse card already has architecture/hotspot data. Also owns the opt-in
# decision: it writes `.code-abyss/.hook-enabled` only after confirming the repo
# ignores `.code-abyss/`. The per-edit hooks then just test for that marker,
# which costs a bash builtin instead of a `git check-ignore` fork (~65ms).
#
# Run synchronously (not backgrounded): Claude Code kills the hook's process
# group when the hook returns, so a backgrounded index would be truncated. A
# full index on a mid-size repo takes under a second.

set -uo pipefail

ABYSS="$(command -v abyss 2>/dev/null || true)"
for cand in "${HOME}/.code-abyss/bin/abyss.exe" "${HOME}/.code-abyss/bin/abyss" "${APPDATA:-}/npm/node_modules/@code-abyss/cli/bin/abyss-bin.exe"; do
  [ -x "$cand" ] && { ABYSS="$cand"; break; }
done
[ -z "$ABYSS" ] && exit 0

cat >/dev/null 2>&1 || true

DB=".code-abyss/index.db"
MARK=".code-abyss/.hook-enabled"

if [ -f "$MARK" ]; then
  # Already opted in — refresh only if a source file is newer than the index.
  # Parenthesize the -name group: without it, `-newer` binds to the last -name
  # only, so a stale .go/.rs/.ts/.tsx/.js file would never trigger a re-index.
  NEWER="$(find . \( -name '*.go' -o -name '*.rs' -o -name '*.ts' -o -name '*.tsx' \
    -o -name '*.js' -o -name '*.py' \) -newer "$DB" 2>/dev/null | head -1)"
  if [ ! -f "$DB" ] || [ -n "$NEWER" ]; then
    "$ABYSS" index >/dev/null 2>&1
  fi
  exit 0
fi

# Not opted in yet. Only repos that already ignore `.code-abyss/` may be indexed,
# so a stray index never shows up in someone's `git status`. Probe a child path,
# not the bare dir: `/.code-abyss/` only matches once the directory exists.
case "$(git check-ignore -q .code-abyss/index.db 2>/dev/null; echo $?)" in
  0) ;;
  *) exit 0 ;;
esac

mkdir -p .code-abyss
: > "$MARK"
"$ABYSS" index >/dev/null 2>&1

exit 0

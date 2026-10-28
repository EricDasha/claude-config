#!/usr/bin/env bash
# abyss PreToolUse bridge for Claude Code on Windows.
#
# Why this exists — three upstream gaps, all verified against
# abyss 0.5.30 + Claude Code 2.1.310:
#
#   1. `abyss hook pre-edit` matches REPO-RELATIVE paths only. Claude Code sends
#      an absolute path (`C:\...`), which yields an empty card — the hook looks
#      installed but never fires. Fixed by normalizing to a repo-relative path.
#
#   2. `abyss hook pre-edit` writes the card to STDERR. Claude Code discards
#      stderr from hooks that exit 0 (only exit 2 feeds it back, and that blocks
#      the tool call). Fixed by re-emitting the card as hookSpecificOutput JSON.
#
#   3. `abyss attach claude` emits `command: "abyss hook pre-edit"`, which on
#      Windows goes through the npm .cmd shim — node spawn + re-exec, ~440ms per
#      call. Fixed by resolving the native exe (~120ms).
#
# Opt-in gate: the session-init hook drops a marker into `.code-abyss/` only
# after confirming the repo ignores it. Checking for that marker is a bash
# builtin; calling `git check-ignore` here would cost ~65ms on every Edit/Write.
#
# Everything below is bash builtins plus ONE child process (abyss). Under Git
# Bash on Windows each spawned process costs 60-100ms, so the count matters.

set -uo pipefail

ABYSS="$(command -v abyss 2>/dev/null || true)"
for cand in "${HOME}/.code-abyss/bin/abyss.exe" "${HOME}/.code-abyss/bin/abyss" "${APPDATA:-}/npm/node_modules/@code-abyss/cli/bin/abyss-bin.exe"; do
  [ -x "$cand" ] && { ABYSS="$cand"; break; }
done
[ -z "$ABYSS" ] && exit 0

# Opt-in gate (builtin, ~0.5ms).
[ -f .code-abyss/.hook-enabled ] || exit 0

IFS= read -r -d '' PAYLOAD || true
[ -z "$PAYLOAD" ] && exit 0

# Payload is one line of JSON. A Windows path never contains a double quote, so
# these parameter expansions stay exact without a parser.
RAW="${PAYLOAD#*\"file_path\":\"}"; RAW="${RAW%%\"*}"
CWD="${PAYLOAD#*\"cwd\":\"}";        CWD="${CWD%%\"*}"
[ -z "$RAW" ] || [ "$RAW" = "$PAYLOAD" ] && exit 0

# Unescape JSON `\\` first, then flip remaining separators.
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

# Anything still absolute points outside the hook's cwd — leave it alone.
case "$REL" in
  [A-Za-z]:/*|/*) exit 0 ;;
  "") exit 0 ;;
esac

CARD="$(printf '{"tool_name":"Edit","tool_input":{"file_path":"%s"}}' "$REL" \
  | "$ABYSS" hook pre-edit 2>&1 1>/dev/null)"
[ -z "${CARD//[[:space:]]/}" ] && exit 0

# Escape for JSON: backslash first, then quotes, then control characters.
# The card is UTF-8 (·, ←, —); JSON passes those through untouched.
ESC="${CARD//\\/\\\\}"
ESC="${ESC//\"/\\\"}"
ESC="${ESC//$'\r'/}"
ESC="${ESC//$'\t'/  }"
ESC="${ESC//$'\n'/\\n}"

# Plain stdout on exit 0 only reaches the debug log; additionalContext is
# inserted next to the tool result, which is what we want.
printf '{"hookSpecificOutput":{"hookEventName":"PreToolUse","additionalContext":"%s"}}' "$ESC"

exit 0

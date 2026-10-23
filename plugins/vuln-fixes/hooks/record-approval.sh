#!/usr/bin/env bash
# UserPromptSubmit hook: the only path that approves repos or resets the gate.
#
# Droid expands slash commands before this hook runs, so /vuln-approve and /vuln-reset reach
# it as their command bodies, which carry a sentinel line:
#   VULN_FIXES_APPROVE: <repo|all>... [--major]
#   VULN_FIXES_RESET
# A typed message that starts with "APPROVE vuln-fixes: ..." or "RESET vuln-fixes", or the
# raw "/vuln-approve ..." / "/vuln-reset" text, is accepted too.
set -u

GATE="$(cd "$(dirname "$0")/../scripts" && pwd)/gate.sh"

input="$(cat)"
command -v jq >/dev/null 2>&1 || exit 0
prompt="$(jq -r '.prompt // empty' <<<"$input")"
[ -n "$prompt" ] || exit 0

first_line="${prompt%%$'\n'*}"
approve_args=""
approve=false
reset=false

if sentinel="$(grep -m1 -E '^[[:space:]]*VULN_FIXES_APPROVE:' <<<"$prompt")"; then
  approve=true
  approve_args="${sentinel#*VULN_FIXES_APPROVE:}"
elif grep -qE '^[[:space:]]*VULN_FIXES_RESET[[:space:]]*$' <<<"$prompt"; then
  reset=true
else
  shopt -s nocasematch
  re_approve='^[[:space:]]*(/vuln-approve|APPROVE[[:space:]]+vuln-fixes:)[[:space:]]*(.*)$'
  re_reset='^[[:space:]]*(/vuln-reset|RESET[[:space:]]+vuln-fixes)([[:space:]]|$)'
  if [[ "$first_line" =~ $re_approve ]]; then
    approve=true
    approve_args="${BASH_REMATCH[2]}"
  elif [[ "$first_line" =~ $re_reset ]]; then
    reset=true
  fi
  shopt -u nocasematch
fi

if [ "$approve" = true ]; then
  read -ra argv <<<"${approve_args//,/ }"
  echo "[vuln-fixes gate] The user approved patching. Recorded result:"
  "$GATE" approve "${argv[@]}"
  echo "Only repos listed as approved above may be edited. Run gate.sh status to confirm."
elif [ "$reset" = true ]; then
  echo "[vuln-fixes gate] $("$GATE" reset)"
fi
exit 0

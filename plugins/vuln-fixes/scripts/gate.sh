#!/usr/bin/env bash
# vuln-fixes approval gate state.
#
#   gate.sh register <repo-path>...   mark repos as in inventory (locked for edits)
#   gate.sh status [--json]           show every registered repo and its status
#   gate.sh done <repo-path>...       re-lock repos after their PR is open
#   gate.sh approve <repo|all>... [--major]   USER ONLY (run by the UserPromptSubmit hook)
#   gate.sh reset                     USER ONLY: forget all state and disarm the gate
#
# State: ${VULN_FIXES_STATE_DIR:-$HOME/.factory/vuln-fixes}/state.json
set -euo pipefail

STATE_DIR="${VULN_FIXES_STATE_DIR:-$HOME/.factory/vuln-fixes}"
STATE="$STATE_DIR/state.json"

die() { echo "gate.sh: $*" >&2; exit 1; }
command -v jq >/dev/null 2>&1 || die "jq is required"

now() { date -u +%Y-%m-%dT%H:%M:%SZ; }

abspath() {
  local p="$1"
  if realpath -m / >/dev/null 2>&1; then realpath -m -- "$p"; else
    (cd "$p" 2>/dev/null && pwd -P) || die "cannot resolve path: $p"
  fi
}

load() {
  mkdir -p "$STATE_DIR"
  [ -f "$STATE" ] || echo '{"repos":{}}' >"$STATE"
}

save() {
  local tmp
  tmp="$(mktemp "$STATE_DIR/.state.XXXXXX")"
  cat >"$tmp"
  mv "$tmp" "$STATE"
}

cmd_register() {
  [ $# -gt 0 ] || die "register needs at least one repo path"
  load
  local p ts
  ts="$(now)"
  for r in "$@"; do
    p="$(abspath "$r")"
    [ -d "$p" ] || die "not a directory: $r"
    jq --arg p "$p" --arg ts "$ts" \
      '.repos[$p] //= {"status":"inventory","registered_at":$ts}' "$STATE" | save
    echo "registered (locked): $p"
  done
}

cmd_status() {
  [ -f "$STATE" ] || { echo "no active vuln-fixes run (gate disarmed)"; return 0; }
  if [ "${1:-}" = "--json" ]; then jq . "$STATE"; return 0; fi
  jq -r '.repos | to_entries[] | "\(.value.status)\t\(if .value.allow_major then "major-ok" else "-" end)\t\(.key)"' "$STATE"
}

cmd_done() {
  [ -f "$STATE" ] || die "no active run"
  local p
  for r in "$@"; do
    p="$(abspath "$r")"
    jq --arg p "$p" --arg ts "$(now)" \
      'if .repos[$p] then .repos[$p].status="done" | .repos[$p].done_at=$ts else . end' "$STATE" | save
    echo "done (re-locked): $p"
  done
}

cmd_approve() {
  [ -f "$STATE" ] || { echo "vuln-fixes: nothing to approve (no repos registered)"; return 0; }
  local major=false tokens=() t
  for t in "$@"; do
    case "$t" in
      --major) major=true ;;
      ,|"") ;;
      *) tokens+=("${t%,}") ;;
    esac
  done
  [ ${#tokens[@]} -gt 0 ] || { echo "vuln-fixes: no repos named. Usage: /vuln-approve <repo|all>... [--major]"; return 0; }
  local repos matched unmatched=() ts
  ts="$(now)"
  repos="$(jq -r '.repos | keys[]' "$STATE")"
  for t in "${tokens[@]}"; do
    if [ "$t" = "all" ]; then
      matched="$(jq -r '.repos | to_entries[] | select(.value.status=="inventory") | .key' "$STATE")"
    else
      matched="$(printf '%s\n' "$repos" | awk -v t="$t" 'length($0) && ($0 == t || substr($0, length($0)-length(t)) == "/" t)')"
    fi
    if [ -z "$matched" ]; then unmatched+=("$t"); continue; fi
    while IFS= read -r p; do
      jq --arg p "$p" --arg ts "$ts" --argjson major "$major" \
        '.repos[$p].status="approved" | .repos[$p].approved_at=$ts | .repos[$p].allow_major=$major' "$STATE" | save
      echo "vuln-fixes: approved $p$( [ "$major" = true ] && echo ' (major upgrades allowed)')"
    done <<<"$matched"
  done
  if [ ${#unmatched[@]} -gt 0 ]; then
    echo "vuln-fixes: no registered repo matches: ${unmatched[*]} (nothing approved for these)"
  fi
}

cmd_reset() {
  rm -f "$STATE"
  echo "vuln-fixes: state cleared, gate disarmed"
}

sub="${1:-}"
shift || true
case "$sub" in
  register) cmd_register "$@" ;;
  status) cmd_status "$@" ;;
  done) cmd_done "$@" ;;
  approve) cmd_approve "$@" ;;
  reset) cmd_reset ;;
  *) sed -n '2,10p' "$0" | sed 's/^# \{0,1\}//'; exit 2 ;;
esac

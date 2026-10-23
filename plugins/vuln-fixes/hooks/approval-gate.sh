#!/usr/bin/env bash
# PreToolUse hook: block mutations in repos that the user has not approved.
# Exit 0 = allow, exit 2 = block (stderr is shown to Droid).
set -u

STATE_DIR="${VULN_FIXES_STATE_DIR:-$HOME/.factory/vuln-fixes}"
STATE="$STATE_DIR/state.json"

# Fast path: no active vuln-fixes run.
[ -f "$STATE" ] || exit 0

input="$(cat)"
if ! command -v jq >/dev/null 2>&1; then
  echo "vuln-fixes gate: jq is required while a vuln-fixes run is active ($STATE). Install jq, or ask the user to run gate.sh reset." >&2
  exit 2
fi

tool="$(jq -r '.tool_name // empty' <<<"$input")"
case "$tool" in
  Create | Edit | MultiEdit | ApplyPatch | Write | Execute) ;;
  *) exit 0 ;;
esac
cwd="$(jq -r '.cwd // empty' <<<"$input")"

block() {
  echo "vuln-fixes approval gate: $1" >&2
  exit 2
}

resolve() {
  local p="$1"
  case "$p" in /*) ;; *) p="${cwd%/}/$p" ;; esac
  realpath -m -- "$p" 2>/dev/null || printf '%s\n' "$p"
}

under() { [ "$1" = "$2" ] || case "$1" in "$2"/*) return 0 ;; *) return 1 ;; esac; }

mapfile -t locked < <(jq -r '.repos | to_entries[] | select(.value.status != "approved") | .key' "$STATE" 2>/dev/null)
state_real="$(realpath -m -- "$STATE_DIR" 2>/dev/null || echo "$STATE_DIR")"

locked_repo_for() {
  local r
  for r in "${locked[@]}"; do
    if under "$1" "$r"; then
      printf '%s\n' "$r"
      return 0
    fi
  done
  return 1
}

if [ "$tool" != "Execute" ]; then
  mapfile -t paths < <(
    jq -r '.tool_input.file_path // empty, .tool_input.path // empty' <<<"$input"
    jq -r '.tool_input | .. | strings' <<<"$input" |
      sed -nE 's/^\*\*\* (Add|Update|Delete) File: (.+)$/\2/p; s/^\*\*\* Move to: (.+)$/\1/p'
  )
  for raw in "${paths[@]}"; do
    [ -n "$raw" ] || continue
    p="$(resolve "$raw")"
    under "$p" "$state_real" && block "the gate state in $STATE_DIR can only be changed by the user."
    if repo="$(locked_repo_for "$p")"; then
      block "$repo has not been approved for patching. Show the inventory and wait for the user to run /vuln-approve $(basename "$repo")."
    fi
  done
  exit 0
fi

cmd="$(jq -r '.tool_input.command // empty' <<<"$input")"
[ -n "$cmd" ] || exit 0

if grep -qE 'gate\.sh["'"'"']?[[:space:]]+(approve|reset)' <<<"$cmd" ||
  grep -qF -- "$state_real" <<<"$cmd" || grep -qF -- "vuln-fixes/state.json" <<<"$cmd"; then
  block "approving repos and editing gate state are user-only actions (/vuln-approve, /vuln-reset)."
fi

[ ${#locked[@]} -gt 0 ] || exit 0

scope=""
if [ -n "$cwd" ] && scope="$(locked_repo_for "$(resolve "$cwd")")"; then :; else
  scope=""
  for r in "${locked[@]}"; do
    if grep -qF -- "$r" <<<"$cmd"; then
      scope="$r"
      break
    fi
  done
fi
[ -n "$scope" ] || exit 0

mut='(^|[;&|[:space:](])(git[[:space:]]+(-C[[:space:]]+[^[:space:]]+[[:space:]]+)?(commit|push|merge|rebase|reset|revert|apply|am|cherry-pick|stash|checkout|switch|restore|rm|mv|add|tag)|gh[[:space:]]+pr[[:space:]]+(create|merge|edit)|glab[[:space:]]+mr[[:space:]]+(create|merge)|sed[[:space:]]+(-[a-zA-Z]*i|--in-place)|perl[[:space:]]+-[a-zA-Z]*i|tee|mv|cp|rm|truncate|patch|install|ln|chmod|touch|mkdir|dd|npm[[:space:]]+(install|i|ci|update|uninstall|pkg)|pnpm[[:space:]]+(install|add|update|i)|yarn|composer[[:space:]]+(require|update|install)|docker[[:space:]]+(push|tag))([[:space:]]|$)'
if grep -qE "$mut" <<<"$cmd"; then
  block "$scope has not been approved, so mutating commands there are blocked. Read-only inspection is fine; wait for /vuln-approve $(basename "$scope")."
fi

# Redirects: drop fd duplications and /dev/null targets, then check where the rest write.
stripped="$(sed -E 's/[0-9]*>&[0-9-]+//g; s/&?[0-9]*>>?[[:space:]]*\/dev\/null//g' <<<"$cmd")"
while IFS= read -r target; do
  [ -n "$target" ] || continue
  t="$(resolve "${target//[\"\']/}")"
  if under "$t" "$scope" || under "$t" "$state_real"; then
    block "$scope has not been approved, so writing files there (shell redirect to $target) is blocked."
  fi
done < <(grep -oE '>>?[[:space:]]*[^[:space:];&|]+' <<<"$stripped" | sed -E 's/^>>?[[:space:]]*//')

exit 0

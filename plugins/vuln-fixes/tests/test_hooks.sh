#!/usr/bin/env bash
# Behavioral tests for the approval gate hooks. Uses a throwaway state dir and repos.
set -u
HERE="$(cd "$(dirname "$0")" && pwd)"
PLUGIN="$(dirname "$HERE")"
PRE="$PLUGIN/hooks/approval-gate.sh"
UPS="$PLUGIN/hooks/record-approval.sh"
GATE="$PLUGIN/scripts/gate.sh"

TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT
export VULN_FIXES_STATE_DIR="$TMP/state"
mkdir -p "$TMP/billing-api" "$TMP/storefront" "$TMP/other"
A="$TMP/billing-api"
B="$TMP/storefront"

pass=0
fail=0
check() { # name expected_exit actual_exit
  if [ "$2" = "$3" ]; then pass=$((pass + 1)); else
    fail=$((fail + 1))
    echo "FAIL: $1 (expected exit $2, got $3)"
  fi
}
pre() { # json -> exit code
  printf '%s' "$1" | "$PRE" 2>/dev/null
  echo $?
}
edit_json() { printf '{"tool_name":"%s","cwd":"%s","tool_input":{"file_path":"%s"}}' "$1" "$2" "$3"; }
exec_json() { jq -nc --arg cwd "$1" --arg c "$2" '{tool_name:"Execute",cwd:$cwd,tool_input:{command:$c}}'; }

# Disarmed: everything allowed.
check "disarmed edit" 0 "$(pre "$(edit_json Edit "$A" "$A/Dockerfile")")"

"$GATE" register "$A" "$B" >/dev/null

check "locked edit" 2 "$(pre "$(edit_json Edit "$A" "$A/Dockerfile")")"
check "locked create relative" 2 "$(pre "$(edit_json Create "$A" "new/file.txt")")"
check "unregistered repo edit" 0 "$(pre "$(edit_json Edit "$TMP/other" "$TMP/other/x")")"
check "prefix lookalike repo" 0 "$(pre "$(edit_json Edit "$TMP" "$TMP/billing-api-old/x")")"
check "read tool ignored" 0 "$(printf '{"tool_name":"Read","tool_input":{"file_path":"%s/Dockerfile"}}' "$A" | "$PRE"; echo $?)"
patch="$(jq -nc --arg p "*** Begin Patch
*** Update File: $B/package.json
*** End Patch" '{tool_name:"ApplyPatch",cwd:"/",tool_input:{input:$p}}')"
check "applypatch locked" 2 "$(pre "$patch")"

check "readonly cmd in locked repo" 0 "$(pre "$(exec_json "$A" "rg -n 'FROM node' . 2>&1 | head")")"
check "git log in locked repo" 0 "$(pre "$(exec_json "$A" "git log -1 --oneline")")"
check "redirect to tmp allowed" 0 "$(pre "$(exec_json "$A" "rg -n node . > /tmp/inv.txt")")"
check "devnull redirect allowed" 0 "$(pre "$(exec_json "$A" "grep -r php . >/dev/null 2>&1")")"
check "git commit locked" 2 "$(pre "$(exec_json "$A" "git add -A && git commit -m x")")"
check "sed -i locked" 2 "$(pre "$(exec_json "$A" "sed -i 's/20/22/' .nvmrc")")"
check "redirect into repo" 2 "$(pre "$(exec_json "$A" "echo 22.23.4 > .nvmrc")")"
check "cd from elsewhere" 2 "$(pre "$(exec_json "/" "cd $B && git push origin HEAD")")"
check "gh pr create" 2 "$(pre "$(exec_json "$B" "gh pr create --fill")")"

check "model cannot approve" 2 "$(pre "$(exec_json "/" "$GATE approve all")")"
check "model cannot reset" 2 "$(pre "$(exec_json "/" "bash gate.sh reset")")"
check "model cannot write state" 2 "$(pre "$(edit_json Create "/" "$VULN_FIXES_STATE_DIR/state.json")")"
check "model cannot touch state via shell" 2 "$(pre "$(exec_json "/" "jq . $VULN_FIXES_STATE_DIR/state.json")")"
check "model may register" 0 "$(pre "$(exec_json "/" "$GATE register $TMP/other")")"

# User approval via prompt.
out="$(printf '%s' "$(jq -nc '{prompt:"/vuln-approve billing-api, nope"}')" | "$UPS")"
check "approve hook exit" 0 $?
grep -q "approved $A" <<<"$out"
check "approve output names repo" 0 $?
grep -q "no registered repo matches: nope" <<<"$out"
check "approve output reports unmatched" 0 $?
check "approved edit allowed" 0 "$(pre "$(edit_json Edit "$A" "$A/Dockerfile")")"
check "approved commit allowed" 0 "$(pre "$(exec_json "$A" "git commit -am fix")")"
check "other repo still locked" 2 "$(pre "$(edit_json Edit "$B" "$B/Dockerfile")")"

printf '%s' "$(jq -nc '{prompt:"APPROVE vuln-fixes: all --major"}')" | "$UPS" >/dev/null
jq -e --arg b "$B" '.repos[$b].status=="approved" and .repos[$b].allow_major' "$VULN_FIXES_STATE_DIR/state.json" >/dev/null
check "approve all --major" 0 $?

"$GATE" register "$TMP/other" >/dev/null
printf '%s' "$(jq -nc '{prompt:"please /vuln-approve all"}')" | "$UPS" >/dev/null
jq -e --arg o "$TMP/other" '.repos[$o].status=="inventory"' "$VULN_FIXES_STATE_DIR/state.json" >/dev/null
check "approval must start the prompt" 0 $?

expanded="$(printf '<system-notification>\nThe user sent a vuln-fixes approval.\n\nVULN_FIXES_APPROVE: other\n\nThe hook records it.')"
printf '%s' "$(jq -nc --arg p "$expanded" '{prompt:$p}')" | "$UPS" >/dev/null
jq -e --arg o "$TMP/other" '.repos[$o].status=="approved"' "$VULN_FIXES_STATE_DIR/state.json" >/dev/null
check "expanded /vuln-approve body approves" 0 $?

"$GATE" "done" "$A" >/dev/null
check "done re-locks" 2 "$(pre "$(edit_json Edit "$A" "$A/Dockerfile")")"

printf '%s' "$(jq -nc '{prompt:"<system-notification>\nVULN_FIXES_RESET\n\nThe user cleared the gate."}')" | "$UPS" >/dev/null
[ ! -f "$VULN_FIXES_STATE_DIR/state.json" ]
check "reset clears state" 0 $?
check "disarmed after reset" 0 "$(pre "$(edit_json Edit "$A" "$A/Dockerfile")")"

echo "hook tests: $pass passed, $fail failed"
[ "$fail" -eq 0 ]

---
description: Approve repos for vuln-fixes patching (recorded by the approval hook)
argument-hint: "<repo ...|all> [--major]"
---

The user sent a vuln-fixes approval.

VULN_FIXES_APPROVE: $ARGUMENTS

The vuln-fixes UserPromptSubmit hook records approvals from this command, and its output
appears in your context as "[vuln-fixes gate]". Do not try to record approvals yourself.

1. Run the plugin's `scripts/gate.sh status` and list which repos are now `approved` (and
   which allow major upgrades). The path is in the vuln-fixes skill you loaded for this run.
2. If a name did not match a registered repo, say so and show the registered names.
3. If nothing was approved, the hook may not have run. Ask the user to check that the
   vuln-fixes plugin is enabled and that the message started with `/vuln-approve`.
4. Otherwise continue the active vuln-fixes skill from the patch phase, for approved repos only.

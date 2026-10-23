---
description: Clear the vuln-fixes approval gate (recorded by the hook)
---

VULN_FIXES_RESET

The user cleared the vuln-fixes gate. The UserPromptSubmit hook deleted the state, so no
repo is locked anymore. Confirm by running the plugin's `scripts/gate.sh status`, which
should say the gate is disarmed. Do not continue any patching from an earlier run unless
the user starts a new one.

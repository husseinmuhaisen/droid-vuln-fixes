---
description: Show the vuln-fixes approval gate state and the current run's progress
---

Show the vuln-fixes state.

1. Run the plugin's `scripts/gate.sh status` (the path is in the vuln-fixes skill for this
   run; if no skill is loaded, find the plugin's `scripts/gate.sh` under
   `~/.factory/plugins`). Present the result as a table: repo, status (`inventory` =
   locked, `approved`, `done` = re-locked), major upgrades allowed.
2. If a run is in progress in this session, add the rollup so far: PRs opened, blocked
   items, and repos still waiting for approval.
3. Remind the user: `/vuln-approve <repo|all> [--major]` approves repos, and `/vuln-reset`
   clears the gate when the run is finished.

# vuln-fixes

A Droid plugin that finds and patches vulnerable runtimes across your repositories. It
ships dedicated skills for the October 21, 2026 PHP, Node.js and GitLab advisories, plus a
generic skill for any runtime CVE.

Each run follows the same steps:
1. Take a read-only inventory.
2. Stop at an approval gate that hooks enforce.
3. Patch each approved repo to a verified fixed version, with tests run before and after
   inside the built image.
4. Open one focused PR per repo, with a risk label and a rollout and rollback plan.

The fix takes effect only after you deploy.

## Skills

| Skill | Use for |
| --- | --- |
| `patching-php-runtimes` | CVE-2026-109618 and CVE-2026-109619 (PHP critical RCE). Fixed in 8.5.12, 8.4.27, 8.3.36 and 8.2.35. |
| `patching-node-runtimes` | Node.js October 21, 2026 release (CVE-2026-111497 and 9 more). Fixed in 26.12.1, 24.22.1 and 22.23.4. Also covers EOL Node 20 and older. |
| `patching-gitlab-self-managed` | CVE-2026-110264 (self-managed GitLab RCE, CVSS 10.0). Fixed in 19.5.1, 19.4.3, 19.3.6, 19.2.9, 19.1.9, 19.0.10 and 18.11.13. |
| `patching-runtime-cves` | Any other runtime or server advisory. It first builds and confirms an advisory record. |

Ask in plain language ("please fix my PHP vulnerability in acme/billing-api"), or invoke a
skill directly, for example `/patching-node-runtimes acme/storefront`.

## Commands

| Command | What it does |
| --- | --- |
| `/vuln-fix <php\|node\|gitlab\|advisory-url\|CVE> [repo ...]` | Picks the matching skill and starts a run. |
| `/vuln-approve <repo ...\|all> [--major]` | Approves repos for patching. `--major` also allows major upgrades. This is the only way to unlock a repo. |
| `/vuln-status` | Shows the gate state and run progress. |
| `/vuln-reset` | Clears the gate when you are done. |

## Droid

The skills dispatch `vuln-patcher` through the Task tool, one per approved repo, with at most
five running at once. It handles a single repo:
1. Verifies the fixed targets.
2. Edits only the files that select the runtime.
3. Runs baseline and after builds, tests and smoke tests inside the image.
4. Opens the PR and returns a structured report.

If custom droids are disabled, the skills run the same steps inline.

## Approval gate (hooks)

- **Registration.** The first step of a run is `scripts/gate.sh register <repo>`, which locks the repo.
- **`hooks/approval-gate.sh` (PreToolUse).** It blocks file edits (Create, Edit, ApplyPatch)
  in locked repos. It also blocks mutating shell commands there: git commit, push and
  checkout; `gh pr create`; `sed -i`; `cp`, `mv` and `rm`; package installs; and redirects
  into the repo. It always blocks changes to the gate state.
- **`hooks/record-approval.sh` (UserPromptSubmit).** This is the only path that approves repos.
  It reads the expanded `/vuln-approve` command (a `VULN_FIXES_APPROVE:` line), or a message
  that starts with `APPROVE vuln-fixes: <repos>`. The model cannot send user prompts, so it
  cannot approve itself.
- **State.** The state lives in `~/.factory/vuln-fixes/state.json`. Set `VULN_FIXES_STATE_DIR`
  to override the location.
- **Fast path.** When no run is active, the hooks exit immediately.

Limits: the shell check is a best-effort pattern match. It is defense in depth, not a
sandbox. A determined process could write files in ways the patterns miss. The gate also
needs `jq`. If `jq` is missing while a run is active, the gate fails closed.

UserPromptSubmit hooks do not run in `droid exec` (headless mode), so `/vuln-approve`
cannot unlock repos there. Use the interactive CLI or the Factory App for the approval step.

## Helper scripts

- `scripts/scan_signals.py --runtime node|php|gitlab|all <path>...` scans read-only and
  writes JSONL of version signals: images, version files, CI setup actions, OS packages,
  source builds, Lambda runtimes, Helm, Operator and config management.
- `scripts/classify_versions.py --advisory <file> [--format table]` classifies each signal
  as fixed, vulnerable, no-fix-on-line, floating-rebuild, vendor-check, signal-only,
  not-affected or unknown.
- `scripts/gate.sh` manages the gate state (`register`, `status`, `done`; `approve` and
  `reset` are reserved for the user).

These scripts need Python 3.9+, bash, `jq` and coreutils (`realpath -m`).

## References

- `references/workflow.md`: the shared phases, the evidence each PR must carry, and the
  rationalizations to reject.
- `references/inventory-signals.md`: where runtime versions hide, and which ones the scanner covers.
- `references/pr-template.md`: the PR body template.
- `references/advisories/*.json` and `advisory.schema.json`: the advisory records, built from
  the official php.net, nodejs.org and GitLab advisories (sources listed in each file).

## Development

```bash
python3 -m unittest discover -s tests   # classifier, scanner, advisory checks
./tests/test_hooks.sh                   # approval gate behavior
shellcheck hooks/*.sh scripts/*.sh tests/*.sh
```

When you change the plugin, bump `version` in `.factory-plugin/plugin.json`.

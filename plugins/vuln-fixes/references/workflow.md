# Shared remediation workflow

Every vuln-fixes skill follows these phases. The skill supplies the advisory file, the
runtime-specific rules, and the paths to the helper scripts (`$SCRIPTS` below means the
plugin's `scripts/` directory).

The approval gate is enforced by hooks, not by trust: once a repo is registered, edits,
commits, pushes and PRs in it are blocked until the user approves it. Registering is the
first thing you do, before any analysis, so a mistake during inventory cannot change a repo.

## Phase 0: Scope

1. Determine the repos. Default to what the user named. If they said "all repos" or an
   org, list them with the host CLI (`gh repo list <org> --limit 1000 --json nameWithOwner,isArchived`,
   `glab repo list -g <group>`), skip archived repos, and say how many you found.
2. Create a run directory outside every repo: `${TMPDIR:-/tmp}/vuln-fixes/<advisory-id>/`.
   Inventory files, logs and clones live there.
3. Get local checkouts. Use existing local clones when the user points at them. Otherwise
   shallow-clone into the run directory (`git clone --depth 1 --filter=blob:none`). Prefer
   host code search first when it exists (`gh search code 'FROM node:' --owner <org>`) to
   skip repos with no signal, but remember code search misses dotfiles and is often absent
   on GitHub Enterprise Server and self-managed GitLab. When in doubt, clone.
4. Register every checkout: `$SCRIPTS/gate.sh register <path>...`.

## Phase 1: Inventory (read-only)

1. Run the scanner and classifier:
   ```bash
   python3 $SCRIPTS/scan_signals.py --runtime <rt> <checkout>... > <run>/signals.jsonl
   python3 $SCRIPTS/classify_versions.py --advisory <advisory.json> <run>/signals.jsonl > <run>/inventory.jsonl
   python3 $SCRIPTS/classify_versions.py --advisory <advisory.json> --format table <run>/signals.jsonl
   ```
2. Do a manual pass for what the scanner cannot see, using the signal list the skill linked:
   `ARG`-parameterized base images (`FROM node:${NODE_VERSION}`), internal base images that
   wrap the runtime, Packer templates, Chef/Puppet, Nix, Bazel rules, vendored binaries.
   Add those rows by hand with `confidence: low|medium` and the evidence you used.
3. Resolve every `vendor-check` row before the gate: read the vendor security tracker
   (Debian, Ubuntu, RHEL, Alpine secdb, AWS Lambda runtime notes, GitLab chart mappings)
   and record the fixed vendor version and source. If you cannot resolve it, keep it
   `unknown` and say what the user must check.
4. Resolve `unknown` aliases (`lts`, `latest`, `lts-alpine`) by inspecting what they point
   to today (`docker buildx imagetools inspect node:lts-alpine`), and note that the answer
   changes over time.
5. For each row decide: production runtime vs build/CI-only, internet exposure if
   discernible (ingress, public load balancer, `EXPOSE`), test coverage (none, thin, suite:
   look for a test script and a CI test step), and confidence.
6. Write one table (columns: repo, file:line, signal, current, pin, prod/CI, exposure,
   tests, status, confidence, note). List repos you could not scan in a separate table with
   the reason.

## Phase 2: Approval gate

1. Show the table. Summarize: counts by status, the riskiest items first, and every change
   riskier than a patch bump (major/minor upgrade, base-OS change, image flavor change,
   likely app-code change) so the user can approve it explicitly.
2. Tell the user exactly how to approve, then end your turn:
   `/vuln-approve <repo> [<repo>...] [--major]` (or `/vuln-approve all`). `--major` allows
   major upgrades for the named repos; without it, `no-fix-on-line` items are reported, not
   upgraded.
3. Do not continue until the hook reports approved repos. Then run `$SCRIPTS/gate.sh status`
   and work only on repos whose status is `approved`.

If the user approves in plain language instead of the command, explain that the gate only
accepts `/vuln-approve` and ask them to send it. Do not try to approve on their behalf; the
hook blocks it.

## Phase 3: Patch, one patcher per approved repo

Dispatch the plugin's `vuln-patcher` droid with the Task tool, one task per approved repo,
at most five running at once (issue several Task calls in the same message). If custom
droids are disabled, run the same procedure inline, one repo at a time.

Give each patcher a self-contained handoff:
- Repo path, default branch, and the user's approval scope (patch only, or `--major`).
- The advisory JSON path and the inventory rows for that repo.
- `$SCRIPTS` path, run directory, and the PR template path.
- Registry or mirror hints the user gave (Artifactory, Nexus, Harbor, ECR).

Each patcher returns a structured report. Never treat a patcher summary as evidence on its
own; check that the report cites logs and digests.

## Phase 4: Evidence every PR must carry

- Every edited path, before → after, with the source used to verify the target exists.
- Image digests: rollback digest (old) and new multi-arch index digest.
- Baseline and after results for install, build, tests and smoke test, run inside the image.
- Runtime diff between old and new images (runtime version, bundled libraries, base OS).
- The runtime version printed by the built production artifact, or for CI-only paths and
  managed runtimes the best available evidence plus the check the user must run after merge.
- Risk label: `low` for a patch bump on the same base with tests; `high` for major/minor
  upgrades, base-OS changes, untested repos. Call out thin coverage.
- Rollout: staging or canary first; rollback target named, with the warning that it is
  still vulnerable and should be used only briefly.

## Phase 5: Rollup

1. One table: repo, PR, path, before → after, prod/CI, tests, risk, blocked items, follow-ups.
2. Mark finished repos `$SCRIPTS/gate.sh done <repo>` (this re-locks them).
3. Remind the user that nothing is fixed until the new build is deployed, and list floating
   tags that need a rebuild and the managed runtimes that need provider-side confirmation.
4. Tell the user `/vuln-reset` clears the gate when they are finished.

## Rationalizations to reject (all runtimes)

| Shortcut | Why it is wrong | Do instead |
| --- | --- | --- |
| "The user said fix everything, so approval is implied." | The gate exists because inventory surprises people. | Show the table; wait for `/vuln-approve`. |
| "The distro package version string looks fixed (or vulnerable)." | Distros backport fixes without changing upstream versions. | Check the vendor tracker. |
| "The tag floats, so it already has the fix." | Only a `--pull` rebuild and redeploy picks it up. | Rebuild, record the digest, list it for redeploy. |
| "Tests passed on my machine." | The host runtime is not the image runtime. | Run tests inside the built image. |
| "Bumping `engines.node` / `require.php` patches it." | Those fields do not choose the runtime. | Change what actually installs the runtime. |
| "The registry is blocked but the tag surely exists." | Guessed tags break builds or pull the wrong thing. | Mark the target unverified and let CI prove it. |
| "A tiny app-code change makes tests pass." | Unapproved code changes hide regressions in a security PR. | Stop, report the failure and the smallest fix, wait. |
| "The hook blocked me; I'll write the file another way." | Bypassing the gate defeats its purpose. | Stop and ask the user. |

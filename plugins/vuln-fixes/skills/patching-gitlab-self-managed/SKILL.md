---
name: patching-gitlab-self-managed
description: "Inventories and patches self-managed GitLab CE/EE affected by CVE-2026-110264 (CVSS 10.0 unauthenticated RCE, fixed in 19.5.1, 19.4.3, 19.3.6, 19.2.9, 19.1.9, 19.0.10, 18.11.13) across Omnibus, Docker, Helm chart, Operator and the IaC that deploys them. Use when the user asks to fix or patch a GitLab vulnerability or this CVE on their own instances. Not for GitLab.com, Dedicated or GitLab Runner."
version: 0.1.0
---

# Patching self-managed GitLab (CVE-2026-110264)

## When to Use
- The user runs GitLab themselves and asks to fix CVE-2026-110264 or "the GitLab RCE".

## When NOT to Use
- GitLab.com: already patched. GitLab Dedicated: tenants on 19.3.5-internal0 or
  19.4.2-internal0 and later already have the fix.
- GitLab Runner: a separate product, not covered by this advisory.
- A different GitLab release: use `patching-runtime-cves`.

## The advisory
Read `${DROID_PLUGIN_ROOT}/references/advisories/gitlab-2026-10.json`. In short: integer
overflow in the regular expression compiler gives unauthenticated RCE (CVSS 10.0). All
versions from 7.0 are affected. Fixed: **19.5.1, 19.4.3, 19.3.6, 19.2.9, 19.1.9, 19.0.10,
18.11.13**. Lines 18.10 and older have no backport. The same release fixes high-severity
auth and cache-poisoning issues too.

## Quick start
Follow [the shared workflow](../../references/workflow.md) with:
- `SCRIPTS=${DROID_PLUGIN_ROOT}/scripts`, `--runtime gitlab`, advisory above.
- Manual signals: [inventory signals](../../references/inventory-signals.md), GitLab section.
- PR body: [PR template](../../references/pr-template.md).

## GitLab-specific rules
Inventory:
- Repos usually hold the deployment, not GitLab itself: Docker Compose, Helm values and
  Argo CD apps, Terraform `helm_release`, Ansible roles, Omnibus package pins. Inventory
  those. When no repo pins a version (for example, a hand-managed VM), list the instance as
  "not in code" and give the user the check: `sudo gitlab-rake gitlab:env:info`, or the
  version shown at `/help` for admins.
- Helm chart and Operator versions are not GitLab versions. Map them using the official
  chart version mappings (source in the advisory JSON) and record the mapped GitLab version.
- Mention the published detections (Onigmo native worker crash, Org mode render error burst)
  so the user can check for exploitation attempts. Patching does not undo a compromise.

Patching:
- Same-line patch is preferred: bump to the fixed patch of the running minor.
- Lines with no fix (18.10 and older): plan an upgrade along the official upgrade path,
  including required stops and background migrations. This needs `--major` approval and is
  always high risk. Do not skip required stops.
- Docker: keep the edition (`-ee` / `-ce`) and the `-ee.0` / `-ce.0` suffix; verify the tag.
- Helm: bump the chart to the version that maps to the fixed GitLab version; keep values.
- Omnibus pins: update the package pin (`gitlab-ee=19.4.3-ee.0`); verify the package exists in
  the configured repo.
- Testing: you usually cannot run GitLab tests. Instead validate the deployment code:
  `helm template` / `helm lint` diff, `docker compose config`, `terraform plan` (read-only;
  never apply), Ansible `--check`. Record those as baseline and after.
- Rollout: always include a backup step (`gitlab-backup create` plus secrets and
  `gitlab.rb`) before upgrading, and note that downgrades after migrations are not
  supported, so rollback means restoring the backup.
- Evidence: the deployed version after rollout, via `gitlab-rake gitlab:env:info`. Before
  merge, give the mapped target version and the command the user must run.

## Rationalizations to Reject
| Shortcut | Required action |
| --- | --- |
| "Chart 9.4.x means GitLab 19.4.x." | Map with the official version table. |
| "Jump straight from 18.4 to 19.5." | Follow the upgrade path's required stops. |
| "Rollback is just the old image." | Migrations make that unsafe; rollback means restoring a backup. |
| "We use GitLab Runner, so we're affected." | Runner is out of scope; the server is what matters. |

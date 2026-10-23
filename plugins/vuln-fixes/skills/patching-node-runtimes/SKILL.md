---
name: patching-node-runtimes
description: "Inventories and patches Node.js runtimes affected by the October 21, 2026 Node.js security release (CVE-2026-111497 Brotli RCE and 9 more) across repos: Docker images, .nvmrc/.tool-versions/Volta, setup-node CI, NodeSource packages, Lambda and IaC, plus end-of-life Node 20 and older. Use when the user asks to fix, patch or upgrade a Node.js vulnerability or Node 20 EOL. Read-only inventory, enforced approval gate, tests before and after, one PR per repo."
version: 0.1.0
---

# Patching Node.js runtimes (October 21, 2026 security release)

## When to Use
- The user asks to fix "my Node vulnerability", CVE-2026-111497 or any CVE in the October
  21, 2026 Node.js release, or to get off Node 20 or older because it is unpatched.

## When NOT to Use
- npm package vulnerabilities (`npm audit` findings): those are dependency upgrades, not
  runtime patches.
- A different Node.js security release: use `patching-runtime-cves` with that advisory.
- Electron apps and vendor appliances: report them for a vendor update; do not patch them.

## The advisory
Read `${DROID_PLUGIN_ROOT}/references/advisories/node-2026-10.json`. In short: 10 CVEs, 4
high (Brotli decoder OOB write RCE; three TLS/DNS hostname issues). Fixed: **22.23.4,
24.22.1, 26.12.1**. Every other line (20 and older, odd lines like 23/25) is end-of-life,
still affected, and gets no fix. Bundled c-ares, OpenSSL (22/24), SQLite (22), Undici and the
CA store changed; the eMudhra intermediate CA was removed.

## Quick start
Follow [the shared workflow](../../references/workflow.md) with:
- `SCRIPTS=${DROID_PLUGIN_ROOT}/scripts`, `--runtime node`, advisory above.
- Manual signals: [inventory signals](../../references/inventory-signals.md), Node.js section.
- PR body: [PR template](../../references/pr-template.md).

## Node-specific rules
Inventory:
- Prioritize internet-facing services that decompress Brotli (HTTP servers, clients,
  proxies, `zlib.createBrotliDecompress`) and TLS clients that connect to user-supplied hosts.
- For each `no-fix-on-line` row, find upgrade-risk signals so the user can approve
  knowingly: import assertions (`assert { type: 'json' }` was removed in 22; use `with`),
  native addons (`binding.gyp`, `node-gyp`, prebuilt `.node` files), and APIs removed in the
  target major's release notes.

Patching (the patcher applies these):
- Exact image tag: smallest fixed patch on the same major, same variant (`-alpine`,
  `-slim`, `-bookworm`). Verify the tag exists before editing.
- Version files (`.nvmrc`, `.node-version`, `.tool-versions`, Volta, `mise.toml`): set the
  fixed patch and keep every file that names a version consistent.
- `actions/setup-node` with a floating version (`22`, `lts/*`): add `check-latest: true`,
  or pin the fixed patch. Without it the runner's cached older Node is used.
- `engines.node`: leave it unless it would exclude the new version (for example `20.x` on
  a 20 → 22 upgrade makes `npm ci` warn `EBADENGINE`).
- AWS Lambda `nodejsNN.x`: the exact patch is provider-managed. Check the public base image
  (`public.ecr.aws/lambda/nodejs:22`) or log `process.version`. With the Auto runtime-update
  mode AWS patches in place; with Function update or Manual mode a redeploy or runtime
  version change is required. Report, do not claim fixed.
- Major upgrades (20 → 22 or 24) only with `--major` approval. Also run tests with
  `NODE_OPTIONS=--pending-deprecation`, `npm rebuild` native addons from source, and list
  the applicable breaking changes in the PR.
- Runtime diff: compare `node -p process.versions` between old and new images. For
  services with outbound TLS, call out the CA store change.
- Evidence: `node -v` from the built production image.

## Rationalizations to Reject
| Shortcut | Required action |
| --- | --- |
| "Node 20 is close to 22, I'll just bump it." | Major upgrade: needs `--major` approval and the major-upgrade checks. |
| "`setup-node` with `22` already gets 22.23.4." | Only with `check-latest: true` or a pinned patch. |
| "Lambda `nodejs22.x` is patched by AWS." | Depends on the runtime-update mode; report the check. |
| "CI-only Node doesn't matter." | Lower priority, but patch it in the same PR when cheap and say so. |

# PR template

Title: `security: patch <runtime> for <advisory-id> (<CVE list or "N CVEs">)`

Labels: `security`, `risk:low` or `risk:high`.

```markdown
## Summary
Patches <runtime> in this repo for <advisory title> (<CVE ids>), per <advisory URL>.
Risk: **<low|high>** because <one sentence>.

## Changes
| Path | Before | After | Verified against |
| --- | --- | --- | --- |
| Dockerfile:1 | node:22.20.0-alpine | node:22.23.4-alpine | Docker Hub tag list, <date> |

Image digests (multi-arch index):
- Before (rollback target, still vulnerable): `sha256:...`
- After: `sha256:...`

Floating tags left as-is (need `--pull` rebuild and redeploy): <list or "none">.

## Not changed in this PR
- <EOL items, blocked items, vendor-managed runtimes, with the next step for each>

## Verification
| Step | Baseline | After |
| --- | --- | --- |
| Install | pass | pass |
| Build | pass | pass |
| Tests | 212 passed, 2 failed (pre-existing) | 212 passed, 2 failed (same) |
| Smoke (`GET /healthz`) | 200 | 200 |

Runtime diff: <runtime version, bundled libraries (OpenSSL, ICU, etc.), base OS>.
Runtime version from the built production image: `<output of node -v / php -v / gitlab-rake gitlab:env:info>`.
Logs: <attached or linked: baseline, after, runtime diff, smoke>.
Test coverage: <none | thin | suite>. <If thin: say so and recommend staging/canary.>

## Rollout
1. Deploy to staging or a canary; watch errors and latency for <window>.
2. Roll out to production.
3. Rollback: redeploy `<previous digest or version>`. It is still vulnerable; roll back only briefly.

This fix takes effect only after the new build is deployed.
```

# droid-vuln-fixes

A Droid plugin marketplace for patching critical runtime vulnerabilities across your
repositories. Each run takes a read-only inventory, stops at an approval gate that hooks
enforce, tests before and after the change, and opens one focused PR per repo.

| Plugin | Description |
| --- | --- |
| [vuln-fixes](plugins/vuln-fixes/) | PHP (CVE-2026-109618/109619), Node.js (Oct 21, 2026 release) and self-managed GitLab (CVE-2026-110264) skills, plus a generic skill for any runtime CVE |

## Install

```bash
droid plugin marketplace add <owner>/droid-vuln-fixes     # or a local path
droid plugin install vuln-fixes@droid-vuln-fixes --scope user
```

You can also use `/plugins` → Marketplaces in the CLI. To roll the plugin out to an
organization, see Factory's internal plugin marketplaces documentation.

## Use

```text
/vuln-fix node acme/storefront acme/billing-api
```

Droid inventories the repos and shows a table, then waits. Approve the repos you want patched:

```text
/vuln-approve storefront billing-api
```

Add `--major` to allow major upgrades, such as Node 20 to 22. Review each PR, roll it out
to staging or a canary first, and redeploy. Run `/vuln-reset` when you are done.

See [plugins/vuln-fixes/README.md](plugins/vuln-fixes/README.md) for details and limits.

## License

MIT. The advisory data is summarized from the official php.net, nodejs.org and GitLab
advisories. Each advisory file lists its sources.

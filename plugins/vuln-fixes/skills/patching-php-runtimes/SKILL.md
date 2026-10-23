---
name: patching-php-runtimes
description: "Inventories and patches PHP runtimes affected by CVE-2026-109618 and CVE-2026-109619 (critical unauthenticated RCE, fixed in PHP 8.5.12, 8.4.27, 8.3.36, 8.2.35) across repos: Docker images, distro packages, source builds, setup-php CI, FrankenPHP, Helm/IaC and config management. Use when the user asks to fix or patch a PHP vulnerability or these CVEs. Read-only inventory, enforced approval gate, tests before and after, one PR per repo."
version: 0.1.0
---

# Patching PHP runtimes (CVE-2026-109618, CVE-2026-109619)

## When to Use
- The user asks to fix "my PHP vulnerability", either CVE, or asks whether their PHP is affected.

## When NOT to Use
- Composer package vulnerabilities: those are dependency upgrades.
- Other PHP advisories: use `patching-runtime-cves`.
- Managed PHP hosting where the user controls no build (shared hosting, PaaS buildpacks
  with provider-chosen PHP): report the provider check instead.

## The advisory
Read `${DROID_PLUGIN_ROOT}/references/advisories/php-2026-10.json`. In short: two critical
RCEs in every web-serving SAPI (mod_php highest risk, exploit runs before application code;
also FPM, php-cgi, FrankenPHP, LiteSpeed). Fixed: **8.5.12, 8.4.27, 8.3.36, 8.2.35**. PHP
8.1 and older get no release; some vendors backport, and php.net published minimal source
backports for 7.4/8.0/8.1. PHP 8.2 reaches end of life on 31 December 2026.

These bugs are being exploited. If the inventory finds an internet-facing, unpatched
mod_php or FPM service, tell the user at the gate that the advisory recommends updating
immediately, and offer the interim mitigations below while PRs are prepared.

## Quick start
Follow [the shared workflow](../../references/workflow.md) with:
- `SCRIPTS=${DROID_PLUGIN_ROOT}/scripts`, `--runtime php`, advisory above.
- Manual signals: [inventory signals](../../references/inventory-signals.md), PHP section.
- PR body: [PR template](../../references/pr-template.md).

## PHP-specific rules
Inventory:
- Record the SAPI for each deployment (mod_php, FPM, FrankenPHP, LSAPI, CLI-only). CLI-only
  workers that never serve web requests are lower priority; say so.
- Distro packages keep the upstream version string after a backport (Ubuntu ships
  `8.3.6-0ubuntu0.24.04.x`, so `php -v` still says 8.3.6). Decide status from the vendor's
  security tracker or package changelog, and cite it.
- Flag `rpms.remirepo.net`: the PHP project said it would not have same-day updates.
- Look for per-request INI settings applied before request startup (`php_value` /
  `php_flag` in `.htaccess` or vhosts, nginx `PHP_VALUE`/`PHP_ADMIN_VALUE`). These are the
  confirmed consumer path for CVE-2026-109619 and matter for mitigations.

Patching:
- Images: smallest fixed patch on the same minor, same variant (`-fpm-alpine`, `-apache`,
  `-cli-bookworm`). Digest pins get the new digest. Floating tags (`php:8.3-fpm`) stay;
  require a `--pull --no-cache` rebuild and record the digest.
- Source builds: switch to the new php.net tarball and update its checksum from php.net's
  published value. Never compute a checksum from a download and call it verified.
- Distro packages: update to the vendor's fixed package (pin if the repo already pins), or
  rebuild so `apt-get upgrade` / `apk upgrade` pulls it; cite the vendor advisory.
- PHP 8.1 and older: no-fix-on-line. Offer an upgrade to 8.3 or 8.4 (needs `--major`
  approval, treated as high risk), a vendor LTS package, or the php.net source backport.
- Composer `require.php` / `config.platform.php`: leave unless they block the new version.
- Runtime diff: compare `php -v`, `php -m`, and `php -i` (ini values, OpenSSL/ICU/libxml)
  between images. Run `composer install` and tests inside the image.
- Evidence: `php -v` from the built image plus the SAPI binary version (`php-fpm -v`,
  `apache2ctl -M | grep php`, `frankenphp version`).

## Interim mitigations (reduce exposure, do not fix)
Offer these only as a stopgap, and say so. They are summarized in the advisory JSON
(`mitigations_not_fixes`). Never suggest `RLIMIT_AS` or `RLIMIT_DATA`; they trigger the
vulnerable path. Hiding diagnostics (`error_reporting`, `display_errors`, `@`) does not help.

## Rationalizations to Reject
| Shortcut | Required action |
| --- | --- |
| "`php -v` says 8.3.6, so it's vulnerable" (or "...says 8.3.36, so it's fixed"). | Distro builds need the vendor tracker; upstream builds need the binary in the image. |
| "Setting `require.php` to `^8.3.36` fixes it." | Composer constraints do not change the runtime. |
| "Mitigations are enough for now." | Only upgrading is a complete fix; mitigations are temporary. |
| "It's CLI-only, skip it." | Report it with lower priority; patch it if it shares the image. |

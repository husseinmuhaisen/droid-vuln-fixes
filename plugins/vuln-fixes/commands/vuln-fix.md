---
description: Inventory and patch a runtime vulnerability across repos (php, node, gitlab, or an advisory URL/CVE)
argument-hint: "<php|node|gitlab|advisory-url|CVE-ID> [repo ...]"
---

Start a vuln-fixes run for: $ARGUMENTS

Pick the skill from the first argument and load it with the Skill tool:
- `php` → `patching-php-runtimes`
- `node` or `nodejs` → `patching-node-runtimes`
- `gitlab` → `patching-gitlab-self-managed`
- anything else (an advisory URL, a CVE ID, another runtime) → `patching-runtime-cves`

If there is no first argument, ask which advisory to work on.

Treat the remaining arguments as the repos in scope (local paths or `owner/name`). If none
are given, ask whether to scan every repo you can access or a specific list. Then follow
the skill: register and inventory read-only, show the table, and stop at the approval gate.

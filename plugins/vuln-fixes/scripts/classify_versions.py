#!/usr/bin/env python3
"""Classify inventory records from scan_signals.py against an advisory JSON file.

Reads JSONL (file argument or stdin), keeps records whose runtime matches the
advisory, and adds `status` and `reason`. Output is JSONL, or a Markdown table
with --format table.

Statuses:
  fixed              exact version at or above the fixed version on its line
  vulnerable         exact version below the fixed version on its line
  no-fix-on-line     line is affected but has no fixed release (EOL/unsupported): upgrade needed
  floating-rebuild   floating tag/version on a fixed line: resolves to a fixed build only after
                     a --pull rebuild / cache refresh and redeploy
  vendor-check       distro package, managed runtime, Helm chart or operator: upstream version
                     strings are not evidence; check the vendor advisory or mapping
  signal-only        declares a constraint but does not choose the runtime (engines, composer)
  not-affected       line is older than the advisory's affected_from
  unknown            version missing, unparsable, an alias (lts, latest), or newer than the advisory

Usage:
  classify_versions.py --advisory ADVISORY.json [--format jsonl|table] [INVENTORY.jsonl]
"""

from __future__ import annotations

import argparse
import json
import re
import sys

VERSION = re.compile(r"(?<![\d.])v?(\d+)(?:\.(\d+|x))?(?:\.(\d+))?")
VENDOR_KINDS = {"distro-package", "managed-runtime", "managed-runtime-image", "helm-chart", "operator", "omnibus-config"}
SIGNAL_KINDS = {"engines-signal", "composer-signal"}


def parse(raw: str | None):
    """Return a tuple of ints (1-3 parts) or None. 'x' parts end the tuple."""
    if not raw:
        return None
    s = re.sub(r"^(nodejs|node|php)", "", raw.strip().lower()).lstrip("v=^~<> ")
    # Versions must lead the string; otherwise aliases like "lts-alpine3.20" would parse as 3.20.
    m = VERSION.match(s)
    if not m:
        return None
    parts = [int(m.group(1))]
    for g in (m.group(2), m.group(3)):
        if g is None or g == "x":
            break
        parts.append(int(g))
    return tuple(parts)


def line_of(parts, line_key):
    need = 1 if line_key == "major" else 2
    if parts is None or len(parts) < need:
        return None
    return parts[:need]


def to_tuple(s):
    return tuple(int(x) for x in s.split("."))


def classify(rec: dict, adv: dict) -> tuple[str, str]:
    kind = rec.get("kind", "")
    raw = rec.get("version")
    line_key = adv["line_key"]
    fixed = {to_tuple(k): to_tuple(v) for k, v in adv["fixed"].items()}
    lines_sorted = sorted(fixed)
    parts = parse(raw)
    line = line_of(parts, line_key)

    if kind in SIGNAL_KINDS:
        return "signal-only", "Declares a constraint; does not select the runtime that runs in production."

    if kind in {"helm-chart", "operator"}:
        return "vendor-check", (
            f"{kind} version {raw!r} is not a GitLab version; map it with the official chart/operator "
            "version mappings, then compare against the fixed GitLab versions."
        )

    if line is None:
        if kind in VENDOR_KINDS:
            return "vendor-check", f"{kind} without a parsable version; check the vendor advisory or deployed version."
        return "unknown", f"Cannot determine the release line from {raw!r}; resolve what it points to."

    affected_from = adv.get("affected_from")
    if affected_from and line < to_tuple(affected_from)[: len(line)]:
        return "not-affected", f"Line {'.'.join(map(str, line))} is older than affected_from {affected_from}."

    line_s = ".".join(map(str, line))
    if line in fixed:
        fixed_s = ".".join(map(str, fixed[line]))
        if kind in VENDOR_KINDS:
            return "vendor-check", (
                f"{kind} on line {line_s}; upstream fix is {fixed_s}, but vendor versions differ "
                "(backports, managed patching, chart mappings). Check the vendor advisory."
            )
        if len(parts) < 3:
            return "floating-rebuild", (
                f"Floats on line {line_s}; fixed upstream as {fixed_s}. Needs a --pull rebuild "
                "(or check-latest in CI) and redeploy; record the resolved version/digest."
            )
        if parts >= fixed[line]:
            return "fixed", f"{'.'.join(map(str, parts))} >= {fixed_s}."
        return "vulnerable", f"{'.'.join(map(str, parts))} < {fixed_s}; smallest fix on this line is {fixed_s}."

    if line < lines_sorted[-1]:
        note = adv.get("unpatched_lines_note", "No fixed release on this line.")
        return "no-fix-on-line", f"Line {line_s} is affected and has no fixed release. {note}"
    return "unknown", f"Line {line_s} is newer than every line in the advisory; verify against the vendor."


def table(rows):
    cols = ["repo", "file", "line", "kind", "context", "version", "pin", "status", "reason"]
    out = ["| " + " | ".join(cols) + " |", "|" + "---|" * len(cols)]
    for r in rows:
        out.append("| " + " | ".join(str(r.get(c, "")).replace("|", "\\|") for c in cols) + " |")
    return "\n".join(out)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--advisory", required=True)
    ap.add_argument("--format", choices=["jsonl", "table"], default="jsonl")
    ap.add_argument("inventory", nargs="?")
    args = ap.parse_args(argv)
    with open(args.advisory, encoding="utf-8") as f:
        adv = json.load(f)
    src = open(args.inventory, encoding="utf-8") if args.inventory else sys.stdin
    rows = []
    with src:
        for n, line in enumerate(src, 1):
            if not line.strip():
                continue
            try:
                rec = json.loads(line)
            except ValueError:
                print(f"classify_versions: skipping invalid JSON on line {n}", file=sys.stderr)
                continue
            if rec.get("runtime") != adv["runtime"]:
                continue
            rec["status"], rec["reason"] = classify(rec, adv)
            rec["advisory"] = adv["id"]
            rows.append(rec)
    if args.format == "table":
        print(table(rows))
    else:
        for r in rows:
            print(json.dumps(r, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())

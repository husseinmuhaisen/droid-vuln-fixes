#!/usr/bin/env python3
"""Read-only inventory of runtime version signals in one or more repositories.

Emits one JSON object per line (JSONL) on stdout. Never writes to the scanned trees.

Usage:
  scan_signals.py --runtime node|php|gitlab|all PATH [PATH ...]
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path

SKIP_DIRS = {
    ".git", "node_modules", "vendor", "dist", "build", ".venv", "venv",
    "__pycache__", ".terraform", ".next", ".cache", "target", "bower_components",
}
MAX_BYTES = 1_000_000

IMAGE_NAMES = {
    "node": {"node", "nodejs", "javascript-node", "typescript-node"},
    "php": {"php", "php-fpm", "php-apache", "frankenphp", "php-nginx"},
    "gitlab": {"gitlab-ee", "gitlab-ce"},
}

IMAGE_LINE = re.compile(
    r"""(?:^\s*FROM\s+(?:--platform=\S+\s+)?|\b(?:image|container)\b["']?\s*[:=]\s*["']?)"""
    r"""(?P<ref>[\w.\-/:@]+)""",
    re.IGNORECASE,
)
IMAGE_REF = re.compile(
    r"^(?P<path>(?:[\w.\-]+(?::\d+)?/)*)(?P<name>[\w.\-]+)"
    r"(?::(?P<tag>[\w.\-]+))?(?:@(?P<digest>sha256:[a-f0-9]{64}))?$"
)
FULL_VERSION = re.compile(r"^v?\d+\.\d+\.\d+")

PKG_INSTALL = re.compile(r"\b(apt-get|apt|apk|dnf|yum|microdnf|zypper|brew)\b.*\b(install|add)\b", re.IGNORECASE)
PKG_NAMES = {
    "node": re.compile(r"(?<![\w-])(nodejs|node)(?:=(?P<ver>[\w.:~+\-]+))?(?![\w-])"),
    "php": re.compile(
        r"(?<![\w-])(php[\d.]*(?:-fpm|-cli|-cgi)?|libapache2-mod-php[\d.]*|php\d\d(?:-fpm)?)"
        r"(?:=(?P<ver>[\w.:~+\-]+))?(?![\w-])"
    ),
    "gitlab": re.compile(r"(?<![\w-])(gitlab-ee|gitlab-ce)(?:[=-](?P<ver>\d[\w.:~+\-]*))?(?![\w-])"),
}
NODESOURCE = re.compile(r"(?:deb\.nodesource\.com|rpm\.nodesource\.com)/setup_(?P<ver>\d+)\.x|node_(?P<ver2>\d+)\.x")
SOURCE_BUILD = {
    "node": re.compile(r"node-v(?P<ver>\d+\.\d+\.\d+)[\w.\-]*\.tar\.(?:gz|xz)"),
    "php": re.compile(r"php-(?P<ver>\d+\.\d+\.\d+)\.tar\.(?:gz|bz2|xz)"),
}
CI_VERSION = {
    "node": re.compile(r"\bnode-version\s*:\s*['\"]?(?P<ver>[\w.*/\-]+)"),
    "php": re.compile(r"\bphp-version\s*:\s*['\"]?(?P<ver>[\w.*/\-]+)"),
}
MANAGED_RUNTIME = re.compile(
    r"""(?:\bruntime\b["']?\s*[:=]\s*["']?nodejs(?P<a>\d+)\.x)|(?:Runtime\.NODEJS_(?P<b>\d+)_X)""",
)
CONFIG_MGMT = {
    "node": re.compile(r"\b(?:nodejs_version|node_version|nodejs_major_version)\s*[:=]\s*['\"]?(?P<ver>[\w.\-]+)"),
    "php": re.compile(r"\b(?:php_version|php_default_version)\s*[:=]\s*['\"]?(?P<ver>[\w.\-]+)"),
    "gitlab": re.compile(r"\b(?:gitlab_version|gitlab_ee_version|gitlab_package_version)\s*[:=]\s*['\"]?(?P<ver>[\w.\-]+)"),
}
TOOL_VERSIONS = re.compile(r"^\s*(?P<tool>nodejs|node|php)\s+(?P<ver>\S+)")
MISE = re.compile(r"^\s*(?P<tool>node|nodejs|php)\s*=\s*['\"](?P<ver>[^'\"]+)['\"]")
HELM_CHART = re.compile(r"""\bchart\b["']?\s*[:=]\s*["']?(?:[\w.\-]+/)?gitlab["']?\s*$|^\s*-?\s*name:\s*gitlab\s*$""")
HELM_VERSION = re.compile(r"""\b(?:version|targetRevision)\b["']?\s*[:=]\s*["']?(?P<ver>v?\d+\.\d+(?:\.\d+)?)""")
OPERATOR = re.compile(r"gitlab-operator|apps\.gitlab\.com/v\d")
OMNIBUS_CONFIG = re.compile(r"^\s*external_url\s+['\"]")


def context_for(rel: str) -> str:
    parts = rel.replace("\\", "/").split("/")
    name = parts[-1].lower()
    if any(p in {".github", ".circleci", ".buildkite", ".gitlab"} for p in parts) or name in {
        ".gitlab-ci.yml", "jenkinsfile", "azure-pipelines.yml", "bitbucket-pipelines.yml", ".travis.yml",
    }:
        return "ci"
    if name.startswith(("dockerfile", "containerfile")) or name.endswith(".dockerfile"):
        return "image"
    if name.endswith((".tf", ".hcl")) or name in {"chart.yaml", "values.yaml"} or "helm" in parts or "charts" in parts:
        return "iac"
    if name.startswith(("docker-compose", "compose")):
        return "compose"
    return "config"


def pin_for(version: str | None, digest: str | None = None) -> str:
    if digest:
        return "digest"
    if not version:
        return "none"
    return "exact" if FULL_VERSION.match(version) else "floating"


class Scanner:
    def __init__(self, runtimes: set[str]):
        self.runtimes = runtimes

    def scan(self, root: Path):
        root = root.resolve()
        for dirpath, dirnames, filenames in os.walk(root):
            dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
            for fn in filenames:
                path = Path(dirpath) / fn
                try:
                    if path.is_symlink() or path.stat().st_size > MAX_BYTES:
                        continue
                    text = path.read_text(encoding="utf-8", errors="strict")
                except (OSError, UnicodeDecodeError):
                    continue
                rel = str(path.relative_to(root))
                yield from self.scan_file(root, rel, fn, text)

    def rec(self, root, rel, line_no, runtime, kind, signal, version, pin=None, **extra):
        r = {
            "repo": str(root), "file": rel, "line": line_no, "runtime": runtime, "kind": kind,
            "signal": signal.strip()[:200], "version": version,
            "pin": pin or pin_for(version), "context": context_for(rel),
        }
        r.update(extra)
        return r

    def scan_file(self, root, rel, fn, text):
        lower = fn.lower()
        lines = text.splitlines()

        if lower in {".nvmrc", ".node-version"} and "node" in self.runtimes and lines:
            v = lines[0].strip()
            if v:
                yield self.rec(root, rel, 1, "node", "version-file", v, v)
            return

        if lower in {"package.json", "composer.json"}:
            yield from self.scan_manifest(root, rel, lower, text)
            return

        for i, line in enumerate(lines, 1):
            if lower == ".tool-versions" or lower.endswith("mise.toml"):
                m = (TOOL_VERSIONS if lower == ".tool-versions" else MISE).match(line)
                if m:
                    rt = "node" if m["tool"] in {"node", "nodejs"} else "php"
                    if rt in self.runtimes:
                        yield self.rec(root, rel, i, rt, "version-file", line, m["ver"])
                continue

            for m in IMAGE_LINE.finditer(line):
                im = IMAGE_REF.match(m["ref"].rstrip("'\","))
                if not im:
                    continue
                name = im["name"].lower()
                for rt in self.runtimes:
                    if name in IMAGE_NAMES[rt]:
                        managed = "lambda" in (im["path"] or "")
                        yield self.rec(
                            root, rel, i, rt, "managed-runtime-image" if managed else "image", line,
                            im["tag"], pin_for(im["tag"], im["digest"]),
                            image=m["ref"], digest=im["digest"],
                        )

            if PKG_INSTALL.search(line):
                for rt in self.runtimes:
                    for pm in PKG_NAMES[rt].finditer(line.split("install", 1)[-1] if "install" in line else line):
                        if rt == "node" and pm.group(1) == "node" and "apk" not in line:
                            continue
                        yield self.rec(root, rel, i, rt, "distro-package", line, pm["ver"])

            if "node" in self.runtimes:
                ns = NODESOURCE.search(line)
                if ns:
                    yield self.rec(root, rel, i, "node", "distro-package", line, ns["ver"] or ns["ver2"],
                                   repo_source="nodesource")
                mr = MANAGED_RUNTIME.search(line)
                if mr:
                    yield self.rec(root, rel, i, "node", "managed-runtime", line, mr["a"] or mr["b"], "floating")

            for rt in self.runtimes & set(SOURCE_BUILD):
                sb = SOURCE_BUILD[rt].search(line)
                if sb:
                    yield self.rec(root, rel, i, rt, "source-build", line, sb["ver"])

            for rt in self.runtimes & set(CI_VERSION):
                cm = CI_VERSION[rt].search(line)
                if cm:
                    yield self.rec(root, rel, i, rt, "ci-setup", line, cm["ver"])

            for rt in self.runtimes:
                cm = CONFIG_MGMT[rt].search(line)
                if cm:
                    yield self.rec(root, rel, i, rt, "config-management", line, cm["ver"])

            if "gitlab" in self.runtimes:
                if HELM_CHART.search(line) and (lower.endswith((".yaml", ".yml", ".tf", ".hcl")) or lower == "chart.yaml"):
                    # Look after the chart reference first so a parent chart's own version is not picked up.
                    window = lines[i: i + 5] + lines[max(0, i - 6): i - 1][::-1]
                    ver = next((hv["ver"] for w in window for hv in [HELM_VERSION.search(w)] if hv), None)
                    if lower == "chart.yaml" and "name: gitlab" in line and not re.search(r"dependencies", text):
                        continue
                    yield self.rec(root, rel, i, "gitlab", "helm-chart", line, ver)
                if OPERATOR.search(line):
                    yield self.rec(root, rel, i, "gitlab", "operator", line, None)
                if lower == "gitlab.rb" and OMNIBUS_CONFIG.search(line):
                    yield self.rec(root, rel, i, "gitlab", "omnibus-config", line, None)

    def scan_manifest(self, root, rel, lower, text):
        try:
            data = json.loads(text)
        except ValueError:
            return
        if not isinstance(data, dict):
            return
        lines = text.splitlines()

        def line_of(key):
            for i, ln in enumerate(lines, 1):
                if f'"{key}"' in ln:
                    return i
            return 1

        if lower == "package.json" and "node" in self.runtimes:
            eng = (data.get("engines") or {}).get("node") if isinstance(data.get("engines"), dict) else None
            if isinstance(eng, str):
                yield self.rec(root, rel, line_of("engines"), "node", "engines-signal", f"engines.node {eng}", eng, "floating")
            volta = (data.get("volta") or {}).get("node") if isinstance(data.get("volta"), dict) else None
            if isinstance(volta, str):
                yield self.rec(root, rel, line_of("volta"), "node", "version-file", f"volta.node {volta}", volta)
        if lower == "composer.json" and "php" in self.runtimes:
            req = (data.get("require") or {}).get("php") if isinstance(data.get("require"), dict) else None
            if isinstance(req, str):
                yield self.rec(root, rel, line_of("require"), "php", "composer-signal", f"require.php {req}", req, "floating")
            plat = ((data.get("config") or {}).get("platform") or {}).get("php") if isinstance(data.get("config"), dict) else None
            if isinstance(plat, str):
                yield self.rec(root, rel, line_of("platform"), "php", "composer-signal", f"config.platform.php {plat}", plat)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--runtime", choices=["node", "php", "gitlab", "all"], required=True)
    ap.add_argument("paths", nargs="+", type=Path)
    args = ap.parse_args(argv)
    runtimes = {"node", "php", "gitlab"} if args.runtime == "all" else {args.runtime}
    scanner = Scanner(runtimes)
    missing = 0
    for p in args.paths:
        if not p.is_dir():
            print(f"scan_signals: not a directory: {p}", file=sys.stderr)
            missing += 1
            continue
        for r in scanner.scan(p):
            print(json.dumps(r, sort_keys=True))
    return 1 if missing else 0


if __name__ == "__main__":
    sys.exit(main())

import json
import subprocess
import sys
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
PLUGIN = HERE.parent
SCRIPTS = PLUGIN / "scripts"
ADV = PLUGIN / "references" / "advisories"
FIXTURE = HERE / "fixtures" / "sample-repo"

sys.path.insert(0, str(SCRIPTS))
import classify_versions as cv  # noqa: E402


def load(name):
    return json.loads((ADV / name).read_text())


NODE, PHP, GITLAB = load("node-2026-10.json"), load("php-2026-10.json"), load("gitlab-2026-10.json")


def status(adv, version, kind="image"):
    return cv.classify({"version": version, "kind": kind}, adv)[0]


class ParseTests(unittest.TestCase):
    def test_parse(self):
        self.assertEqual(cv.parse("22.23.4-alpine"), (22, 23, 4))
        self.assertEqual(cv.parse("v20.11.1"), (20, 11, 1))
        self.assertEqual(cv.parse("nodejs22.x"), (22,))
        self.assertEqual(cv.parse("8.3-fpm"), (8, 3))
        self.assertEqual(cv.parse("19.5.1-ee.0"), (19, 5, 1))
        for alias in ("lts/*", "latest", "lts-alpine3.20", "alpine", None, ""):
            self.assertIsNone(cv.parse(alias), alias)


class NodeTests(unittest.TestCase):
    def test_lines(self):
        self.assertEqual(status(NODE, "22.23.3"), "vulnerable")
        self.assertEqual(status(NODE, "22.23.4"), "fixed")
        self.assertEqual(status(NODE, "24.22.1-slim"), "fixed")
        self.assertEqual(status(NODE, "26.12.0"), "vulnerable")
        self.assertEqual(status(NODE, "22"), "floating-rebuild")
        self.assertEqual(status(NODE, "20.19.0"), "no-fix-on-line")
        self.assertEqual(status(NODE, "25.1.0"), "no-fix-on-line")
        self.assertEqual(status(NODE, "28.0.0"), "unknown")
        self.assertEqual(status(NODE, "lts/*"), "unknown")

    def test_vendor_and_signals(self):
        self.assertEqual(status(NODE, "22", "managed-runtime"), "vendor-check")
        self.assertEqual(status(NODE, "20", "managed-runtime"), "no-fix-on-line")
        self.assertEqual(status(NODE, ">=20", "engines-signal"), "signal-only")


class PhpTests(unittest.TestCase):
    def test_lines(self):
        self.assertEqual(status(PHP, "8.3.30-fpm"), "vulnerable")
        self.assertEqual(status(PHP, "8.3.36-apache"), "fixed")
        self.assertEqual(status(PHP, "8.5"), "floating-rebuild")
        self.assertEqual(status(PHP, "8.1.30"), "no-fix-on-line")
        self.assertEqual(status(PHP, "7.4.33"), "no-fix-on-line")

    def test_distro_backports_are_not_judged_by_version_string(self):
        self.assertEqual(status(PHP, "8.3.6-0ubuntu0.24.04.13", "distro-package"), "vendor-check")
        self.assertEqual(status(PHP, "8.1.2-1ubuntu2.28", "distro-package"), "no-fix-on-line")
        self.assertEqual(status(PHP, "^8.2", "composer-signal"), "signal-only")


class GitlabTests(unittest.TestCase):
    def test_lines(self):
        self.assertEqual(status(GITLAB, "19.4.2-ee.0"), "vulnerable")
        self.assertEqual(status(GITLAB, "19.4.3-ee.0"), "fixed")
        self.assertEqual(status(GITLAB, "18.11.12-ce.0"), "vulnerable")
        self.assertEqual(status(GITLAB, "18.10.5-ee.0"), "no-fix-on-line")
        self.assertEqual(status(GITLAB, "6.9.0"), "not-affected")
        self.assertEqual(status(GITLAB, "9.5.1", "helm-chart"), "vendor-check")


class ScannerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        out = subprocess.run(
            [sys.executable, str(SCRIPTS / "scan_signals.py"), "--runtime", "all", str(FIXTURE)],
            check=True, capture_output=True, text=True,
        ).stdout
        cls.recs = [json.loads(line) for line in out.splitlines() if line.strip()]

    def find(self, **kw):
        return [r for r in self.recs if all(r.get(k) == v for k, v in kw.items())]

    def test_images(self):
        self.assertTrue(self.find(runtime="node", kind="image", version="20.11.1-alpine", pin="exact", context="image"))
        self.assertTrue(self.find(runtime="php", kind="image", version="8.3.30-fpm-bookworm"))
        self.assertTrue(self.find(runtime="node", kind="image", version="24.22.1-bookworm", context="ci"))
        self.assertTrue(self.find(runtime="gitlab", kind="image", version="19.4.2-ee.0"))
        self.assertTrue(self.find(runtime="node", kind="image", version="lts-alpine3.20", pin="floating"))
        self.assertFalse([r for r in self.recs if "gitlab-runner" in r["signal"]], "gitlab-runner is out of scope")

    def test_other_signals(self):
        self.assertTrue(self.find(runtime="node", kind="version-file", file=".nvmrc", version="22.20.0"))
        self.assertTrue(self.find(runtime="node", kind="ci-setup", version="22"))
        self.assertTrue(self.find(runtime="php", kind="ci-setup", version="8.4"))
        self.assertTrue(self.find(runtime="node", kind="managed-runtime", version="20"))
        self.assertTrue(self.find(runtime="node", kind="distro-package", repo_source="nodesource", version="22"))
        self.assertTrue(self.find(runtime="php", kind="distro-package"))
        self.assertTrue(self.find(runtime="gitlab", kind="helm-chart", version="9.5.1"))
        self.assertTrue(self.find(runtime="node", kind="engines-signal"))
        self.assertTrue(self.find(runtime="node", kind="version-file", version="22.23.4"))
        self.assertEqual(len(self.find(runtime="php", kind="composer-signal")), 2)

    def test_pipeline_table(self):
        scan = subprocess.run(
            [sys.executable, str(SCRIPTS / "scan_signals.py"), "--runtime", "node", str(FIXTURE)],
            check=True, capture_output=True, text=True,
        ).stdout
        out = subprocess.run(
            [sys.executable, str(SCRIPTS / "classify_versions.py"), "--advisory", str(ADV / "node-2026-10.json"),
             "--format", "table"],
            input=scan, check=True, capture_output=True, text=True,
        ).stdout
        self.assertIn("no-fix-on-line", out)
        self.assertIn("vulnerable", out)
        self.assertIn("| repo |", out)


class AdvisorySchemaTests(unittest.TestCase):
    def test_required_fields(self):
        schema = json.loads((PLUGIN / "references" / "advisory.schema.json").read_text())
        for adv in (NODE, PHP, GITLAB):
            for key in schema["required"]:
                self.assertIn(key, adv)
            for line, ver in adv["fixed"].items():
                self.assertTrue(ver.startswith(line + "."), (line, ver))


if __name__ == "__main__":
    unittest.main()

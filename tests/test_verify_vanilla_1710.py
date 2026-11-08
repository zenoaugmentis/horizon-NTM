"""Tests for tools/verify_vanilla_1710.py on a fake install (no game files needed)."""
import hashlib
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("verify", ROOT / "tools" / "verify_vanilla_1710.py")
verify = importlib.util.module_from_spec(spec)
spec.loader.exec_module(verify)

CLIENT = b"fake client jar"
SERVER = b"fake server jar"
FORGE = b"fake forge jar"


def sha(data: bytes) -> str:
    return hashlib.sha1(data).hexdigest()


class VerifyTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.mc = Path(self.tmp.name) / ".minecraft"
        ver = self.mc / "versions" / "1.7.10"
        ver.mkdir(parents=True)
        (ver / "1.7.10.jar").write_bytes(CLIENT)
        meta = {"downloads": {"client": {"sha1": sha(CLIENT)}, "server": {"sha1": sha(SERVER)}},
                "javaVersion": {"majorVersion": 8}}
        (ver / "1.7.10.json").write_text(json.dumps(meta))
        self.server = Path(self.tmp.name) / "server.jar"
        self.server.write_bytes(SERVER)
        self.patch = mock.patch.object(verify, "CLIENT_SHA1", sha(CLIENT))
        self.patch.start()

    def tearDown(self):
        self.patch.stop()
        self.tmp.cleanup()

    def run_check(self, *extra):
        out = Path(self.tmp.name) / "report.json"
        with mock.patch("builtins.print"):
            code = verify.main(["--minecraft-dir", str(self.mc), "--report", str(out), *extra])
        return code, json.loads(out.read_text())

    def statuses(self, report):
        return {c["check"]: c["status"] for c in report["checks"]}

    def add_forge(self, build):
        d = self.mc / "libraries" / "net" / "minecraftforge" / "forge" / f"1.7.10-{build}-1.7.10"
        d.mkdir(parents=True)
        (d / f"forge-1.7.10-{build}-1.7.10.jar").write_bytes(FORGE)

    def test_matching_install_passes(self):
        self.add_forge("10.13.4.1614")
        code, report = self.run_check("--server-jar", str(self.server))
        s = self.statuses(report)
        self.assertEqual(code, 0)
        self.assertEqual((s["client jar"], s["server jar"], s["forge"]), ("OK", "OK", "OK"))
        self.assertEqual(report["forge"][0]["sha1"], sha(FORGE))
        self.assertEqual(report["java_version"], {"majorVersion": 8})

    def test_modified_client_fails(self):
        (self.mc / "versions" / "1.7.10" / "1.7.10.jar").write_bytes(b"patched")
        code, report = self.run_check()
        self.assertEqual(code, 1)
        self.assertEqual(self.statuses(report)["client jar"], "FAIL")

    def test_wrong_server_fails(self):
        self.server.write_bytes(b"other server")
        code, report = self.run_check("--server-jar", str(self.server))
        self.assertEqual(code, 1)
        self.assertEqual(self.statuses(report)["server jar"], "FAIL")

    def test_missing_forge_is_not_a_failure(self):
        code, report = self.run_check()
        self.assertEqual(code, 0)
        self.assertEqual(self.statuses(report)["forge"], "MISSING")

    def test_other_forge_build_warns(self):
        self.add_forge("10.13.4.1558")
        code, report = self.run_check()
        self.assertEqual(code, 0)
        self.assertEqual(self.statuses(report)["forge"], "WARN")
        self.assertEqual(report["forge"][0]["note"], "recommended build")

    def test_prism_layout_with_explicit_client_jar(self):
        prism = Path(self.tmp.name) / "minecraft-1.7.10-client.jar"
        prism.write_bytes(CLIENT)
        with mock.patch("builtins.print"):
            code = verify.main(["--minecraft-dir", str(Path(self.tmp.name) / "none"),
                                "--client-jar", str(prism)])
        self.assertEqual(code, 0)

    def test_report_holds_no_file_contents(self):
        code, report = self.run_check()
        text = json.dumps(report)
        self.assertNotIn(CLIENT.decode(), text)

    def test_reference_hash_constant_is_the_official_one(self):
        self.patch.stop()
        try:
            self.assertEqual(verify.CLIENT_SHA1, "e80d9b3bf5085002218d4be59e668bac718abbc6")
        finally:
            self.patch.start()


if __name__ == "__main__":
    unittest.main()

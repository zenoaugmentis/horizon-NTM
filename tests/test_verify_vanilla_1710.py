"""Tests for tools/verify_vanilla_1710.py on a fake install (no real jars needed).

Run: python -m unittest discover -s tests -p "test_verify_vanilla_1710.py" -v
"""
import hashlib
import importlib.util
import json
import re
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("verify_vanilla_1710", ROOT / "tools" / "verify_vanilla_1710.py")
vv = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = vv
spec.loader.exec_module(vv)


def sha1(data: bytes) -> str:
    return hashlib.sha1(data).hexdigest()


class FakeInstall(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.game = self.root / "game"
        self.files = {
            "client_jar": b"fake client",
            "version_json": b'{"id": "1.7.10"}',
            "asset_index": b'{"objects": {}}',
        }
        for name, data in self.files.items():
            path = self.game / vv.GAME_DIR_FILES[name]
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
        self.server = self.root / "minecraft_server.1.7.10.jar"
        self.server.write_bytes(b"fake server")
        self.ref = {n: vv.Ref(sha1(d), len(d)) for n, d in self.files.items()}
        self.ref["server_jar"] = vv.Ref(sha1(b"fake server"), 11)
        self.ref["forge_universal"] = vv.Ref("0" * 40)

    def tearDown(self):
        self.tmp.cleanup()

    def test_matching_install_passes(self):
        results = vv.collect(self.game, self.server, None, self.ref)
        statuses = {r.component: r.status for r in results}
        self.assertEqual(statuses["client_jar"], vv.OK)
        self.assertEqual(statuses["server_jar"], vv.OK)
        self.assertEqual(statuses["forge_universal"], vv.SKIPPED)
        self.assertTrue(vv.passed(results))

    def test_modified_client_is_mismatch(self):
        (self.game / vv.GAME_DIR_FILES["client_jar"]).write_bytes(b"patched client")
        results = vv.collect(self.game, None, None, self.ref)
        self.assertEqual(results[0].status, vv.MISMATCH)
        self.assertFalse(vv.passed(results))

    def test_size_mismatch_with_same_hash_is_reported(self):
        ref = dict(self.ref, client_jar=vv.Ref(self.ref["client_jar"].sha1, 1))
        r = vv.check("client_jar", self.game / vv.GAME_DIR_FILES["client_jar"], ref)
        self.assertEqual(r.status, vv.MISMATCH)
        self.assertIn("size", r.note)

    def test_missing_file_fails(self):
        (self.game / vv.GAME_DIR_FILES["asset_index"]).unlink()
        results = vv.collect(self.game, None, None, self.ref)
        self.assertEqual({r.component: r.status for r in results}["asset_index"], vv.MISSING)
        self.assertFalse(vv.passed(results))

    def test_nothing_checked_is_not_a_pass(self):
        self.assertFalse(vv.passed(vv.collect(None, None, None, self.ref)))

    def test_report_has_hashes_but_no_paths(self):
        report = self.root / "out" / "report.json"
        vv.REFERENCE, saved = self.ref, vv.REFERENCE
        try:
            with redirect_stdout(StringIO()):
                code = vv.main(["--game-dir", str(self.game), "--report", str(report)])
        finally:
            vv.REFERENCE = saved
        self.assertEqual(code, 0)
        text = report.read_text(encoding="utf-8")
        self.assertNotIn(str(self.root), text)
        self.assertNotIn(self.root.as_posix(), text)
        data = json.loads(text)
        self.assertTrue(data["ok"])
        self.assertEqual(data["results"][0]["sha1"], sha1(self.files["client_jar"]))


class ReferenceValues(unittest.TestCase):
    def test_reference_hashes_are_sha1(self):
        for name, ref in vv.REFERENCE.items():
            self.assertRegex(ref.sha1, r"^[0-9a-f]{40}$", name)

    def test_reference_matches_spec(self):
        spec_text = (ROOT / "docs" / "specs" / "versions.md").read_text(encoding="utf-8")
        for name, ref in vv.REFERENCE.items():
            self.assertIn(ref.sha1, spec_text, f"{name} hash missing from versions.md")
        self.assertIsNotNone(re.search(r"Minecraft Forge \| `10\.13\.4\.1614`", spec_text))


if __name__ == "__main__":
    unittest.main()

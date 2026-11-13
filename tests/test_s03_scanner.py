"""Checks of the new read-only runner on synthetic regions, not game saves."""
import gzip
import json
from pathlib import Path
import struct
import subprocess
import sys
import tempfile
import unittest
import zlib

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from s03_codec import encode
from check_s03 import inspect_region


def fixture(compression=2, x=-1, z=-1):
    section = {"Y": (1, 0), "Blocks": (7, bytes(4096)),
               "Data": (7, bytes(2048)), "BlockLight": (7, bytes(2048)),
               "SkyLight": (7, bytes(2048))}
    raw = encode("", {"Level": (10, {
        "xPos": (3, x), "zPos": (3, z),
        "Sections": (9, (10, [section])),
        "HeightMap": (11, [0] * 256), "Biomes": (7, bytes(256))})})
    packed = zlib.compress(raw) if compression == 2 else gzip.compress(raw, mtime=0)
    record = struct.pack(">IB", len(packed) + 1, compression) + packed
    sectors = (len(record) + 4095) // 4096
    header = bytearray(8192)
    struct.pack_into(">I", header, 1023 * 4, (2 << 8) | sectors)
    return bytes(header) + record + bytes(sectors * 4096 - len(record))


class ScannerTests(unittest.TestCase):
    def test_gzip_and_zlib_negative_coordinates_and_read_only(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "r.-1.-1.mca"
            for compression in (1, 2):
                original = fixture(compression)
                path.write_bytes(original)
                report = inspect_region(path)
                self.assertEqual(report["errors"], [])
                self.assertEqual(report["pass_chunks"], 1)
                self.assertEqual(report["sky_sections"], {"all_zero": 1})
                self.assertEqual(path.read_bytes(), original)

    def test_coordinate_mismatch_is_an_error(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "r.-1.-1.mca"
            path.write_bytes(fixture(x=0))
            report = inspect_region(path)
            self.assertEqual(report["pass_chunks"], 0)
            self.assertIn("coordinate mismatch", report["errors"][0])

    def test_overlapping_allocations_are_an_error(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "r.-1.-1.mca"
            data = bytearray(fixture())
            data[0:4] = data[1023 * 4:1024 * 4]
            path.write_bytes(data)
            report = inspect_region(path)
            self.assertTrue(any("Overlapping" in e for e in report["errors"]))

    def test_empty_input_directory_is_not_success(self):
        with tempfile.TemporaryDirectory() as temp:
            script = Path(__file__).resolve().parents[1] / "tools/check_s03.py"
            result = subprocess.run([sys.executable, str(script), temp],
                                    capture_output=True, text=True)
            self.assertEqual(result.returncode, 2)
            self.assertIn("error", json.loads(result.stdout))


if __name__ == "__main__":
    unittest.main(verbosity=2)

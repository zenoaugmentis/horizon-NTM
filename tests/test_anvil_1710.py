"""Round-trip fixture and vectors for the S03 chunk spec. W04/W05 must reproduce them in Rust.

Run: python -m unittest discover -s tests -p "test_anvil_1710.py" -v
"""
import gzip
import hashlib
import importlib.util
import struct
import sys
import tempfile
import unittest
import zlib
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("anvil_1710", ROOT / "tools" / "anvil_1710.py")
av = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = av
spec.loader.exec_module(av)
LegacyBlock, LegacyChunk, Tag = av.LegacyBlock, av.LegacyChunk, av.Tag

# Changes only when the fixture or the NBT encoding changes on purpose.
FIXTURE_SHA256 = "8406f4fb63d3f96c21f3fbfe0c15b97c21ae909e8925c80017d08d0160866c06"


def fixture_chunk() -> LegacyChunk:
    _, root = av.nbt_decode(av.fixture_nbt())
    return LegacyChunk(root)


def region_with(nbt: bytes, compression: int = av.ZLIB) -> bytes:
    return av.write_region({av.chunk_index(*av.FIXTURE_POS): av.ChunkBlob(compression, nbt, 1700000000)})


class Nbt(unittest.TestCase):
    def test_fixture_hash_is_pinned(self):
        self.assertEqual(hashlib.sha256(av.fixture_nbt()).hexdigest(), FIXTURE_SHA256)

    def test_decode_encode_is_byte_exact(self):
        data = av.fixture_nbt()
        name, root = av.nbt_decode(data)
        self.assertEqual(av.nbt_encode(name, root), data)

    def test_modified_utf8(self):
        self.assertEqual(av.mutf8_encode("\u0000"), b"\xc0\x80")
        self.assertEqual(av.mutf8_encode("\u0001ntm:ore"), b"\x01ntm:ore")  # FML block key, S02
        self.assertEqual(av.mutf8_encode("\U0001F600"), b"\xed\xa0\xbd\xed\xb8\x80")  # two 3-byte surrogates
        for s in ["", "abc", "\u0000", "мир", "\U0001F600", "\u0001x\u0002"]:
            self.assertEqual(av.mutf8_decode(av.mutf8_encode(s)), s)
        with self.assertRaises(av.NbtError):
            av.mutf8_decode(b"\x00")  # raw NUL is not modified UTF-8

    def test_long_array_is_rejected(self):
        data = bytes([av.COMPOUND]) + b"\x00\x00" + bytes([12]) + b"\x00\x01L" + struct.pack(">i", 0) + b"\x00"
        with self.assertRaises(av.NbtError):
            av.nbt_decode(data)
        with self.assertRaises(av.NbtError):
            av.nbt_encode("", Tag(av.COMPOUND, {"L": Tag(12, [])}))

    def test_empty_list_type_and_key_order_survive(self):
        ch = fixture_chunk()
        self.assertEqual(ch.level["Entities"].value, (av.END, []))
        self.assertEqual(list(ch.level.value)[:3], ["xPos", "zPos", "LastUpdate"])
        self.assertEqual(ch.level["ntm:Radiation"]["note"].value, "nul\u0000 and \U0001F600")


class Region(unittest.TestCase):
    def test_round_trip_gzip_and_zlib(self):
        for comp in (av.GZIP, av.ZLIB):
            region = region_with(av.fixture_nbt(), comp)
            blobs = av.read_region(region)
            self.assertEqual(list(blobs), [av.chunk_index(3, -2)])
            blob = blobs[av.chunk_index(3, -2)]
            self.assertEqual((blob.compression, blob.nbt, blob.timestamp), (comp, av.fixture_nbt(), 1700000000))
            self.assertEqual(av.round_trip(region), [])

    def test_layout(self):
        region = region_with(av.fixture_nbt())
        self.assertEqual(len(region) % av.SECTOR, 0)
        idx = av.chunk_index(3, -2)
        self.assertEqual(idx, 3 + 30 * 32)
        loc = struct.unpack_from(">I", region, idx * 4)[0]
        self.assertEqual(loc >> 8, 2)
        length, comp = struct.unpack_from(">IB", region, 2 * av.SECTOR)
        self.assertEqual(comp, av.ZLIB)
        self.assertEqual(zlib.decompress(region[2 * av.SECTOR + 5: 2 * av.SECTOR + 4 + length]), av.fixture_nbt())
        self.assertEqual(av.region_file_name(3, -2), "r.0.-1.mca")
        self.assertEqual(av.region_file_name(-33, 32), "r.-2.1.mca")

    def test_modern_compressions_are_rejected(self):
        region = bytearray(region_with(av.fixture_nbt()))
        for comp in (3, 4, 128 | av.ZLIB):
            region[2 * av.SECTOR + 4] = comp
            with self.assertRaises(av.RegionError):
                av.read_region(bytes(region))
        with self.assertRaises(av.RegionError):
            av.write_region({0: av.ChunkBlob(3, b"")})

    def test_bad_location_is_rejected(self):
        region = bytearray(region_with(av.fixture_nbt()))
        struct.pack_into(">I", region, av.chunk_index(3, -2) * 4, 999 << 8 | 1)
        with self.assertRaises(av.RegionError):
            av.read_region(bytes(region))


class ChunkValues(unittest.TestCase):
    def test_known_points(self):
        ch = fixture_chunk()
        self.assertEqual(ch.pos, (3, -2))
        self.assertEqual(ch.section_ys(), [0, 1, 4])
        self.assertEqual(ch.block(9, 0, 0), LegacyBlock(7))
        for m in range(16):
            self.assertEqual(ch.block(m, 1, 1), LegacyBlock(35, m))
            self.assertEqual((ch.block_light(m, 17, 3), ch.sky_light(m, 17, 3)), (m, 15 - m))
        self.assertEqual(ch.block(5, 70, 9), LegacyBlock(1204, 2))
        self.assertEqual(ch.block(5, 200, 9), LegacyBlock(0))  # missing section = air
        self.assertEqual((ch.block_light(5, 200, 9), ch.sky_light(5, 200, 9)), (0, 15))
        self.assertEqual(ch.biome(0, 0), 255)
        self.assertEqual(ch.biome(1, 0), 1)
        self.assertEqual(ch.height(2, 1), 17)
        self.assertEqual(ch.tile_ticks(), [{"i": 8, "x": 48, "y": 64, "z": -32, "t": 5, "p": 0}])

    def test_section_index_order_is_y_z_x(self):
        ch = fixture_chunk()
        blocks = ch._sections[0]["Blocks"].value
        self.assertEqual(blocks[1 << 8 | 1 << 4 | 14], 35)  # y=1, z=1, x=14
        self.assertEqual(blocks[0 << 8 | 0 << 4 | 15], 7)  # y=0, z=0, x=15


class Edits(unittest.TestCase):
    def test_add_appears_only_when_needed_and_stays(self):
        ch = fixture_chunk()
        self.assertIsNone(ch._sections[0].get("Add"))
        ch.set_block(0, 2, 0, LegacyBlock(255, 1))
        self.assertIsNone(ch._sections[0].get("Add"))
        ch.set_block(0, 2, 0, LegacyBlock(256, 1))
        self.assertEqual(list(ch._sections[0].value)[:3], ["Y", "Blocks", "Add"])
        ch.set_block(0, 2, 0, LegacyBlock(1))
        self.assertIsNotNone(ch._sections[0].get("Add"))  # kept once present
        self.assertEqual(ch.block(0, 2, 0), LegacyBlock(1))

    def test_new_section_defaults(self):
        ch = fixture_chunk()
        ch.set_block(3, 250, 3, LegacyBlock(0))
        self.assertNotIn(15, ch.section_ys())  # air never creates a section
        ch.set_block(3, 250, 3, LegacyBlock(1))
        self.assertIn(15, ch.section_ys())
        self.assertEqual((ch.block_light(0, 240, 0), ch.sky_light(0, 240, 0)), (0, 15))
        nether = LegacyChunk(av.nbt_decode(av.fixture_nbt())[1], has_sky=False)
        nether.set_block(3, 250, 3, LegacyBlock(87))
        self.assertEqual(nether.sky_light(0, 240, 0), 0)

    def test_emptied_section_is_kept_and_edits_round_trip(self):
        ch = fixture_chunk()
        ch.set_block(5, 70, 9, LegacyBlock(0))
        self.assertIn(4, ch.section_ys())
        data = av.nbt_encode("", ch.root)
        again = LegacyChunk(av.nbt_decode(data)[1])
        self.assertEqual(again.block(5, 70, 9), LegacyBlock(0))
        self.assertEqual(av.nbt_encode("", again.root), data)

    def test_edits_do_not_touch_light_heightmap_or_ticks(self):
        ch = fixture_chunk()
        before = (ch.level["HeightMap"].value[:], ch.tile_ticks(), bytes(ch._sections[1]["SkyLight"].value))
        ch.set_block(0, 20, 0, LegacyBlock(1))
        self.assertEqual((ch.level["HeightMap"].value, ch.tile_ticks(), bytes(ch._sections[1]["SkyLight"].value)), before)


class Rejections(unittest.TestCase):
    def chunk_with(self, mutate):
        _, root = av.nbt_decode(av.fixture_nbt())
        mutate(root)
        return lambda: LegacyChunk(root)

    def test_invalid_chunks(self):
        cases = {
            "duplicate Y": lambda r: r["Level"]["Sections"].value[1].append(r["Level"]["Sections"].value[1][0]),
            "Y out of range": lambda r: setattr(r["Level"]["Sections"].value[1][0]["Y"], "value", 16),
            "short Blocks": lambda r: r["Level"]["Sections"].value[1][0]["Blocks"].value.pop(),
            "no Data": lambda r: r["Level"]["Sections"].value[1][0].value.pop("Data"),
            "short HeightMap": lambda r: r["Level"]["HeightMap"].value.pop(),
            "short Biomes": lambda r: r["Level"]["Biomes"].value.pop(),
            "DataVersion": lambda r: r.value.__setitem__("DataVersion", Tag(av.INT, 1343)),
            "no Level": lambda r: r.value.pop("Level"),
        }
        for name, mutate in cases.items():
            with self.subTest(name), self.assertRaises(av.NbtError):
                self.chunk_with(mutate)()

    def test_optional_tags_may_be_absent(self):
        def strip(r):
            for k in ("Biomes", "TileTicks", "LightPopulated", "V"):
                r["Level"].value.pop(k)
            r["Level"]["Sections"].value[1][0].value.pop("SkyLight")
        _, root = av.nbt_decode(av.fixture_nbt())
        strip(root)
        ch = LegacyChunk(root, has_sky=False)
        self.assertEqual((ch.biome(4, 4), ch.tile_ticks()), (255, []))
        with self.assertRaises(av.NbtError):  # with sky, SkyLight is required
            LegacyChunk(root)


class Cli(unittest.TestCase):
    def test_fixture_and_check(self):
        with tempfile.TemporaryDirectory() as d:
            out = Path(d) / "r.0.-1.mca"
            with redirect_stdout(StringIO()) as s:
                self.assertEqual(av.main(["fixture", str(out)]), 0)
                self.assertEqual(av.main(["check", str(out)]), 0)
            self.assertIn(FIXTURE_SHA256, s.getvalue())
            self.assertIn("lossless", s.getvalue())


if __name__ == "__main__":
    unittest.main()

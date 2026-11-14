"""Five user-validated vectors; bootstrap adapted to a world-independent codec."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import unittest


def get_nibble(data, index):
    return (data[index // 2] >> (4 * (index % 2))) & 15


def set_nibble(data, index, value):
    if not 0 <= value <= 15:
        raise ValueError("Nibble outside 0..15")
    shift = 4 * (index % 2)
    data[index // 2] = (
        (data[index // 2] & ~(15 << shift)) | (value << shift)
    )


def write_id(blocks, add, index, block_id):
    if not 0 <= block_id <= 4095:
        raise ValueError("Block ID outside 0..4095")
    blocks[index] = block_id & 255
    set_nibble(add, index, block_id >> 8)


def read_id(blocks, add, index):
    return blocks[index] | (get_nibble(add, index) << 8)


class AddTests(unittest.TestCase):
    def test_known_bytes(self):
        blocks = bytearray(4096)
        add = bytearray(2048)
        ids = [255, 256, 1204, 4095]

        for index, block_id in enumerate(ids):
            write_id(blocks, add, index, block_id)

        # Независимо заданные ожидаемые байты:
        self.assertEqual(bytes(blocks[:4]), bytes.fromhex("ff 00 b4 ff"))
        self.assertEqual(bytes(add[:2]), bytes.fromhex("10 f4"))

        for index, block_id in enumerate(ids):
            self.assertEqual(read_id(blocks, add, index), block_id)

    def test_edit_preserves_neighbor(self):
        blocks = bytearray(4096)
        add = bytearray(2048)
        write_id(blocks, add, 0, 1204)
        write_id(blocks, add, 1, 4095)

        write_id(blocks, add, 0, 1)

        self.assertEqual(add[0], 0xF0)
        self.assertEqual(read_id(blocks, add, 0), 1)
        self.assertEqual(read_id(blocks, add, 1), 4095)

    def test_all_ids_both_nibble_positions(self):
        blocks = bytearray(4096)
        add = bytearray(2048)

        for block_id in range(4096):
            for index in (0, 1):
                write_id(blocks, add, index, block_id)
                self.assertEqual(read_id(blocks, add, index), block_id)

    def test_invalid_ids(self):
        for block_id in (-1, 4096):
            with self.assertRaises(ValueError):
                write_id(bytearray(4096), bytearray(2048), 0, block_id)

    def test_add_and_unknown_tags_nbt_round_trip(self):
        import struct
        from s03_codec import payload, number, string, encode_payload
        import s03_codec

        class CodecNamespace:
            def __getitem__(self, key):
                return getattr(s03_codec, key)
            def __setitem__(self, key, value):
                setattr(s03_codec, key, value)

        ns = CodecNamespace()

        blocks = bytearray(4096)
        add = bytearray(2048)
        write_id(blocks, add, 0, 1204)
        write_id(blocks, add, 1, 4095)

        section = {
            "Y": (1, 0),
            "Blocks": (7, bytes(blocks)),
            "Add": (7, bytes(add)),
            "Data": (7, bytes(2048)),
            "BlockLight": (7, bytes(2048)),
            "SkyLight": (7, bytes(2048)),
            "test:section": (3, 123456),
        }
        root = {
            "Level": (10, {
                "xPos": (3, -3),
                "zPos": (3, 15),
                "Sections": (9, (10, [section])),
                "test:level": (8, "nul\0 and \U0001F600"),
            }),
            "test:root": (10, {
                "counter": (4, 1234567890123),
                "empty": (9, (3, [])),
            }),
        }

        def encode(value):
            return b"\x0a\x00\x00" + ns["encode_payload"](10, value)

        original = encode(root)
        ns["raw"], ns["pos"] = original, 0
        self.assertEqual(ns["number"]("B"), 10)
        self.assertEqual(ns["string"](), "")
        decoded = ns["payload"](10)
        self.assertEqual(ns["pos"], len(original))
        self.assertEqual(encode(decoded), original)

        saved = decoded["Level"][1]["Sections"][1][1][0]
        self.assertEqual(
            [read_id(saved["Blocks"][1], saved["Add"][1], i)
             for i in (0, 1)],
            [1204, 4095],
        )
        self.assertEqual(saved["test:section"], (3, 123456))
        self.assertEqual(decoded["test:root"], root["test:root"])

        # Меняем известный тег; дополнительные данные должны сохраниться.
        decoded["Level"][1]["xPos"] = (3, -4)
        changed = encode(decoded)
        self.assertNotEqual(changed, original)
        ns["raw"], ns["pos"] = changed, 0
        self.assertEqual(ns["number"]("B"), 10)
        self.assertEqual(ns["string"](), "")
        reread = ns["payload"](10)
        self.assertEqual(ns["pos"], len(changed))
        self.assertEqual(encode(reread), changed)

        self.assertEqual(reread["Level"][1]["xPos"], (3, -4))
        actual_type, actual_text = reread["Level"][1]["test:level"]
        expected_type, expected_text = root["Level"][1]["test:level"]
        self.assertEqual(actual_type, expected_type)
        self.assertEqual(
            actual_text.encode("utf-16-be", errors="surrogatepass"),
            expected_text.encode("utf-16-be", errors="surrogatepass"),
        )
        self.assertEqual(reread["test:root"], root["test:root"])
        self.assertEqual(
            reread["Level"][1]["Sections"],
            decoded["Level"][1]["Sections"],
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)

"""Test vectors for the S02 block contract. W01/W02 must reproduce them in Rust.

Run: python -m unittest discover -s tests -p "test_legacy_blocks.py" -v
"""
import importlib.util
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("legacy_blocks", ROOT / "tools" / "legacy_blocks.py")
lb = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = lb
spec.loader.exec_module(lb)
LegacyBlock, BlockIdMap, LegacyStateTable = lb.LegacyBlock, lb.BlockIdMap, lb.LegacyStateTable

VANILLA = {
    "minecraft:air": 0,
    "minecraft:stone": 1,
    "minecraft:wool": 35,
    "minecraft:coal_block": 173,
    "minecraft:double_plant": 175,
}


def vanilla_map() -> BlockIdMap:
    m = BlockIdMap()
    for name, block_id in VANILLA.items():
        m.bind(name, block_id)
    return m


class Packing(unittest.TestCase):
    def test_ranges(self):
        LegacyBlock(4095, 15)
        for bad in [(-1, 0), (4096, 0), (0, 16), (0, -1)]:
            with self.assertRaises(ValueError):
                LegacyBlock(*bad)

    def test_all_pairs_round_trip(self):
        seen = set()
        for block_id in range(4096):
            for meta in range(16):
                b = LegacyBlock(block_id, meta)
                p = b.packed()
                self.assertEqual(LegacyBlock.unpack(p), b)
                self.assertEqual(LegacyBlock.from_anvil(*b.anvil()), b)
                seen.add(p)
        self.assertEqual(len(seen), 65536)

    def test_vectors_from_contract(self):
        self.assertEqual(LegacyBlock(35, 14).packed(), 574)
        self.assertEqual(LegacyBlock(35, 14).anvil(), (35, 0, 14))
        self.assertEqual(LegacyBlock(1204, 0).packed(), 19264)
        self.assertEqual(LegacyBlock(1204, 0).anvil(), (180, 4, 0))

    def test_nibble_order(self):
        arr = bytearray(2)
        lb.nibble_set(arr, 0, 0xA)
        lb.nibble_set(arr, 1, 0x5)
        lb.nibble_set(arr, 2, 0xF)
        self.assertEqual(bytes(arr), bytes([0x5A, 0x0F]))
        self.assertEqual([lb.nibble_get(arr, i) for i in range(4)], [0xA, 0x5, 0xF, 0x0])


class IdMap(unittest.TestCase):
    def test_world_ids_win(self):
        m = vanilla_map()
        m.bind("ntm:ore_uranium", 1204)
        self.assertEqual(m.register("ntm:ore_uranium"), 1204)

    def test_new_mod_block_gets_lowest_free_from_256(self):
        m = vanilla_map()
        m.bind("ntm:a", 256)
        self.assertEqual(m.register("ntm:b"), 257)
        self.assertNotIn(m.register("ntm:c"), lb.VANILLA_GAPS)

    def test_conflicts_are_errors(self):
        m = vanilla_map()
        with self.assertRaises(ValueError):
            m.bind("minecraft:stone", 2)
        with self.assertRaises(ValueError):
            m.bind("minecraft:granite", 1)

    def test_names_must_be_namespaced(self):
        for bad in ["stone", ":stone", "minecraft:"]:
            with self.assertRaises(ValueError):
                BlockIdMap().register(bad)

    def test_fml_item_data_round_trip_keeps_only_blocks(self):
        entries = [("\u0001minecraft:stone", 1), ("\u0002minecraft:stick", 280), ("\u0001ntm:ore_uranium", 1204)]
        m = BlockIdMap.from_fml_item_data(entries)
        self.assertEqual(m.id_of("ntm:ore_uranium"), 1204)
        self.assertIsNone(m.id_of("minecraft:stick"))
        self.assertEqual(m.to_fml_item_data(), [("\u0001minecraft:stone", 1), ("\u0001ntm:ore_uranium", 1204)])


class StateTable(unittest.TestCase):
    def test_contract_example(self):
        t = LegacyStateTable(vanilla_map())
        wool = LegacyBlock(35, 14)
        # registry ids 0, 1, 35, 173, 175 -> wool is index 2
        self.assertEqual(t.state_of(wool), 2 * 16 + 14)
        self.assertEqual(t.block_of(46), wool)
        self.assertEqual(t.name(46), "minecraft:wool")

    def test_bijection_over_every_state(self):
        t = LegacyStateTable(vanilla_map(), chunk_ids={2000})
        states = [t.state_of(LegacyBlock(i, m)) for i in [0, 1, 35, 173, 175, 2000] for m in range(16)]
        self.assertEqual(sorted(states), list(range(len(t))))
        for s in states:
            self.assertEqual(t.state_of(t.block_of(s)), s)

    def test_unknown_id_is_placeholder_and_saved_as_is(self):
        t = LegacyStateTable(vanilla_map(), chunk_ids={2000})
        s = t.state_of(LegacyBlock(2000, 7))
        self.assertEqual(t.name(s), "horizon:unknown_2000")
        self.assertEqual(t.block_of(s), LegacyBlock(2000, 7))
        self.assertIsNone(t.saved_name(s))

    def test_missing_mod_keeps_name_on_save(self):
        m = vanilla_map()
        m.bind("ntm:ore_uranium", 1204)
        t = LegacyStateTable(m, loaded=set(VANILLA))
        s = t.state_of(LegacyBlock(1204, 0))
        self.assertEqual(t.name(s), lb.MISSING)
        self.assertEqual(t.saved_name(s), "ntm:ore_uranium")

    def test_global_bits(self):
        self.assertEqual(LegacyStateTable(vanilla_map()).global_bits(), 7)  # 5 blocks * 16 = 80 states


class Boundaries(unittest.TestCase):
    def test_item_ranges(self):
        self.assertEqual(lb.item_kind(35), "block_or_itemblock")
        self.assertEqual(lb.item_kind(4095), "block_or_itemblock")
        self.assertEqual(lb.item_kind(4096), "item_only")
        self.assertEqual(lb.item_kind(31999), "item_only")
        with self.assertRaises(ValueError):
            lb.item_kind(32000)

    def test_modern_view_exceptions(self):
        table = {LegacyBlock(1, 3).packed(): "minecraft:diorite", LegacyBlock(35, 14).packed(): "minecraft:red_wool"}
        self.assertEqual(lb.modern_view(LegacyBlock(1, 3), "minecraft:stone", table), "minecraft:stone")
        self.assertEqual(lb.modern_view(LegacyBlock(35, 14), "minecraft:wool", table), "minecraft:red_wool")
        self.assertEqual(lb.modern_view(LegacyBlock(165, 0), "minecraft:slime", table), "horizon:unknown_165")
        self.assertEqual(lb.modern_view(LegacyBlock(2000, 0), None, table), "horizon:unknown_2000")
        self.assertEqual(lb.modern_view(LegacyBlock(1204, 0), "ntm:ore_uranium", table), "ntm:ore_uranium")


if __name__ == "__main__":
    unittest.main()

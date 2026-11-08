"""Test vectors for the S02 block contract. W01/W02 must reproduce them in Rust."""
import importlib.util
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("legacy_blocks", ROOT / "tools" / "legacy_blocks.py")
lb = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = lb
spec.loader.exec_module(lb)
LegacyBlock, BlockIdMap = lb.LegacyBlock, lb.BlockIdMap

# A few vanilla 1.7.10 blocks with their fixed ids.
VANILLA = {
    "minecraft:air": 0,
    "minecraft:stone": 1,
    "minecraft:wool": 35,
    "minecraft:coal_block": 173,
    "minecraft:packed_ice": 174,
    "minecraft:double_plant": 175,
}


class PackingTests(unittest.TestCase):
    def test_packed_vectors(self):
        for block, packed in [
            (LegacyBlock(0, 0), 0),
            (LegacyBlock(1, 0), 16),
            (LegacyBlock(35, 14), 574),     # red wool; 1.12 table: 574 -> minecraft:red_wool
            (LegacyBlock(175, 0), 2800),    # double_plant (sunflower, lower half)
            (LegacyBlock(4095, 15), 0xFFFF),
        ]:
            self.assertEqual(block.packed(), packed)
            self.assertEqual(LegacyBlock.unpack(packed), block)

    def test_all_pairs_round_trip(self):
        for value in range(1 << 16):
            self.assertEqual(LegacyBlock.unpack(value).packed(), value)

    def test_anvil_split_for_ids_above_255(self):
        b = LegacyBlock(2000, 7)                     # 0x7D0
        self.assertEqual(b.anvil_parts(), (0xD0, 0x7, 7))
        self.assertEqual(LegacyBlock.from_anvil(0xD0, 0x7, 7), b)
        self.assertEqual(LegacyBlock(35, 14).anvil_parts(), (35, 0, 14))  # no Add nibble needed

    def test_ranges(self):
        for bad in [(-1, 0), (4096, 0), (1, 16), (1, -1)]:
            with self.assertRaises(ValueError):
                LegacyBlock(*bad)


class IdMapTests(unittest.TestCase):
    def setUp(self):
        self.m = BlockIdMap.with_vanilla(VANILLA)

    def test_world_ids_win_over_allocation(self):
        self.m.load_world({"examplemod:ore": 2000}, loaded_mods={"examplemod"})
        self.assertEqual(self.m.allocate("examplemod:ore"), 2000)
        self.assertEqual(self.m.allocate("examplemod:machine"), 176)   # lowest free >= 176
        self.assertEqual(self.m.allocate("examplemod:machine"), 176)   # stable

    def test_conflicting_binding_is_an_error(self):
        with self.assertRaises(ValueError):
            self.m.load_world({"examplemod:ore": 1}, loaded_mods={"examplemod"})   # id of stone

    def test_mod_not_loaded_is_missing_but_kept(self):
        self.m.load_world({"gonemod:pipe": 300}, loaded_mods=set())
        self.assertTrue(self.m.is_missing(300))
        key = lb.internal_key(self.m, LegacyBlock(300, 5))
        self.assertEqual(key, ("gonemod:pipe", 5))
        self.assertEqual(lb.from_internal(self.m, key), LegacyBlock(300, 5))

    def test_unbound_id_gets_placeholder_and_round_trips(self):
        key = lb.internal_key(self.m, LegacyBlock(1234, 9))
        self.assertEqual(key, ("horizon_ntm:unknown_1234", 9))
        self.assertTrue(self.m.is_missing(1234))
        self.assertEqual(lb.from_internal(self.m, key), LegacyBlock(1234, 9))

    def test_every_meta_is_a_state_even_unused_ones(self):
        # 1.7.10 stone uses only meta 0; meta 1 must survive (in 1.12 it would mean granite).
        for meta in range(16):
            key = lb.internal_key(self.m, LegacyBlock(1, meta))
            self.assertEqual(lb.from_internal(self.m, key), LegacyBlock(1, meta))

    def test_names_must_be_namespaced(self):
        for bad in ["stone", ":stone", "minecraft:"]:
            with self.assertRaises(ValueError):
                self.m.allocate(bad)

    def test_vanilla_ids_stay_in_vanilla_range(self):
        with self.assertRaises(ValueError):
            BlockIdMap.with_vanilla({"minecraft:slime": 165, "minecraft:fake": 200})


if __name__ == "__main__":
    unittest.main()

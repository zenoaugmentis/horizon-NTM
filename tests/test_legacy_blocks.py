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
LegacyBlock, LegacyRegistry, LegacyStateTable = lb.LegacyBlock, lb.LegacyRegistry, lb.LegacyStateTable

# Real names for ids the vectors use; the rest of vanilla 1.7.10 is filled with
# stand-in names until the S06 fixture provides the full table.
REAL = {1: "minecraft:stone", 35: "minecraft:wool", 175: "minecraft:double_plant", 256: "minecraft:iron_shovel"}
VANILLA_BLOCK_IDS = [i for i in range(0, 176) if i not in lb.VANILLA_GAPS]
VANILLA_ITEM_IDS = list(range(256, 423)) + list(range(2256, 2268))


def vanilla() -> LegacyRegistry:
    r = LegacyRegistry()
    for i in VANILLA_BLOCK_IDS:
        r.register_block("minecraft:air" if i == 0 else REAL.get(i, f"minecraft:block_{i}"), hint=i)
    for i in VANILLA_ITEM_IDS:
        r.register_item(REAL.get(i, f"minecraft:item_{i}"), hint=i)
    return r


def fml(*entries, **extra):
    return {"ItemData": [{"K": k, "V": v} for k, v in entries], **extra}


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
                self.assertEqual(LegacyBlock.unpack(b.packed()), b)
                self.assertEqual(LegacyBlock.from_anvil(*b.anvil()), b)
                seen.add(b.packed())
        self.assertEqual(len(seen), 65536)

    def test_contract_vectors(self):
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


class Allocation(unittest.TestCase):
    """FML 1.7.10: one id space; blocks from 0, items from 4096, ItemBlock = block id."""

    def test_first_mod_block_is_165(self):
        r = vanilla()
        self.assertEqual(r.register_block("ntm:ore_uranium"), 165)
        self.assertEqual(r.items["ntm:ore_uranium"], 165)  # ItemBlock

    def test_mod_blocks_skip_vanilla_items(self):
        r = vanilla()
        ids = [r.register_block(f"ntm:b{i}") for i in range(5 + 80 + 1)]
        self.assertEqual(ids[:5], [165, 166, 167, 168, 169])
        self.assertEqual(ids[5], 176)
        self.assertEqual(ids[-1], 423)  # 176..255 taken, 256..422 are vanilla items
        self.assertNotIn(256, ids)

    def test_first_mod_item_is_4096(self):
        r = vanilla()
        self.assertEqual(r.register_item("ntm:ingot_uranium"), 4096)

    def test_free_hint_is_honoured_taken_hint_is_not(self):
        r = vanilla()
        self.assertEqual(r.register_block("ntm:a", hint=1000), 1000)
        self.assertEqual(r.register_block("ntm:b", hint=1000), 165)
        self.assertEqual(r.register_block("ntm:c", hint=5000), 166)  # > 4095 is not a block id

    def test_blocked_ids_are_skipped(self):
        r = vanilla()
        r.blocked = {165, 166}
        self.assertEqual(r.register_block("ntm:a"), 167)

    def test_conflicts_and_names(self):
        r = vanilla()
        with self.assertRaises(ValueError):
            r._bind_block("minecraft:stone", 2)
        with self.assertRaises(ValueError):
            r._bind_block("minecraft:granite", 1)
        with self.assertRaises(ValueError):
            r._bind_item("ntm:ingot", 35)  # id 35 is block wool, different name
        for bad in ["stone", ":stone", "minecraft:"]:
            with self.assertRaises(ValueError):
                r.register_block(bad)

    def test_frozen_rejects_new_names(self):
        r = vanilla().freeze()
        with self.assertRaises(ValueError):
            r.register_block("ntm:late")

    def test_item_kinds(self):
        r = vanilla()
        r.register_block("ntm:ore_uranium")
        self.assertEqual(r.item_kind(35), "item_block")
        self.assertEqual(r.item_kind(165), "item_block")
        self.assertEqual(r.item_kind(256), "item")
        self.assertEqual(r.item_kind(4096), "free")
        with self.assertRaises(ValueError):
            r.item_kind(32000)


class WorldLifecycle(unittest.TestCase):
    def frozen(self):
        r = vanilla()
        r.register_block("ntm:ore_uranium")  # 165 in a fresh world
        r.register_item("ntm:ingot_uranium")  # 4096
        return r.freeze()

    def test_world_ids_win(self):
        w = self.frozen().inject_world(fml(("\u0001ntm:ore_uranium", 1204), ("\u0002ntm:ore_uranium", 1204)))
        self.assertEqual(w.blocks["ntm:ore_uranium"], 1204)
        self.assertEqual(w.items["ntm:ore_uranium"], 1204)

    def test_removed_mod_is_missing_and_keeps_id(self):
        w = self.frozen().inject_world(fml(("\u0001oldmod:x", 300), ("\u0002oldmod:x", 300)))
        self.assertIn("oldmod:x", w.missing_blocks)
        self.assertEqual(w.blocks["oldmod:x"], 300)
        self.assertIn({"K": "\u0001oldmod:x", "V": 300}, w.to_fml()["ItemData"])

    def test_added_mod_gets_free_ids_around_world_ids(self):
        w = self.frozen().inject_world(fml(("\u0001othermod:y", 165)))
        self.assertEqual(w.blocks["othermod:y"], 165)
        self.assertEqual(w.blocks["ntm:ore_uranium"], 166)
        self.assertEqual(w.items["ntm:ore_uranium"], 166)
        self.assertEqual(w.items["ntm:ingot_uranium"], 4096)

    def test_aliases_rename_before_binding(self):
        w = self.frozen().inject_world(
            fml(("\u0001ntm:old_ore", 1204), BlockAliases=[{"K": "ntm:old_ore", "V": "ntm:ore_uranium"}])
        )
        self.assertEqual(w.blocks["ntm:ore_uranium"], 1204)
        self.assertNotIn("ntm:old_ore", w.blocks)

    def test_full_fml_round_trip(self):
        world = fml(
            ("\u0001ntm:ore_uranium", 1204),
            ("\u0002ntm:ore_uranium", 1204),
            ("\u0002ntm:ingot_uranium", 4100),
            BlockedItemIds=[3000],
            BlockAliases=[],
            BlockSubstitutions=[{"K": "minecraft:dirt"}],
            ItemAliases=[{"K": "ntm:a", "V": "ntm:b"}],
            ItemSubstitutions=[],
        )
        out = self.frozen().inject_world(world).to_fml()
        for key in ("BlockedItemIds", "BlockSubstitutions", "ItemAliases"):
            self.assertEqual(out[key], world[key], key)
        for entry in world["ItemData"]:
            self.assertIn(entry, out["ItemData"])

    def test_old_modItemData_format_is_rejected(self):
        with self.assertRaises(ValueError):
            self.frozen().inject_world({"ModItemData": []})

    def test_client_takes_server_map_and_never_allocates(self):
        client = self.frozen()
        w = client.from_handshake({"\u0001ntm:ore_uranium": 1204, "\u0001servermod:z": 1300})
        self.assertEqual(w.blocks["ntm:ore_uranium"], 1204)
        self.assertIn("servermod:z", w.missing_blocks)
        self.assertNotIn("minecraft:stone", w.blocks)  # not sent -> not on this server
        self.assertNotIn("ntm:ingot_uranium", w.items)


class StateTable(unittest.TestCase):
    def table(self):
        w = vanilla().freeze().inject_world(fml(("\u0001oldmod:x", 300)))
        return LegacyStateTable(w)

    def test_state_is_packed_and_dense(self):
        t = self.table()
        self.assertEqual(len(t), 65536)
        self.assertEqual(t.state_of(LegacyBlock(35, 14)), 574)
        self.assertEqual(t.block_of(574), LegacyBlock(35, 14))
        self.assertEqual(t.name(574), "minecraft:wool")
        self.assertEqual(t.global_bits(), 16)

    def test_ids_do_not_shift_when_unknown_ids_appear(self):
        t = self.table()
        before = t.state_of(LegacyBlock(1204, 3))
        self.assertEqual(t.name(LegacyBlock(2000, 0).packed()), "horizon:unknown_2000")
        self.assertEqual(t.state_of(LegacyBlock(1204, 3)), before)

    def test_names_are_unique_and_placeholders_flagged(self):
        t = self.table()
        names = [t.name(i << 4) for i in range(4096)]
        self.assertEqual(len(set(names)), 4096)
        self.assertTrue(t.is_missing(300 << 4))
        self.assertEqual(t.name(300 << 4), "oldmod:x")
        self.assertTrue(t.is_placeholder(2000 << 4))
        self.assertFalse(t.is_placeholder(35 << 4))


class ModernView(unittest.TestCase):
    def test_exceptions(self):
        table = {LegacyBlock(1, 3).packed(): "minecraft:diorite", LegacyBlock(35, 14).packed(): "minecraft:red_wool"}
        mv = lb.modern_view
        self.assertEqual(mv(LegacyBlock(1, 3), "minecraft:stone", table), "minecraft:stone")
        self.assertEqual(mv(LegacyBlock(35, 14), "minecraft:wool", table), "minecraft:red_wool")
        self.assertEqual(mv(LegacyBlock(165, 0), "minecraft:slime", table), "horizon:unknown_165")
        self.assertEqual(mv(LegacyBlock(165, 0), "ntm:ore_uranium", table), "ntm:ore_uranium")
        self.assertEqual(mv(LegacyBlock(2000, 0), "horizon:unknown_2000", table), "horizon:unknown_2000")
        self.assertEqual(mv(LegacyBlock(1204, 0), "ntm:ore_uranium", table), "ntm:ore_uranium")


if __name__ == "__main__":
    unittest.main()

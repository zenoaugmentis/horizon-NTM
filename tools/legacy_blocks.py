#!/usr/bin/env python3
"""Executable reference for the S02 block contract (docs/contracts/blocks.md).

Not engine code: W01/W02 implement this in Rust and must reproduce
tests/test_legacy_blocks.py exactly. Id allocation follows FML 1.7.10
GameData / FMLControlledNamespacedRegistry.add (facts only, no code copied).
"""
from __future__ import annotations

from dataclasses import dataclass, field

MAX_BLOCK_ID = 4095
MIN_ITEM_ID = 4096
MAX_ITEM_ID = 31999
MAX_META = 15
VANILLA_MAX_BLOCK_ID = 175
VANILLA_GAPS = range(165, 170)  # free in 1.7.10, taken by 1.8

BLOCK_PREFIX = "\u0001"
ITEM_PREFIX = "\u0002"
UNKNOWN_PREFIX = "horizon:unknown_"
STATE_COUNT = (MAX_BLOCK_ID + 1) * 16  # dense legacy registry: 65 536 states


@dataclass(frozen=True, order=True)
class LegacyBlock:
    id: int
    meta: int = 0

    def __post_init__(self):
        if not 0 <= self.id <= MAX_BLOCK_ID:
            raise ValueError(f"block id {self.id} out of 0..={MAX_BLOCK_ID}")
        if not 0 <= self.meta <= MAX_META:
            raise ValueError(f"meta {self.meta} out of 0..={MAX_META}")

    def packed(self) -> int:
        return self.id << 4 | self.meta

    @classmethod
    def unpack(cls, packed: int) -> "LegacyBlock":
        if not 0 <= packed <= 0xFFFF:
            raise ValueError(f"packed {packed} out of u16")
        return cls(packed >> 4, packed & 0xF)

    def anvil(self) -> tuple[int, int, int]:
        """(Blocks byte, Add nibble, Data nibble) for one block of a section."""
        return self.id & 0xFF, self.id >> 8, self.meta

    @classmethod
    def from_anvil(cls, blocks: int, add: int, data: int) -> "LegacyBlock":
        return cls((add & 0xF) << 8 | (blocks & 0xFF), data & 0xF)


def nibble_get(array: bytes, index: int) -> int:
    b = array[index >> 1]
    return b & 0xF if index % 2 == 0 else b >> 4


def nibble_set(array: bytearray, index: int, value: int) -> None:
    i = index >> 1
    if index % 2 == 0:
        array[i] = (array[i] & 0xF0) | (value & 0xF)
    else:
        array[i] = (array[i] & 0x0F) | (value & 0xF) << 4


def check_name(name: str) -> None:
    ns, sep, path = name.partition(":")
    if not sep or not ns or not path:
        raise ValueError(f"name {name!r} must be namespaced (modid:name)")


@dataclass
class LegacyRegistry:
    """Shared block+item id space of one world (FML availabilityMap)."""

    blocks: dict[str, int] = field(default_factory=dict)
    items: dict[str, int] = field(default_factory=dict)
    blocked: set[int] = field(default_factory=set)
    block_aliases: dict[str, str] = field(default_factory=dict)
    item_aliases: dict[str, str] = field(default_factory=dict)
    block_substitutions: list[str] = field(default_factory=list)
    item_substitutions: list[str] = field(default_factory=list)
    mods: list[tuple[str, str]] = field(default_factory=list)
    missing_blocks: set[str] = field(default_factory=set)
    missing_items: set[str] = field(default_factory=set)
    frozen: bool = False

    # -- id space ---------------------------------------------------------
    def _owner(self, i: int) -> tuple[str, str] | None:
        for kind, table in (("block", self.blocks), ("item", self.items)):
            for name, v in table.items():
                if v == i:
                    return kind, name
        return None

    def _used(self) -> set[int]:
        return set(self.blocks.values()) | set(self.items.values()) | self.blocked

    def _first_free(self, start: int, stop: int) -> int:
        used = self._used()
        for i in range(start, stop + 1):
            if i not in used:
                return i
        raise ValueError(f"no free id in {start}..={stop}")

    def _bind_block(self, name: str, block_id: int) -> None:
        LegacyBlock(block_id)
        if self.blocks.get(name, block_id) != block_id:
            raise ValueError(f"block {name} is {self.blocks[name]}, not {block_id}")
        owner = self._owner(block_id)
        if owner and owner != ("block", name) and owner != ("item", name):
            raise ValueError(f"id {block_id} belongs to {owner[0]} {owner[1]}, not block {name}")
        self.blocks[name] = block_id

    def _bind_item(self, name: str, item_id: int) -> None:
        if not 0 <= item_id <= MAX_ITEM_ID:
            raise ValueError(f"item id {item_id} out of 0..={MAX_ITEM_ID}")
        if self.items.get(name, item_id) != item_id:
            raise ValueError(f"item {name} is {self.items[name]}, not {item_id}")
        owner = self._owner(item_id)
        if owner and owner != ("item", name) and owner != ("block", name):
            raise ValueError(f"id {item_id} belongs to {owner[0]} {owner[1]}, not item {name}")
        self.items[name] = item_id

    # -- registration (before freeze) -------------------------------------
    def register_block(self, name: str, hint: int = -1, item_block: bool = True) -> int:
        """FML: hint if free and <= 4095, else first free id from 0."""
        self._check_open(name)
        if name in self.blocks:
            return self.blocks[name]
        used = self._used()
        block_id = hint if 0 <= hint <= MAX_BLOCK_ID and hint not in used else self._first_free(0, MAX_BLOCK_ID)
        self._bind_block(name, block_id)
        if item_block:
            self._bind_item(name, block_id)
        return block_id

    def register_item(self, name: str, hint: int = -1) -> int:
        """FML: hint if free, else first free id from 4096."""
        self._check_open(name)
        if name in self.items:
            return self.items[name]
        item_id = hint if 0 <= hint <= MAX_ITEM_ID and hint not in self._used() else self._first_free(MIN_ITEM_ID, MAX_ITEM_ID)
        self._bind_item(name, item_id)
        return item_id

    def _check_open(self, name: str) -> None:
        check_name(name)
        if self.frozen:
            raise ValueError(f"registry is frozen, cannot register {name}")

    def freeze(self) -> "LegacyRegistry":
        self.frozen = True
        return self

    # -- world load / save -------------------------------------------------
    def inject_world(self, fml: dict) -> "LegacyRegistry":
        """Registry for a world: world ids win, missing names keep their ids, new names get free ids."""
        if "ModItemData" in fml and "ItemData" not in fml:
            raise ValueError("pre-1.7 FML ModItemData is not supported")
        w = LegacyRegistry(frozen=True)
        w.blocked = set(fml.get("BlockedItemIds", []))
        w.block_aliases = {e["K"]: e["V"] for e in fml.get("BlockAliases", [])}
        w.item_aliases = {e["K"]: e["V"] for e in fml.get("ItemAliases", [])}
        w.block_substitutions = [e["K"] for e in fml.get("BlockSubstitutions", [])]
        w.item_substitutions = [e["K"] for e in fml.get("ItemSubstitutions", [])]
        w.mods = list(self.mods)
        data = [(e["K"], e["V"]) for e in fml.get("ItemData", [])]
        for prefix, known, aliases, bind, missing in (
            (BLOCK_PREFIX, self.blocks, w.block_aliases, w._bind_block, w.missing_blocks),
            (ITEM_PREFIX, self.items, w.item_aliases, w._bind_item, w.missing_items),
        ):
            for key, value in data:
                if not key.startswith(prefix):
                    continue
                name = aliases.get(key[1:], key[1:])
                check_name(name)
                bind(name, value)
                if name not in known:
                    missing.add(name)
        for name, hint in self.blocks.items():
            if name not in w.blocks:
                block_id = hint if hint not in w._used() else w._first_free(0, MAX_BLOCK_ID)
                w._bind_block(name, block_id)
        for name, hint in self.items.items():
            if name not in w.items:
                if name in w.blocks:
                    w._bind_item(name, w.blocks[name])
                else:
                    item_id = hint if hint not in w._used() else w._first_free(MIN_ITEM_ID, MAX_ITEM_ID)
                    w._bind_item(name, item_id)
        return w

    def to_fml(self) -> dict:
        data = [{"K": BLOCK_PREFIX + n, "V": i} for n, i in sorted(self.blocks.items(), key=lambda x: (x[1], x[0]))]
        data += [{"K": ITEM_PREFIX + n, "V": i} for n, i in sorted(self.items.items(), key=lambda x: (x[1], x[0]))]
        return {
            "ModList": [{"ModId": m, "ModVersion": v} for m, v in self.mods],
            "ItemData": data,
            "BlockedItemIds": sorted(self.blocked),
            "BlockAliases": [{"K": k, "V": v} for k, v in self.block_aliases.items()],
            "BlockSubstitutions": [{"K": k} for k in self.block_substitutions],
            "ItemAliases": [{"K": k, "V": v} for k, v in self.item_aliases.items()],
            "ItemSubstitutions": [{"K": k} for k in self.item_substitutions],
        }

    def from_handshake(self, mod_ids: dict[str, int]) -> "LegacyRegistry":
        """Client side: the server's ModIdData map replaces ours; the client never allocates."""
        w = self.inject_world({"ItemData": [{"K": k, "V": v} for k, v in mod_ids.items()]})
        # names the server did not send do not exist there: no local allocation
        w.blocks = {n: i for n, i in w.blocks.items() if BLOCK_PREFIX + n in mod_ids}
        w.items = {n: i for n, i in w.items.items() if ITEM_PREFIX + n in mod_ids}
        return w

    def item_kind(self, item_id: int) -> str:
        if not 0 <= item_id <= MAX_ITEM_ID:
            raise ValueError(f"item id {item_id} out of 0..={MAX_ITEM_ID}")
        owner = self._owner(item_id)
        if owner is None:
            return "free"
        if owner[0] == "block" or owner[1] in self.blocks:
            return "item_block"
        return "item"


class LegacyStateTable:
    """Horizon side: dense registry of 4096 blocks x 16 `meta` states; state == packed."""

    def __init__(self, registry: LegacyRegistry):
        self._names: dict[int, str] = {i: n for n, i in registry.blocks.items()}
        self._missing = set(registry.missing_blocks)

    def __len__(self) -> int:
        return STATE_COUNT

    @staticmethod
    def state_of(block: LegacyBlock) -> int:
        return block.packed()

    @staticmethod
    def block_of(state: int) -> LegacyBlock:
        if not 0 <= state < STATE_COUNT:
            raise ValueError(f"state {state} out of range")
        return LegacyBlock.unpack(state)

    def name(self, state: int) -> str:
        block_id = state >> 4
        return self._names.get(block_id, f"{UNKNOWN_PREFIX}{block_id}")

    def is_missing(self, state: int) -> bool:
        return self.name(state) in self._missing

    def is_placeholder(self, state: int) -> bool:
        return self.is_missing(state) or self.name(state).startswith(UNKNOWN_PREFIX)

    @staticmethod
    def global_bits() -> int:
        return (STATE_COUNT - 1).bit_length()


def modern_view(block: LegacyBlock, name: str, table_1_12: dict[int, str]) -> str:
    """Render-only mapping to a modern state via Horizon's 1.12 table, with 1.7.10 exceptions."""
    unknown = f"{UNKNOWN_PREFIX}{block.id}"
    if name.startswith(UNKNOWN_PREFIX):
        return unknown
    if not name.startswith("minecraft:"):
        return name  # mod block, even on 165..=169
    if block.id in VANILLA_GAPS or block.id > VANILLA_MAX_BLOCK_ID:
        return unknown
    if name == "minecraft:stone":
        return "minecraft:stone"
    return table_1_12.get(block.packed(), unknown)

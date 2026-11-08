#!/usr/bin/env python3
"""Executable reference for the S02 block contract (docs/contracts/blocks.md).

Not engine code: W01/W02 implement this in Rust and must reproduce
tests/test_legacy_blocks.py exactly.
"""
from __future__ import annotations

from dataclasses import dataclass

MAX_BLOCK_ID = 4095
MAX_ITEM_ID = 31999
MAX_META = 15
FIRST_MOD_ID = 256
VANILLA_MAX_ID = 175
VANILLA_GAPS = range(165, 170)  # unused in 1.7.10, taken by 1.8

FML_BLOCK_PREFIX = "\u0001"
FML_ITEM_PREFIX = "\u0002"

UNKNOWN_PREFIX = "horizon:unknown_"
MISSING = "horizon:missing"


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
        """(Blocks byte, Add nibble, Data nibble) for one block in a section."""
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
        raise ValueError(f"block name {name!r} must be namespaced (modid:name)")


class BlockIdMap:
    """Per-world name <-> id map. The world's existing ids always win."""

    def __init__(self) -> None:
        self._by_name: dict[str, int] = {}
        self._by_id: dict[int, str] = {}

    def bind(self, name: str, block_id: int) -> None:
        check_name(name)
        LegacyBlock(block_id)
        if self._by_name.get(name, block_id) != block_id:
            raise ValueError(f"{name} is bound to {self._by_name[name]}, not {block_id}")
        if self._by_id.get(block_id, name) != name:
            raise ValueError(f"id {block_id} is bound to {self._by_id[block_id]}, not {name}")
        self._by_name[name] = block_id
        self._by_id[block_id] = name

    def register(self, name: str) -> int:
        """Id for a block name: the existing one, or the lowest free id >= 256."""
        check_name(name)
        if name in self._by_name:
            return self._by_name[name]
        for block_id in range(FIRST_MOD_ID, MAX_BLOCK_ID + 1):
            if block_id not in self._by_id:
                self.bind(name, block_id)
                return block_id
        raise ValueError("no free block ids")

    def id_of(self, name: str) -> int | None:
        return self._by_name.get(name)

    def name_of(self, block_id: int) -> str | None:
        return self._by_id.get(block_id)

    def ids(self) -> list[int]:
        return sorted(self._by_id)

    @classmethod
    def from_fml_item_data(cls, entries: list[tuple[str, int]]) -> "BlockIdMap":
        """FML level.dat ItemData {K, V}; only \\u0001 (block) keys are taken."""
        m = cls()
        for key, value in entries:
            if key.startswith(FML_BLOCK_PREFIX):
                m.bind(key[len(FML_BLOCK_PREFIX):], value)
        return m

    def to_fml_item_data(self) -> list[tuple[str, int]]:
        return [(FML_BLOCK_PREFIX + self._by_id[i], i) for i in self.ids()]


class LegacyStateTable:
    """Horizon-side registry: every legacy id is one block with 16 states (property `meta`).

    state = base(id) + meta, blocks ordered by id. Ids found in chunks but not in
    the map become `horizon:unknown_<id>` placeholders, so nothing is lost.
    """

    def __init__(self, id_map: BlockIdMap, chunk_ids: set[int] = frozenset(), loaded: set[str] | None = None):
        ids = sorted(set(id_map.ids()) | set(chunk_ids))
        self._ids = ids
        self._index = {block_id: i for i, block_id in enumerate(ids)}
        self._names = []
        for block_id in ids:
            name = id_map.name_of(block_id)
            if name is None:
                self._names.append(f"{UNKNOWN_PREFIX}{block_id}")
            elif loaded is not None and name not in loaded:
                self._names.append(MISSING)
            else:
                self._names.append(name)
        self._original = {block_id: id_map.name_of(block_id) for block_id in ids}

    def __len__(self) -> int:
        return len(self._ids) * 16

    def state_of(self, block: LegacyBlock) -> int:
        return self._index[block.id] * 16 + block.meta

    def block_of(self, state: int) -> LegacyBlock:
        if not 0 <= state < len(self):
            raise ValueError(f"state {state} out of range")
        return LegacyBlock(self._ids[state >> 4], state & 0xF)

    def name(self, state: int) -> str:
        return self._names[state >> 4]

    def saved_name(self, state: int) -> str | None:
        """The name written back on save: the world's original one, never a placeholder."""
        return self._original[self._ids[state >> 4]]

    def global_bits(self) -> int:
        return max(1, (len(self) - 1).bit_length())


def item_kind(item_id: int) -> str:
    if not 0 <= item_id <= MAX_ITEM_ID:
        raise ValueError(f"item id {item_id} out of 0..={MAX_ITEM_ID}")
    return "block_or_itemblock" if item_id <= MAX_BLOCK_ID else "item_only"


def modern_view(block: LegacyBlock, name: str | None, table_1_12: dict[int, str]) -> str:
    """Render-only mapping to a modern state via Horizon's 1.12 table, with 1.7.10 exceptions."""
    if name is None or block.id in VANILLA_GAPS or (block.id > VANILLA_MAX_ID and name.startswith("minecraft:")):
        return f"{UNKNOWN_PREFIX}{block.id}"
    if name == "minecraft:stone":
        return "minecraft:stone"
    if not name.startswith("minecraft:"):
        return name
    return table_1_12.get(block.packed(), f"{UNKNOWN_PREFIX}{block.id}")

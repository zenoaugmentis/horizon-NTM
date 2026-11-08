#!/usr/bin/env python3
"""Reference model of the S02 block contract (docs/contracts/blocks.md).

Executable spec, not production code: W01/W02 implement the same rules in Rust
and must reproduce the vectors in tests/test_legacy_blocks.py.
"""
from __future__ import annotations

from dataclasses import dataclass, field

MAX_ID = 4095        # 12 bits: Blocks byte (low 8) + Add nibble (high 4)
MAX_META = 15        # 4 bits: Data nibble
VANILLA_MAX_ID = 175  # minecraft:double_plant, the highest vanilla 1.7.10 block id
FIRST_MOD_ID = VANILLA_MAX_ID + 1
MISSING_NS = "horizon_ntm"


@dataclass(frozen=True, order=True)
class LegacyBlock:
    id: int
    meta: int = 0

    def __post_init__(self):
        if not 0 <= self.id <= MAX_ID:
            raise ValueError(f"block id {self.id} outside 0..={MAX_ID}")
        if not 0 <= self.meta <= MAX_META:
            raise ValueError(f"meta {self.meta} outside 0..={MAX_META}")

    def packed(self) -> int:
        """`id << 4 | meta`, 16 bits; the same key as vanilla's 1.12 `blockId << 4 | data`."""
        return self.id << 4 | self.meta

    @classmethod
    def unpack(cls, value: int) -> "LegacyBlock":
        if not 0 <= value <= 0xFFFF:
            raise ValueError(f"packed value {value} outside u16")
        return cls(value >> 4, value & 0xF)

    def anvil_parts(self) -> tuple[int, int, int]:
        """(Blocks byte, Add nibble, Data nibble) as stored in a 1.7.10 Anvil section."""
        return self.id & 0xFF, self.id >> 8, self.meta

    @classmethod
    def from_anvil(cls, blocks_byte: int, add_nibble: int, data_nibble: int) -> "LegacyBlock":
        return cls((add_nibble & 0xF) << 8 | (blocks_byte & 0xFF), data_nibble & 0xF)


def check_name(name: str) -> str:
    ns, sep, path = name.partition(":")
    if not sep or not ns or not path:
        raise ValueError(f"block name {name!r} is not namespace:path")
    return name


@dataclass
class BlockIdMap:
    """Per-world name <-> numeric id map (what FML keeps in level.dat)."""

    by_name: dict[str, int] = field(default_factory=dict)
    by_id: dict[int, str] = field(default_factory=dict)
    missing: set[str] = field(default_factory=set)  # names whose mod is not loaded

    @classmethod
    def with_vanilla(cls, vanilla: dict[str, int]) -> "BlockIdMap":
        m = cls()
        for name, i in vanilla.items():
            if i > VANILLA_MAX_ID:
                raise ValueError(f"vanilla {name} has id {i} > {VANILLA_MAX_ID}")
            m._bind(name, i)
        return m

    def _bind(self, name: str, i: int) -> None:
        check_name(name)
        LegacyBlock(i)  # range check
        if self.by_name.get(name, i) != i:
            raise ValueError(f"{name} already has id {self.by_name[name]}, not {i}")
        if self.by_id.get(i, name) != name:
            raise ValueError(f"id {i} already belongs to {self.by_id[i]}, not {name}")
        self.by_name[name] = i
        self.by_id[i] = name

    def load_world(self, saved: dict[str, int], loaded_mods: set[str]) -> None:
        """Apply a world's saved map. Saved ids always win; mods not loaded become missing."""
        for name, i in sorted(saved.items(), key=lambda kv: kv[1]):
            self._bind(name, i)
            ns = name.split(":", 1)[0]
            if ns != "minecraft" and ns not in loaded_mods:
                self.missing.add(name)

    def allocate(self, name: str) -> int:
        """Id for a block registered by a loaded mod: existing binding, else lowest free id >= 176."""
        check_name(name)
        if name in self.by_name:
            return self.by_name[name]
        for i in range(FIRST_MOD_ID, MAX_ID + 1):
            if i not in self.by_id:
                self._bind(name, i)
                return i
        raise OverflowError("no free block ids left (4096 used)")

    def name_of(self, i: int) -> str:
        """Name for an id found in a chunk; ids nobody bound get a stable placeholder name."""
        LegacyBlock(i)
        return self.by_id.get(i) or f"{MISSING_NS}:unknown_{i}"

    def is_missing(self, i: int) -> bool:
        return i not in self.by_id or self.by_id[i] in self.missing


def internal_key(m: BlockIdMap, b: LegacyBlock) -> tuple[str, int]:
    """The internal state for a legacy pair: (block name, meta). Every name gets all 16 metas."""
    return m.name_of(b.id), b.meta


def from_internal(m: BlockIdMap, key: tuple[str, int]) -> LegacyBlock:
    name, meta = key
    if name.startswith(f"{MISSING_NS}:unknown_"):
        return LegacyBlock(int(name.rsplit("_", 1)[1]), meta)
    return LegacyBlock(m.by_name[name], meta)

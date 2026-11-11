#!/usr/bin/env python3
"""Executable reference for the S03 chunk spec (docs/specs/chunks-1.7.10.md).

NBT (types 0..=11, Java modified UTF-8, order-preserving), Anvil region files
(gzip/zlib only) and a LegacyChunk view over Sections using S02 LegacyBlock.
Not engine code: W04/W05 implement this in Rust and reproduce tests/test_anvil_1710.py.

    python tools/anvil_1710.py fixture OUT.mca   # write the synthetic S03 fixture
    python tools/anvil_1710.py check REGION.mca  # lossless round-trip of every chunk
"""
from __future__ import annotations

import gzip
import hashlib
import importlib.util
import struct
import sys
import zlib
from dataclasses import dataclass
from pathlib import Path

_spec = importlib.util.spec_from_file_location("legacy_blocks", Path(__file__).with_name("legacy_blocks.py"))
legacy_blocks = importlib.util.module_from_spec(_spec)
sys.modules.setdefault("legacy_blocks", legacy_blocks)
_spec.loader.exec_module(legacy_blocks)
LegacyBlock = legacy_blocks.LegacyBlock
nibble_get, nibble_set = legacy_blocks.nibble_get, legacy_blocks.nibble_set

# --------------------------------------------------------------------------- NBT
END, BYTE, SHORT, INT, LONG, FLOAT, DOUBLE, BYTE_ARRAY, STRING, LIST, COMPOUND, INT_ARRAY = range(12)
LONG_ARRAY = 12  # not in 1.7.10


class NbtError(ValueError):
    pass


@dataclass
class Tag:
    type: int
    value: object  # Compound: dict[str, Tag]; List: (elem_type, list[Tag]); ByteArray: bytearray

    def __getitem__(self, key: str) -> "Tag":
        return self.value[key]

    def get(self, key: str):
        return self.value.get(key)


def mutf8_encode(s: str) -> bytes:
    out = bytearray()
    units = s.encode("utf-16-be", "surrogatepass")
    for k in range(0, len(units), 2):
        c = units[k] << 8 | units[k + 1]
        if 0x0001 <= c <= 0x007F:
            out.append(c)
        elif c <= 0x07FF:
            out += bytes([0xC0 | c >> 6, 0x80 | c & 0x3F])
        else:
            out += bytes([0xE0 | c >> 12, 0x80 | c >> 6 & 0x3F, 0x80 | c & 0x3F])
    if len(out) > 0xFFFF:
        raise NbtError("string longer than 65535 bytes")
    return bytes(out)


def mutf8_decode(b: bytes) -> str:
    units, i = [], 0
    while i < len(b):
        c = b[i]
        if c < 0x80 and c != 0:
            units.append(c); i += 1
        elif c & 0xE0 == 0xC0 and i + 1 < len(b) and b[i + 1] & 0xC0 == 0x80:
            units.append((c & 0x1F) << 6 | b[i + 1] & 0x3F); i += 2
        elif c & 0xF0 == 0xE0 and i + 2 < len(b) and b[i + 1] & 0xC0 == 0x80 and b[i + 2] & 0xC0 == 0x80:
            units.append((c & 0x0F) << 12 | (b[i + 1] & 0x3F) << 6 | b[i + 2] & 0x3F); i += 3
        else:
            raise NbtError(f"invalid modified UTF-8 at byte {i}")
    return b"".join(u.to_bytes(2, "big") for u in units).decode("utf-16-be", "surrogatepass")


_SCALAR = {BYTE: ">b", SHORT: ">h", INT: ">i", LONG: ">q", FLOAT: ">f", DOUBLE: ">d"}


class _Reader:
    def __init__(self, data: bytes):
        self.d, self.p = data, 0

    def take(self, n: int) -> bytes:
        if self.p + n > len(self.d):
            raise NbtError("unexpected end of NBT")
        b = self.d[self.p:self.p + n]
        self.p += n
        return b

    def unpack(self, fmt: str):
        return struct.unpack(fmt, self.take(struct.calcsize(fmt)))[0]

    def string(self) -> str:
        return mutf8_decode(self.take(self.unpack(">H")))

    def payload(self, t: int, depth: int = 0):
        if depth > 512:
            raise NbtError("NBT nested too deep")
        if t in _SCALAR:
            return self.unpack(_SCALAR[t])
        if t == BYTE_ARRAY:
            return bytearray(self.take(self._len()))
        if t == STRING:
            return self.string()
        if t == LIST:
            et, n = self.unpack(">b"), self._len()
            if et == LONG_ARRAY or not 0 <= et <= INT_ARRAY:
                raise NbtError(f"list of tag type {et} is not valid in 1.7.10")
            return et, [Tag(et, self.payload(et, depth + 1)) for _ in range(n)]
        if t == COMPOUND:
            out = {}
            while True:
                ct = self.unpack(">b")
                if ct == END:
                    return out
                self._check_type(ct)
                name = self.string()
                out[name] = Tag(ct, self.payload(ct, depth + 1))
        if t == INT_ARRAY:
            n = self._len()
            return list(struct.unpack(f">{n}i", self.take(4 * n)))
        raise NbtError(f"tag type {t} is not valid in 1.7.10")

    def _len(self) -> int:
        n = self.unpack(">i")
        if n < 0:
            raise NbtError("negative length")
        return n

    @staticmethod
    def _check_type(t: int) -> None:
        if t == LONG_ARRAY:
            raise NbtError("LongArray (12) does not exist in 1.7.10")
        if not 1 <= t <= INT_ARRAY:
            raise NbtError(f"tag type {t} is not valid in 1.7.10")


def nbt_decode(data: bytes) -> tuple[str, Tag]:
    r = _Reader(data)
    t = r.unpack(">b")
    if t != COMPOUND:
        raise NbtError("root tag must be a Compound")
    name = r.string()
    root = Tag(COMPOUND, r.payload(COMPOUND))
    if r.p != len(data):
        raise NbtError("trailing bytes after root tag")
    return name, root


def _write(out: bytearray, t: int, v) -> None:
    if t in _SCALAR:
        out += struct.pack(_SCALAR[t], v)
    elif t == BYTE_ARRAY:
        out += struct.pack(">i", len(v)) + bytes(v)
    elif t == STRING:
        b = mutf8_encode(v)
        out += struct.pack(">H", len(b)) + b
    elif t == LIST:
        et, items = v
        out += struct.pack(">bi", et, len(items))
        for item in items:
            if item.type != et:
                raise NbtError("list element type mismatch")
            _write(out, et, item.value)
    elif t == COMPOUND:
        for name, tag in v.items():
            _Reader._check_type(tag.type)
            out += struct.pack(">b", tag.type)
            _write(out, STRING, name)
            _write(out, tag.type, tag.value)
        out.append(END)
    elif t == INT_ARRAY:
        out += struct.pack(f">i{len(v)}i", len(v), *v)
    else:
        raise NbtError(f"tag type {t} is not valid in 1.7.10")


def nbt_encode(name: str, root: Tag) -> bytes:
    out = bytearray([COMPOUND])
    _write(out, STRING, name)
    _write(out, COMPOUND, root.value)
    return bytes(out)


# ------------------------------------------------------------------------ region
SECTOR = 4096
GZIP, ZLIB = 1, 2


class RegionError(ValueError):
    pass


def region_file_name(cx: int, cz: int) -> str:
    return f"r.{cx >> 5}.{cz >> 5}.mca"


def chunk_index(cx: int, cz: int) -> int:
    return (cx & 31) + (cz & 31) * 32


@dataclass
class ChunkBlob:
    compression: int
    nbt: bytes  # uncompressed
    timestamp: int = 0


def read_region(data: bytes) -> dict[int, ChunkBlob]:
    if len(data) < 2 * SECTOR:
        raise RegionError("region shorter than its header")
    out = {}
    for idx in range(1024):
        loc = struct.unpack_from(">I", data, idx * 4)[0]
        if loc == 0:
            continue
        start, count = loc >> 8, loc & 0xFF
        if start < 2 or count == 0 or (start + count) * SECTOR > len(data):
            raise RegionError(f"chunk {idx}: bad location {start}+{count}")
        length, comp = struct.unpack_from(">IB", data, start * SECTOR)
        if length < 1 or length + 4 > count * SECTOR:
            raise RegionError(f"chunk {idx}: bad length {length}")
        body = data[start * SECTOR + 5: start * SECTOR + 4 + length]
        if comp == GZIP:
            raw = gzip.decompress(body)
        elif comp == ZLIB:
            raw = zlib.decompress(body)
        else:
            raise RegionError(f"chunk {idx}: compression {comp} does not exist in 1.7.10")
        ts = struct.unpack_from(">I", data, SECTOR + idx * 4)[0]
        out[idx] = ChunkBlob(comp, raw, ts)
    return out


def write_region(chunks: dict[int, ChunkBlob]) -> bytes:
    header, stamps, body = bytearray(SECTOR), bytearray(SECTOR), bytearray()
    sector = 2
    for idx in sorted(chunks):
        c = chunks[idx]
        if c.compression == GZIP:
            packed = gzip.compress(c.nbt, mtime=0)
        elif c.compression == ZLIB:
            packed = zlib.compress(c.nbt)
        else:
            raise RegionError(f"compression {c.compression} is not written for 1.7.10")
        blob = struct.pack(">IB", len(packed) + 1, c.compression) + packed
        count = -(-len(blob) // SECTOR)
        if count > 255:
            raise RegionError(f"chunk {idx} needs {count} sectors, 1.7.10 allows 255")
        struct.pack_into(">I", header, idx * 4, sector << 8 | count)
        struct.pack_into(">I", stamps, idx * 4, c.timestamp)
        body += blob + bytes(count * SECTOR - len(blob))
        sector += count
    return bytes(header + stamps + body)


# ------------------------------------------------------------------------- chunk
SECTION_ARRAYS = {"Blocks": 4096, "Add": 2048, "Data": 2048, "BlockLight": 2048, "SkyLight": 2048}


def _b(v: int) -> Tag: return Tag(BYTE, v)
def _ba(n: int, fill: int = 0) -> Tag: return Tag(BYTE_ARRAY, bytearray([fill]) * n)


class LegacyChunk:
    """View over a chunk root Tag. Edits change the Tag in place; nothing else is recomputed."""

    def __init__(self, root: Tag, has_sky: bool = True):
        self.root, self.has_sky = root, has_sky
        level = root.get("Level")
        if level is None or level.type != COMPOUND:
            raise NbtError("chunk has no Level compound")
        if "DataVersion" in root.value:
            raise NbtError("DataVersion present: not a 1.7.10 chunk")
        self.level = level
        sections = level.get("Sections")
        if sections is None:
            sections = level.value["Sections"] = Tag(LIST, (COMPOUND, []))
        self._sections: dict[int, Tag] = {}
        for sec in sections.value[1]:
            y = sec["Y"].value
            if not 0 <= y <= 15:
                raise NbtError(f"section Y {y} out of 0..=15")
            if y in self._sections:
                raise NbtError(f"duplicate section Y {y}")
            for name, size in SECTION_ARRAYS.items():
                arr = sec.get(name)
                optional = name == "Add" or (name == "SkyLight" and not has_sky)
                if arr is None and optional:
                    continue
                if arr is None or arr.type != BYTE_ARRAY or len(arr.value) != size:
                    raise NbtError(f"section {y}: {name} must be ByteArray[{size}]")
            self._sections[y] = sec
        h = level.get("HeightMap")
        if h is not None and (h.type != INT_ARRAY or len(h.value) != 256):
            raise NbtError("HeightMap must be IntArray[256]")
        b = level.get("Biomes")
        if b is not None and (b.type != BYTE_ARRAY or len(b.value) != 256):
            raise NbtError("Biomes must be ByteArray[256]")

    @property
    def pos(self) -> tuple[int, int]:
        return self.level["xPos"].value, self.level["zPos"].value

    def section_ys(self) -> list[int]:
        return sorted(self._sections)

    @staticmethod
    def _i(x: int, y: int, z: int) -> int:
        if not (0 <= x < 16 and 0 <= y < 256 and 0 <= z < 16):
            raise ValueError(f"({x}, {y}, {z}) outside the chunk")
        return (y & 15) << 8 | z << 4 | x

    def block(self, x: int, y: int, z: int) -> LegacyBlock:
        i, sec = self._i(x, y, z), self._sections.get(y >> 4)
        if sec is None:
            return LegacyBlock(0, 0)
        add = sec.get("Add")
        return LegacyBlock.from_anvil(sec["Blocks"].value[i], nibble_get(add.value, i) if add else 0,
                                      nibble_get(sec["Data"].value, i))

    def set_block(self, x: int, y: int, z: int, block: LegacyBlock) -> None:
        i, sec = self._i(x, y, z), self._sections.get(y >> 4)
        if sec is None:
            if block.id == 0:
                return
            sec = self._new_section(y >> 4)
        low, high, meta = block.anvil()
        sec["Blocks"].value[i] = low
        add = sec.get("Add")
        if high and add is None:
            add = _ba(2048)
            items = list(sec.value.items())
            pos = [k for k, _ in items].index("Blocks") + 1
            sec.value.clear()
            sec.value.update(items[:pos] + [("Add", add)] + items[pos:])
        if add is not None:
            nibble_set(add.value, i, high)
        nibble_set(sec["Data"].value, i, meta)

    def _new_section(self, y: int) -> Tag:
        sec = Tag(COMPOUND, {"Y": _b(y), "Blocks": _ba(4096), "Data": _ba(2048),
                             "BlockLight": _ba(2048), "SkyLight": _ba(2048, 0xFF if self.has_sky else 0)})
        self.level["Sections"].value[1].append(sec)
        self._sections[y] = sec
        return sec

    def block_light(self, x: int, y: int, z: int) -> int:
        sec = self._sections.get(y >> 4)
        return nibble_get(sec["BlockLight"].value, self._i(x, y, z)) if sec else 0

    def sky_light(self, x: int, y: int, z: int) -> int:
        sec = self._sections.get(y >> 4)
        if sec is None or sec.get("SkyLight") is None:
            return 15 if self.has_sky and sec is None else 0
        return nibble_get(sec["SkyLight"].value, self._i(x, y, z))

    def biome(self, x: int, z: int) -> int:
        b = self.level.get("Biomes")
        return 255 if b is None else b.value[z << 4 | x]

    def height(self, x: int, z: int) -> int:
        return self.level["HeightMap"].value[z << 4 | x]

    def tile_ticks(self) -> list[dict]:
        t = self.level.get("TileTicks")
        if t is None:
            return []
        out = []
        for e in t.value[1]:
            v = {k: e[k].value for k in ("i", "x", "y", "z", "t")}
            v["p"] = e.get("p").value if e.get("p") else 0
            out.append(v)
        return out


# ----------------------------------------------------------------------- fixture
FIXTURE_POS = (3, -2)


def fixture_root() -> Tag:
    """Deterministic synthetic chunk: no Mojang data, covers every case of spec section 7."""
    cx, cz = FIXTURE_POS
    secs = []
    for y in (4, 0, 1):  # out of order, section 2..15 missing
        sec = {"Y": _b(y), "Blocks": _ba(4096), "Data": _ba(2048), "BlockLight": _ba(2048), "SkyLight": _ba(2048, 0xFF)}
        if y == 4:
            sec = dict(list(sec.items())[:2] + [("Add", _ba(2048))] + list(sec.items())[2:])
        secs.append(Tag(COMPOUND, sec))
    level = {
        "xPos": Tag(INT, cx), "zPos": Tag(INT, cz),
        "LastUpdate": Tag(LONG, 123456789), "TerrainPopulated": _b(1), "LightPopulated": _b(1), "V": _b(1),
        "InhabitedTime": Tag(LONG, 4242),
        "HeightMap": Tag(INT_ARRAY, [(x * 7 + z * 3) % 256 for z in range(16) for x in range(16)]),
        "Biomes": Tag(BYTE_ARRAY, bytearray([255 if (z + x) % 5 == 0 else (z * 16 + x) % 40 for z in range(16) for x in range(16)])),
        "Sections": Tag(LIST, (COMPOUND, secs)),
        "Entities": Tag(LIST, (END, [])),
        "TileEntities": Tag(LIST, (COMPOUND, [Tag(COMPOUND, {"id": Tag(STRING, "Chest"), "x": Tag(INT, cx * 16 + 1),
                                                             "y": Tag(INT, 5), "z": Tag(INT, cz * 16 + 2),
                                                             "Items": Tag(LIST, (END, []))})])),
        "TileTicks": Tag(LIST, (COMPOUND, [Tag(COMPOUND, {"i": Tag(INT, 8), "x": Tag(INT, cx * 16), "y": Tag(INT, 64),
                                                          "z": Tag(INT, cz * 16), "t": Tag(INT, 5), "p": Tag(INT, 0)})])),
        "ntm:Radiation": Tag(COMPOUND, {"level": Tag(FLOAT, 0.5), "note": Tag(STRING, "nul\u0000 and \U0001F600")}),
    }
    root = Tag(COMPOUND, {"Level": Tag(COMPOUND, level), "ntm:ChunkData": Tag(COMPOUND, {})})
    ch = LegacyChunk(root)
    for x in range(16):
        ch.set_block(x, 0, 0, LegacyBlock(7))  # bedrock row
    for m in range(16):
        ch.set_block(m, 1, 1, LegacyBlock(35, m))  # all wool colours
        i = LegacyChunk._i(m, 17, 3)
        nibble_set(ch._sections[1]["BlockLight"].value, i, m)
        nibble_set(ch._sections[1]["SkyLight"].value, i, 15 - m)
    ch.set_block(5, 70, 9, LegacyBlock(1204, 2))  # needs Add, in section 4
    return root


def fixture_nbt() -> bytes:
    return nbt_encode("", fixture_root())


def round_trip(region: bytes) -> list[str]:
    """Problems found when re-encoding every chunk of a region (empty list = lossless)."""
    problems = []
    for idx, blob in read_region(region).items():
        name, root = nbt_decode(blob.nbt)
        LegacyChunk(root)
        if nbt_encode(name, root) != blob.nbt:
            problems.append(f"chunk {idx}: NBT differs after re-encoding")
    again = read_region(write_region(read_region(region)))
    for idx, blob in read_region(region).items():
        if again[idx].nbt != blob.nbt:
            problems.append(f"chunk {idx}: differs after region rewrite")
    return problems


def main(argv: list[str]) -> int:
    if len(argv) == 2 and argv[0] == "fixture":
        out = Path(argv[1])
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_bytes(write_region({chunk_index(*FIXTURE_POS): ChunkBlob(ZLIB, fixture_nbt())}))
        print(f"{out}  nbt sha256 {hashlib.sha256(fixture_nbt()).hexdigest()}")
        return 0
    if len(argv) == 2 and argv[0] == "check":
        data = Path(argv[1]).read_bytes()
        problems = round_trip(data)
        print(f"{len(read_region(data))} chunks, " + ("lossless" if not problems else f"{len(problems)} problems"))
        for p in problems:
            print(" ", p)
        return 0 if not problems else 1
    print(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

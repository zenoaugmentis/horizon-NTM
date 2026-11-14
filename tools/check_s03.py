"""Read-only region scanner for trusted local S03 reference saves.

Usage: py tools/check_s03.py PATH_TO_REGION_DIRECTORY
Writes JSON to stdout and exits nonzero on a failed check or missing files.
"""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import struct
import sys
import zlib

from s03_codec import decode, encode


def require(condition, message):
    if not condition:
        raise ValueError(message)


def inspect_region(path):
    data = path.read_bytes()
    result = {"file": path.name, "size": len(data),
              "sha256": hashlib.sha256(data).hexdigest(),
              "pass_chunks": 0, "errors": []}
    counters = {name: Counter() for name in
                ("sky_sections", "add_sections", "root_tags", "level_tags",
                 "section_tags", "tick_field_types", "compressions")}
    ticks_total = 0
    try:
        require(len(data) >= 8192 and len(data) % 4096 == 0,
                "Region size must be a multiple of 4096 and at least 8192")
        _, rx, rz, suffix = path.name.split(".")
        require(suffix == "mca", "Expected .mca")
        rx, rz = int(rx), int(rz)
    except Exception as exc:
        result["errors"].append(str(exc))
        return result

    used = {0, 1}
    for slot in range(1024):
        location = struct.unpack_from(">I", data, slot * 4)[0]
        if location == 0:
            continue
        try:
            start, count = location >> 8, location & 255
            require(start >= 2 and count > 0, "Invalid allocation")
            require((start + count) * 4096 <= len(data), "Allocation outside file")
            occupied = set(range(start, start + count))
            require(not occupied.intersection(used), "Overlapping allocations")
            used.update(occupied)
            offset = start * 4096
            length, compression = struct.unpack_from(">IB", data, offset)
            require(1 <= length <= count * 4096 - 4, "Invalid length")
            require(compression in (1, 2), "Unsupported legacy compression")
            body = data[offset + 5:offset + 4 + length]
            decoder = zlib.decompressobj(
                16 + zlib.MAX_WBITS if compression == 1 else zlib.MAX_WBITS)
            raw = decoder.decompress(body) + decoder.flush()
            require(decoder.eof and not decoder.unused_data, "Invalid compressed stream")
            name, root = decode(raw)
            require(encode(name, root) == raw, "NBT round-trip differs")
            require(root.get("Level", (None,))[0] == 10, "Level must be Compound")
            level = root["Level"][1]
            for key in ("xPos", "zPos"):
                require(level.get(key, (None,))[0] == 3, key + " must be Int")
            expected = (rx * 32 + slot % 32, rz * 32 + slot // 32)
            require((level["xPos"][1], level["zPos"][1]) == expected,
                    "Chunk coordinate mismatch")
            require(level.get("Sections", (None,))[0] == 9, "Sections must be List")
            element_type, sections = level["Sections"][1]
            require(element_type == 10 or (element_type == 0 and not sections),
                    "Sections must contain Compounds")
            local = {key: Counter() for key in counters}
            local["compressions"][str(compression)] += 1
            local["root_tags"].update(root.keys())
            local["level_tags"].update(level.keys())
            ys = set()
            for section in sections:
                require(section.get("Y", (None,))[0] == 1, "Y must be Byte")
                y = section["Y"][1]
                require(0 <= y <= 15 and y not in ys, "Invalid or duplicate section Y")
                ys.add(y)
                local["section_tags"].update(section.keys())
                for key, size in (("Blocks", 4096), ("Data", 2048),
                                  ("BlockLight", 2048), ("SkyLight", 2048),
                                  ("Add", 2048)):
                    tag = section.get(key)
                    if tag is None:
                        require(key in ("SkyLight", "Add"), "Missing " + key)
                        if key == "SkyLight":
                            local["sky_sections"]["absent"] += 1
                        if key == "Add":
                            local["add_sections"]["absent"] += 1
                        continue
                    require(tag[0] == 7 and len(tag[1]) == size, "Invalid " + key)
                    if key in ("SkyLight", "Add"):
                        counter = "sky_sections" if key == "SkyLight" else "add_sections"
                        local[counter]["nonzero" if any(tag[1]) else "all_zero"] += 1
            for key, kind, size in (("HeightMap", 11, 256), ("Biomes", 7, 256)):
                tag = level.get(key)
                if tag is not None:
                    require(tag[0] == kind and len(tag[1]) == size, "Invalid " + key)
            local_ticks = 0
            ticks = level.get("TileTicks")
            if ticks is not None:
                require(ticks[0] == 9, "TileTicks must be List")
                element_type, entries = ticks[1]
                require(element_type == 10 or (element_type == 0 and not entries),
                        "TileTicks must contain Compounds")
                local_ticks = len(entries)
                for entry in entries:
                    for key, (kind, _) in entry.items():
                        local["tick_field_types"][f"{key}:{kind}"] += 1
            for key in counters:
                counters[key].update(local[key])
            ticks_total += local_ticks
            result["pass_chunks"] += 1
        except Exception as exc:
            result["errors"].append(f"slot {slot}: {type(exc).__name__}: {exc}")
    result.update({key: dict(value) for key, value in counters.items()})
    result["tick_entries"] = ticks_total
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", type=Path)
    args = parser.parse_args()
    files = sorted(args.directory.glob("r.*.*.mca")) if args.directory.is_dir() else []
    if not files:
        print(json.dumps({"error": "No region files in the specified directory"}))
        return 2
    results = [inspect_region(path) for path in files]
    report = {"regions": results,
              "pass_chunks": sum(r["pass_chunks"] for r in results),
              "errors": sum(len(r["errors"]) for r in results)}
    print(json.dumps(report, indent=2, ensure_ascii=True))
    return 1 if report["errors"] else 0


if __name__ == "__main__":
    sys.exit(main())

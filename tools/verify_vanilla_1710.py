#!/usr/bin/env python3
"""Check a local Minecraft 1.7.10 / Forge install against the S01 reference.

Reference values: docs/specs/versions.md, section 2. Change both together.

The script only reads files and computes SHA-1 and size. It never copies,
unpacks or uploads anything, and the JSON report holds no user paths.

    python tools/verify_vanilla_1710.py --game-dir PATH [--server-jar PATH]
        [--forge-universal PATH] [--report .local/s01-report.json]

Exit code: 0 if every given component matches, 1 otherwise.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from dataclasses import asdict, dataclass
from pathlib import Path


@dataclass(frozen=True)
class Ref:
    sha1: str
    size: int | None = None


# Mojang version JSON 1.7.10 (piston-meta ed5d8789...) and Forge maven .sha1 files.
REFERENCE: dict[str, Ref] = {
    "client_jar": Ref("e80d9b3bf5085002218d4be59e668bac718abbc6", 5256245),
    "version_json": Ref("ed5d8789ed29872ea2ef1c348302b0c55e3f3468"),
    "asset_index": Ref("1863782e33ce7b584fc45b037325a1964e095d3e", 72996),
    "server_jar": Ref("952438ac4e01b4d115c5fc38f891710c4941df29", 9605030),
    "forge_universal": Ref("25fd97f72beca728112256938e03e8105b1b78cc"),
}

# Files inside a launcher game directory.
GAME_DIR_FILES = {
    "client_jar": Path("versions/1.7.10/1.7.10.jar"),
    "version_json": Path("versions/1.7.10/1.7.10.json"),
    "asset_index": Path("assets/indexes/1.7.10.json"),
}

OK, MISMATCH, MISSING, SKIPPED = "OK", "MISMATCH", "MISSING", "SKIPPED"


@dataclass
class Result:
    component: str
    status: str
    sha1: str | None = None
    size: int | None = None
    expected_sha1: str | None = None
    note: str = ""


def sha1_of(path: Path) -> str:
    h = hashlib.sha1()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def check(component: str, path: Path | None, reference: dict[str, Ref] | None = None) -> Result:
    ref = (reference or REFERENCE)[component]
    if path is None:
        return Result(component, SKIPPED, expected_sha1=ref.sha1)
    if not path.is_file():
        return Result(component, MISSING, expected_sha1=ref.sha1, note="file not found")
    digest, size = sha1_of(path), path.stat().st_size
    status = OK if digest == ref.sha1 and (ref.size is None or size == ref.size) else MISMATCH
    note = ""
    if status == MISMATCH and digest == ref.sha1:
        note = f"size {size} != {ref.size}"
    return Result(component, status, digest, size, ref.sha1, note)


def collect(game_dir: Path | None, server_jar: Path | None, forge_universal: Path | None,
            reference: dict[str, Ref] | None = None) -> list[Result]:
    results = [
        check(name, game_dir / rel if game_dir else None, reference)
        for name, rel in GAME_DIR_FILES.items()
    ]
    results.append(check("server_jar", server_jar, reference))
    results.append(check("forge_universal", forge_universal, reference))
    return results


def passed(results: list[Result]) -> bool:
    return all(r.status in (OK, SKIPPED) for r in results) and any(r.status == OK for r in results)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--game-dir", type=Path, help="launcher game directory with versions/1.7.10")
    p.add_argument("--server-jar", type=Path, help="minecraft_server.1.7.10.jar")
    p.add_argument("--forge-universal", type=Path, help="Forge 10.13.4.1614 universal jar")
    p.add_argument("--report", type=Path, help="write a JSON report (hashes only) here")
    a = p.parse_args(argv)
    if not (a.game_dir or a.server_jar or a.forge_universal):
        p.error("give at least one of --game-dir, --server-jar, --forge-universal")

    results = collect(a.game_dir, a.server_jar, a.forge_universal)
    for r in results:
        line = f"{r.component:<16} {r.status:<9} {r.sha1 or '-'}"
        print(line + (f"  ({r.note})" if r.note else ""))
    ok = passed(results)
    print("RESULT:", "OK" if ok else "FAIL")
    if a.report:
        a.report.parent.mkdir(parents=True, exist_ok=True)
        a.report.write_text(
            json.dumps({"reference": "S01", "ok": ok, "results": [asdict(r) for r in results]}, indent=2),
            encoding="utf-8",
        )
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())

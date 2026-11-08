#!/usr/bin/env python3
"""Check a local Minecraft 1.7.10 (+ Forge) install against the reference (S01).

Reads the player's own install, never downloads or copies game files, and writes
only hashes and version facts: docs/specs/versions.md, section "Local check".

    python tools/verify_vanilla_1710.py                        # default .minecraft
    python tools/verify_vanilla_1710.py --minecraft-dir D:/mc  # another launcher dir
    python tools/verify_vanilla_1710.py --client-jar path/to/minecraft-1.7.10-client.jar  # Prism/MultiMC
    python tools/verify_vanilla_1710.py --server-jar .local/reference/1.7.10/server.jar
    python tools/verify_vanilla_1710.py --report .local/reference/1.7.10/report.json

Exit code 0 = the client (and server, if given) match the reference.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from pathlib import Path

VERSION = "1.7.10"
# SHA-1 of Mojang's 1.7.10 client.jar: the object name in its download URL
# (piston-data.mojang.com/v1/objects/<sha1>/client.jar) and `downloads.client.sha1` in 1.7.10.json.
CLIENT_SHA1 = "e80d9b3bf5085002218d4be59e668bac718abbc6"
# SHA-1 of Mojang's 1.7.10.json (piston-meta.mojang.com/v1/packages/<sha1>/1.7.10.json).
VERSION_JSON_SHA1 = "2e818dc89e364c7efcfa54bec7e873c5f00b3840"
FORGE_REFERENCE = "10.13.4.1614"
FORGE_ALSO_SEEN = {"10.13.4.1558": "recommended build"}


def sha1(path: Path) -> str:
    h = hashlib.sha1()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def default_minecraft_dir() -> Path:
    if sys.platform.startswith("win"):
        return Path(os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming")) / ".minecraft"
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / "minecraft"
    return Path.home() / ".minecraft"


def find_forge(mc_dir: Path) -> list[dict]:
    """Forge 1.7.10 installs found under libraries/, with their hashes."""
    found = []
    base = mc_dir / "libraries" / "net" / "minecraftforge" / "forge"
    if not base.is_dir():
        return found
    for d in sorted(base.glob(f"{VERSION}-*")):
        build = d.name.split("-")[1] if d.name.count("-") >= 1 else d.name
        for jar in sorted(d.glob("*.jar")):
            found.append({
                "build": build,
                "file": jar.name,
                "sha1": sha1(jar),
                "reference": build == FORGE_REFERENCE,
                "note": FORGE_ALSO_SEEN.get(build, ""),
            })
    return found


def check(args) -> tuple[dict, bool]:
    mc_dir = Path(args.minecraft_dir) if args.minecraft_dir else default_minecraft_dir()
    report: dict = {"version": VERSION, "minecraft_dir": str(mc_dir), "checks": []}
    ok = True

    def add(name: str, status: str, **extra):
        nonlocal ok
        report["checks"].append({"check": name, "status": status, **extra})
        if status == "FAIL":
            ok = False

    version_json = mc_dir / "versions" / VERSION / f"{VERSION}.json"
    expected_client = CLIENT_SHA1
    expected_server = None
    if version_json.is_file():
        meta = json.loads(version_json.read_text(encoding="utf-8"))
        downloads = meta.get("downloads", {})
        json_client = downloads.get("client", {}).get("sha1")
        expected_server = downloads.get("server", {}).get("sha1")
        report["java_version"] = meta.get("javaVersion")
        report["server_sha1_from_json"] = expected_server
        add("version json sha1", "OK" if sha1(version_json) == VERSION_JSON_SHA1 else "WARN",
            note="the launcher may rewrite this file; a mismatch alone is not a failure")
        if json_client and json_client != CLIENT_SHA1:
            add("client sha1 in json", "FAIL", json=json_client, reference=CLIENT_SHA1)
    else:
        add("version json", "MISSING", path=str(version_json),
            note="run 1.7.10 once in the official launcher, or pass --client-jar")

    client = Path(args.client_jar) if args.client_jar else mc_dir / "versions" / VERSION / f"{VERSION}.jar"
    if client.is_file():
        got = sha1(client)
        add("client jar", "OK" if got == expected_client else "FAIL", sha1=got, reference=expected_client)
    else:
        add("client jar", "FAIL", path=str(client), note="not found")

    if args.server_jar:
        server = Path(args.server_jar)
        if not server.is_file():
            add("server jar", "FAIL", path=str(server), note="not found")
        elif expected_server is None:
            add("server jar", "WARN", sha1=sha1(server),
                note="no 1.7.10.json to compare with; share this hash in the PR instead")
        else:
            got = sha1(server)
            add("server jar", "OK" if got == expected_server else "FAIL", sha1=got, reference=expected_server)

    forge = find_forge(mc_dir)
    report["forge"] = forge
    if not forge:
        add("forge", "MISSING", note=f"install Forge {FORGE_REFERENCE} in a separate instance (versions.md)")
    elif not any(f["reference"] for f in forge):
        add("forge", "WARN", note=f"reference build {FORGE_REFERENCE} not found")
    else:
        add("forge", "OK", build=FORGE_REFERENCE)
    return report, ok


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--minecraft-dir", help="launcher directory (default: the OS's .minecraft)")
    p.add_argument("--client-jar", help="path to the 1.7.10 client jar (Prism/MultiMC layouts)")
    p.add_argument("--server-jar", help="path to minecraft_server.1.7.10.jar")
    p.add_argument("--report", help="write the JSON report here (keep it under .local/)")
    args = p.parse_args(argv)
    report, ok = check(args)
    for c in report["checks"]:
        extra = ", ".join(f"{k}={v}" for k, v in c.items() if k not in ("check", "status"))
        print(f"[{c['status']:<7}] {c['check']}" + (f": {extra}" if extra else ""))
    for f in report.get("forge", []):
        print(f"          forge {f['build']} {f['file']} sha1={f['sha1']}")
    if args.report:
        out = Path(args.report)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        print(f"report: {out}")
    print("RESULT:", "OK" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())

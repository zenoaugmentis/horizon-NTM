#!/usr/bin/env python3
"""Move issues on the GitHub Project board "Horizon-NTM Development".

Requires `gh` authenticated with the `project` scope:
    gh auth refresh -s project

Usage:
    python scripts/board.py status 5 "In Progress"   # issue #5 -> In Progress
    python scripts/board.py status 5 Done
    python scripts/board.py show 5                    # current status of issue #5
    python scripts/board.py list                      # all items with status
    python scripts/board.py options                   # available Status values

Status values are looked up by name, so new columns added in the Project UI
(e.g. "In Review", "Blocked") work without changing this script.
An issue that is not on the board yet is added to it first.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys

OWNER = "zenoaugmentis"
REPO = "zenoaugmentis/horizon-NTM"
PROJECT_NUMBER = "1"
STATUS_FIELD = "Status"
ITEM_LIMIT = "1000"  # gh defaults to 30, which silently truncates the board


def gh(*args: str) -> str:
    try:
        out = subprocess.run(
            ["gh", *args], check=True, capture_output=True, text=True, encoding="utf-8"
        )
    except FileNotFoundError:
        sys.exit("gh not found: install GitHub CLI (winget install --id GitHub.cli)")
    except subprocess.CalledProcessError as e:
        msg = (e.stderr or e.stdout or "").strip()
        if "project" in msg and ("scope" in msg or "INSUFFICIENT_SCOPES" in msg):
            msg += "\nHint: run `gh auth refresh -s project`"
        sys.exit(f"gh {' '.join(args)} failed:\n{msg}")
    return out.stdout


def gh_json(*args: str):
    return json.loads(gh(*args))


def project_id() -> str:
    return gh_json("project", "view", PROJECT_NUMBER, "--owner", OWNER, "--format", "json")["id"]


def status_field() -> tuple[str, dict[str, str]]:
    fields = gh_json("project", "field-list", PROJECT_NUMBER, "--owner", OWNER, "--format", "json")
    for f in fields["fields"]:
        if f["name"] == STATUS_FIELD:
            return f["id"], {o["name"]: o["id"] for o in f.get("options", [])}
    sys.exit(f'Field "{STATUS_FIELD}" not found in project {PROJECT_NUMBER}')


def items() -> list[dict]:
    data = gh_json(
        "project", "item-list", PROJECT_NUMBER, "--owner", OWNER, "--format", "json", "-L", ITEM_LIMIT
    )
    return data["items"]


def find_item(issue: int, all_items: list[dict]) -> dict | None:
    for it in all_items:
        c = it.get("content") or {}
        if c.get("number") == issue and REPO.lower() in (c.get("repository") or "").lower():
            return it
    return None


def resolve_option(name: str, options: dict[str, str]) -> tuple[str, str]:
    for opt_name, opt_id in options.items():
        if opt_name.casefold() == name.casefold():
            return opt_name, opt_id
    sys.exit(f'Unknown status "{name}". Available: {", ".join(options)}')


def cmd_status(issue: int, status: str) -> None:
    field_id, options = status_field()
    opt_name, opt_id = resolve_option(status, options)
    item = find_item(issue, items())
    if item is None:
        url = f"https://github.com/{REPO}/issues/{issue}"
        item = gh_json("project", "item-add", PROJECT_NUMBER, "--owner", OWNER, "--url", url, "--format", "json")
        print(f"#{issue} added to the board")
    gh(
        "project", "item-edit",
        "--project-id", project_id(),
        "--id", item["id"],
        "--field-id", field_id,
        "--single-select-option-id", opt_id,
    )
    print(f"#{issue}: {item.get('status') or '-'} -> {opt_name}")


def cmd_show(issue: int) -> None:
    item = find_item(issue, items())
    if item is None:
        sys.exit(f"#{issue} is not on the board")
    print(f"#{issue} {item['title']}: {item.get('status') or '-'}")


def cmd_list() -> None:
    rows = []
    for it in items():
        c = it.get("content") or {}
        rows.append((c.get("number") or 0, it.get("status") or "-", it["title"]))
    for num, status, title in sorted(rows):
        print(f"#{num:<4} {status:<12} {title}")


def cmd_options() -> None:
    _, options = status_field()
    print("\n".join(options))


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("status", help="set Status of an issue")
    s.add_argument("issue", type=int)
    s.add_argument("status")
    sh = sub.add_parser("show", help="show Status of an issue")
    sh.add_argument("issue", type=int)
    sub.add_parser("list", help="list all board items")
    sub.add_parser("options", help="list Status values")
    a = p.parse_args()
    if a.cmd == "status":
        cmd_status(a.issue, a.status)
    elif a.cmd == "show":
        cmd_show(a.issue)
    elif a.cmd == "list":
        cmd_list()
    else:
        cmd_options()


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Print a page of the translation work list.

Each entry is prefixed with ###<id>|<chars>. The id is a content hash, so written
translations stay bound to their paragraph even if a later capture reorders segments.
Untranslatable text is never listed.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import read_jsonl, text_id  # noqa: E402


def main() -> int:
    if not sys.stdout.isatty():
        sys.stdout.reconfigure(encoding="utf-8", errors="backslashreplace")
    ap = argparse.ArgumentParser()
    ap.add_argument("--work", required=True)
    ap.add_argument("--start", type=int, default=0)
    ap.add_argument("--count", type=int, default=30)
    ap.add_argument("--ids", default=None,
                    help="comma separated content ids instead of a range")
    args = ap.parse_args()

    work = Path(args.work).resolve()
    todo = read_jsonl(work / "todo.json")
    if not todo:
        print(f"[show] no todo.json in {work}; run prepare.py first")
        return 2

    by_id = {(r.get("id") or text_id(r["text"])): r for r in todo}

    if args.ids:
        picked = [by_id[i] for i in (x.strip() for x in args.ids.split(",")) if i in by_id]
    else:
        picked = todo[args.start:args.start + args.count]

    for it in picked:
        sid = it.get("id") or text_id(it["text"])
        print(f"###{sid}|{len(it['text'])}")
        print(it["text"])
        print()

    if args.ids:
        print(f"--- showed {len(picked)} of {len(todo)} ---")
    else:
        end = min(args.start + len(picked), len(todo))
        print(f"--- {args.start}..{end - 1} of {len(todo)} ---")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Cross-paper translation memory.

Papers share a lot of boilerplate: licence footers, "References", table captions,
publisher colophons. Translating them again for every paper wastes effort, so every
accepted translation is folded into one shared store and reused automatically.

Layout
------
The store is a single JSONL file keyed by the exact source text:

    {"text": "<english>", "translation": "<chinese>", "hits": 3}

Location: $MT_MEMORY, else <skill>/memory.jsonl. Paper-local translations still win,
so a one-off override in a work dir never has to fight the shared store.

Commands
--------
  merge   fold a work dir's translations.jsonl into the store (default)
  stat    show how many entries exist and the best-reused ones
  lookup  print the stored translation for a text given on stdin
  prune   drop entries never reused and older than N days
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import read_jsonl, write_jsonl_atomic  # noqa: E402

HERE = Path(__file__).resolve().parent
SKILL = HERE.parent
DEFAULT_MEMORY = SKILL / "memory.jsonl"


def memory_path() -> Path:
    raw = os.environ.get("MT_MEMORY")
    return Path(raw) if raw else DEFAULT_MEMORY


def load(path: Path) -> dict[str, dict]:
    store: dict[str, dict] = {}
    if not path.exists():
        return store
    with path.open(encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                continue
            text = rec.get("text")
            trans = rec.get("translation")
            if isinstance(text, str) and isinstance(trans, str):
                store[text] = {
                    "text": text,
                    "translation": trans,
                    "hits": int(rec.get("hits", 0)),
                    "ts": rec.get("ts", int(time.time())),
                }
    return store


def save(path: Path, store: dict[str, dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with tmp.open("w", encoding="utf-8") as fh:
        for rec in store.values():
            fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
    os.replace(tmp, path)


def cmd_merge(args: argparse.Namespace) -> int:
    store = load(memory_path())
    work = Path(args.work).resolve()
    src = work / "translations.jsonl"
    if not src.exists():
        print(f"[memory] no translations.jsonl in {work}")
        return 2

    added = updated = 0
    with src.open(encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                continue
            text, trans = rec.get("text"), rec.get("translation")
            if not isinstance(text, str) or not isinstance(trans, str):
                continue
            # Never let the shared store absorb a paragraph that still looks English.
            if not any("\u4e00" <= ch <= "\u9fff" for ch in trans):
                continue
            if text in store:
                if store[text]["translation"] != trans:
                    store[text]["translation"] = trans
                    store[text]["ts"] = int(time.time())
                    updated += 1
            else:
                store[text] = {"text": text, "translation": trans,
                               "hits": 0, "ts": int(time.time())}
                added += 1

    save(memory_path(), store)
    print(f"[memory] merged {work.name}: +{added} new, {updated} updated, "
          f"total {len(store)} -> {memory_path()}")
    return 0


def cmd_stat(args: argparse.Namespace) -> int:
    store = load(memory_path())
    print(f"[memory] {len(store)} entries at {memory_path()}")
    reused = sorted(store.values(), key=lambda r: -r["hits"])[:10]
    if reused and reused[0]["hits"]:
        print("[memory] most reused:")
        for rec in reused:
            if rec["hits"]:
                print(f"  hits={rec['hits']:<3} {rec['text'][:60]!r}")
    return 0


def cmd_lookup(args: argparse.Namespace) -> int:
    store = load(memory_path())
    text = sys.stdin.read()
    rec = store.get(text)
    sys.stdout.write(rec["translation"] if rec else text)
    return 0


def cmd_prune(args: argparse.Namespace) -> int:
    store = load(memory_path())
    cutoff = int(time.time()) - args.days * 86400
    keep = {k: v for k, v in store.items()
            if v["hits"] > 0 or v.get("ts", 0) >= cutoff}
    removed = len(store) - len(keep)
    save(memory_path(), keep)
    print(f"[memory] pruned {removed} entries, {len(keep)} remain")
    return 0


def cmd_count(args: argparse.Namespace) -> int:
    """Report how many planned segments in a work dir are already remembered.

    Called before translating so the work list can be trimmed to genuinely new
    text. This is what makes the memory pay off in saved tokens.
    """
    store = load(memory_path())
    work = Path(args.work).resolve()
    todo_path = work / "todo.json"
    if not todo_path.exists():
        print(f"[memory] no todo.json in {work}")
        return 2

    todo = read_jsonl(todo_path)
    covered = [it for it in todo if it["text"] in store]
    new = [it for it in todo if it["text"] not in store]
    saved = sum(it["len"] for it in covered)

    print(f"[memory] planned={len(todo)} already-known={len(covered)} new={len(new)}")
    print(f"[memory] reusable text = {saved} chars "
          f"({saved / max(sum(it['len'] for it in todo), 1):.1%} of this paper)")
    if args.write:
        path = work / "todo_new.json"
        write_jsonl_atomic(path, new)
        print(f"[memory] wrote {path} ({len(new)} segments still to translate)")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description="cross-paper translation memory")
    sub = ap.add_subparsers(dest="cmd")
    m = sub.add_parser("merge", help="fold a work dir into the memory")
    m.add_argument("--work", required=True)
    sub.add_parser("stat", help="show memory statistics")
    sub.add_parser("lookup", help="translate stdin from memory")
    p = sub.add_parser("prune", help="drop unused old entries")
    p.add_argument("--days", type=int, default=90)
    c = sub.add_parser("count", help="how much of a work dir is already remembered")
    c.add_argument("--work", required=True)
    c.add_argument("--write", action="store_true",
                   help="write todo_new.json with only the untranslated segments")
    args = ap.parse_args()

    if args.cmd in (None, "merge"):
        if not getattr(args, "work", None):
            print("[memory] --work is required for merge")
            return 2
        return cmd_merge(args)
    if args.cmd == "stat":
        return cmd_stat(args)
    if args.cmd == "lookup":
        return cmd_lookup(args)
    if args.cmd == "prune":
        return cmd_prune(args)
    if args.cmd == "count":
        return cmd_count(args)
    ap.print_help()
    return 2


if __name__ == "__main__":
    raise SystemExit(main())

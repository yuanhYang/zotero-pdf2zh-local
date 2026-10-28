#!/usr/bin/env python3
"""Classify captured segments and keep only what needs translating.

Every kept segment carries a content id (`id`), so translations survive
reordering between capture runs.

Skipped segments are written to `skipped.jsonl` with their reason, so a
misclassification can be inspected and restored: `--restore <id[,id...]>` moves
them back into the work list. Use `--skip-ids` for visually identified figure text.

Writes <work>/todo.json and <work>/skipped.jsonl. Dropped text is never printed.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import read_jsonl, text_id, write_jsonl_atomic  # noqa: E402

LATIN = re.compile(r"[A-Za-z]")
REF_HINT = re.compile(r"vol\.\s*\d+|Proceedings of|pp\.\s*\d+|Springer|IEEE Access")
NUMBERED_REFERENCE = re.compile(r"^\s*\[\d+\]\s*\S")
REFERENCE_YEAR = re.compile(r"\b(?:19|20)\d{2}\b")
REFERENCE_DETAIL = re.compile(
    r"\b(?:vol\.|pp\.|doi\b|proceedings\b|journal\b|conference\b|IEEE\b|et al\.)"
    r"|\b[A-Z]\.\s*(?:[A-Z]\.\s*)?[A-Z][a-z]+"
    r"|\b[A-Z][A-Za-z'-]+,\s*(?:[A-Z]\.\s*)+", re.IGNORECASE)
REFERENCE_HEADING = re.compile(r"^\s*(?:references|bibliography)\s*$", re.IGNORECASE)
LICENCE_HINT = re.compile(r"Authorized licensed|IEEE Xplore|Downloaded on|Restrictions apply")
PLACEHOLDER = re.compile(r"\{v\d+\}")
WORD = re.compile(r"[A-Za-z]{2,}")


def classify(text: str) -> str:
    if "\x00" in text:
        return "garbled"
    if LICENCE_HINT.search(text):
        return "licence"
    if (REFERENCE_HEADING.fullmatch(text) or
            (len(text) > 1200 and REF_HINT.search(text)) or
            (NUMBERED_REFERENCE.search(text) and REFERENCE_YEAR.search(text)
             and REFERENCE_DETAIL.search(text))):
        return "reference"
    if not LATIN.search(text):
        return "numeric"

    # Axis ticks and set notation carry placeholders and digits but no words
    # ("{v1}.9", "L{v1}", "({v1},{v2})"); translating them would be a no-op.
    residue = PLACEHOLDER.sub("", text)
    if not WORD.search(residue):
        return "symbol"

    # Mojibake axis labels: many Latin-1 supplement chars, few real words.
    odd = sum(1 for ch in text if 0x80 <= ord(ch) <= 0x2FF)
    if odd > len(text) * 0.25 and len(text) < 200:
        return "garbled"
    return "body"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--work", required=True)
    ap.add_argument("--min-chars", type=int, default=1,
                    help="drop body segments shorter than this (default 1 = keep all)")
    ap.add_argument("--restore", default=None,
                    help="comma separated content ids to move back into the work list")
    ap.add_argument("--skip-ids", default=None,
                    help="comma separated ids of figure text to preserve unchanged")
    ap.add_argument("--show-skipped", action="store_true",
                    help="list skipped segments with a short preview")
    args = ap.parse_args()

    work = Path(args.work).resolve()
    seg_file = work / "segments.jsonl"
    if not seg_file.exists():
        print(f"[prepare] no segments.jsonl in {work}")
        return 2

    segs = [r["text"] for r in read_jsonl(seg_file) if str(r.get("text", "")).strip()]

    # A previous skip list can be used to restore specific segments.
    previous = {r["id"]: r for r in read_jsonl(work / "skipped.jsonl")}
    restore_ids = {s.strip() for s in (args.restore or "").split(",") if s.strip()}
    manual_skip_ids = {s.strip() for s in (args.skip_ids or "").split(",") if s.strip()}
    known_ids = {text_id(text) for text in segs}
    invalid_ids = (restore_ids | manual_skip_ids) - known_ids
    if invalid_ids or restore_ids & manual_skip_ids:
        print(f"[prepare] invalid or conflicting ids: {sorted(invalid_ids | (restore_ids & manual_skip_ids))}")
        return 2

    todo, skipped, counts = [], [], {}
    kept_chars = dropped_chars = 0

    for idx, text in enumerate(segs):
        sid = text_id(text)
        kind = classify(text)
        restore = sid in restore_ids
        manually_skipped = (sid in manual_skip_ids or
                            (previous.get(sid, {}).get("reason") == "figure" and not restore))
        if manually_skipped:
            kind = "figure"

        if (kind == "body" and len(text) >= args.min_chars) or restore:
            todo.append({"id": sid, "idx": idx, "len": len(text), "text": text})
            kept_chars += len(text)
            if restore and kind != "body":
                counts["restored"] = counts.get("restored", 0) + 1
        else:
            entry = previous.get(sid, {"id": sid, "reason": kind, "len": len(text), "text": text})
            entry["reason"] = kind
            skipped.append(entry)
            dropped_chars += len(text)
            counts[kind] = counts.get(kind, 0) + 1

    write_jsonl_atomic(work / "todo.json", todo)
    write_jsonl_atomic(work / "skipped.jsonl", skipped)

    total = kept_chars + dropped_chars
    print(f"[prepare] segments={len(segs)}")
    for kind in ("body", "figure", "reference", "garbled", "numeric", "symbol", "licence", "restored"):
        if counts.get(kind):
            print(f"  {kind:<10} {counts[kind]:>4} segments")
    print(f"[prepare] to translate = {len(todo)} segments, {kept_chars} chars")
    print(f"[prepare] skipped      = {dropped_chars} chars "
          f"({dropped_chars / max(total, 1):.1%} of captured text)")
    print(f"[prepare] skipped list -> {work / 'skipped.jsonl'} "
          f"(restore any with --restore <id>)")

    if args.show_skipped:
        print("[prepare] skipped preview:")
        for rec in skipped[:40]:
            preview = rec["text"][:70].replace("\n", " ")
            print(f"  {rec['id']} [{rec['reason']}] {preview!r}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

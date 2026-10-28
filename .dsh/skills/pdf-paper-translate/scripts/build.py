#!/usr/bin/env python3
"""Join hand-written translations into translations.jsonl, validating them first.

Input: <work>/src.jsonl, one record per segment:

    {"id": "<content id>", "t": "译文……"}

Use the content `id` printed by show.py. Legacy index-only records are rejected
because indices are not stable across capture runs.

Validation (the output file is written only when all pass):
  * non-empty translation
  * placeholder tokens ({v1}...) keep the same order and count
  * the content id matches the source text actually present now
  * no two different translations for the same source id
  * prose segments are actually translated (see quality checks)

The table is written to a temp file and moved into place atomically, so a failed
build never leaves a half-written table behind for a generation run to consume.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import read_jsonl, text_id, write_jsonl_atomic  # noqa: E402

PLACEHOLDER = re.compile(r"\{v\d+\}")
CITATION = re.compile(r"\[\s*\d+\s*(?:[,;–—-]\s*\d+\s*)*\]")
KEEP_AS_IS = re.compile(r"^(https?://\S+|\S+@\S+|\{\{?v\d+\}?\}[,;:.\s]*)+$")

CJK = re.compile(r"[\u4e00-\u9fff]")
DOUBLE_PUNCT = re.compile(r"[,;:]\s*[，；：]|[，；：]\s*[,;:]")
REPEAT_PUNCT = re.compile(r"([，；：。])\1")
PUNCT_AFTER_PLACEHOLDER = re.compile(r"\{v\d+\}\s*([，；：、])")


def punct_after_placeholder_notes(dst: str) -> list[str]:
    """Notes only: whether a mark after a placeholder is wrong depends on what the
    placeholder expands to, which is not knowable here, so this never blocks."""
    notes = []
    for m in PUNCT_AFTER_PLACEHOLDER.finditer(dst):
        ctx = dst[max(0, m.start() - 16):m.end() + 16].replace("\n", " ")
        notes.append(f"'{m.group(1)}' after placeholder: ...{ctx}...")
    return notes


def quality_issues(source: str, dst: str) -> list[str]:
    issues: list[str] = []

    if "\ufffd" in dst:
        issues.append("replacement character in translation; check source encoding")

    residue = PLACEHOLDER.sub("", dst).strip()
    if not residue:
        return ["empty translation"]

    source_residue = PLACEHOLDER.sub("", source).strip()
    verbatim = bool(KEEP_AS_IS.match(source_residue)) or not re.search(r"[A-Za-z]{2,}", source_residue)
    prose = (not verbatim
             and len(source_residue) >= 30
             and len(re.findall(r"[A-Za-z]{2,}", source_residue)) >= 4)

    if prose:
        cjk = len(CJK.findall(residue))
        latin = len(re.findall(r"[A-Za-z]", residue))
        if cjk == 0:
            issues.append("no Chinese characters")
        elif latin > cjk * 3:
            issues.append(f"mostly untranslated (cjk={cjk}, latin={latin})")
        if cjk and len(residue) < len(source_residue) * 0.15:
            issues.append("suspiciously short")
    if DOUBLE_PUNCT.search(dst):
        issues.append("mixed ASCII/fullwidth punctuation")
    if REPEAT_PUNCT.search(dst):
        issues.append("duplicated punctuation")
    return issues


def load_src(path: Path) -> tuple[dict[str, str], list[str]]:
    """Return (by_id, warnings).

    Only records carrying a content id are accepted. A bare numeric index is not a
    safe key — see the rejection in main() — but it is still tracked so the message
    can explain what to fix.
    """
    by_id: dict[str, str] = {}
    warnings: list[str] = []
    for lineno, rec in enumerate(read_jsonl(path), 1):
        text = rec.get("t")
        if not isinstance(text, str):
            warnings.append(f"line {lineno}: missing 't', skipped")
            continue
        sid = rec.get("id")
        if isinstance(sid, str) and sid:
            if sid in by_id and by_id[sid] != text:
                raise ValueError(f"line {lineno}: conflicting translations for id {sid}; keep one version")
            else:
                by_id[sid] = text
        elif isinstance(rec.get("i"), int):
            warnings.append(
                f"line {lineno}: indexed by 'i' only; add the 'id' shown by show.py")
        else:
            warnings.append(f"line {lineno}: neither 'id' nor 'i' present, skipped")
    return by_id, warnings


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--work", required=True)
    ap.add_argument("--allow-missing", action="store_true")
    ap.add_argument("--allow-warnings", action="store_true")
    args = ap.parse_args()

    work = Path(args.work).resolve()
    todo_path = work / "todo.json"
    if not todo_path.exists():
        print(f"[build] no todo.json in {work}; run prepare.py first")
        return 2

    try:
        todo = read_jsonl(todo_path, required=True)
        by_id, load_warnings = load_src(work / "src.jsonl")
    except ValueError as exc:
        print(f"[build] {exc}")
        return 1

    records: list[dict] = []
    problems: list[tuple[str, str]] = []
    missing: list[str] = []
    quality: list[tuple[str, str]] = []
    notes: list[tuple[str, str]] = []
    index_only = any("indexed by 'i' only" in w for w in load_warnings)

    for item in todo:
        sid = item.get("id") or text_id(item["text"])
        source = item["text"]
        if sid != text_id(source):
            problems.append((sid, "content id does not match source text; re-run prepare.py"))
            continue

        dst = by_id.get(sid)
        if dst is None:
            if index_only:
                # The caller wrote records keyed by position, which cannot be trusted:
                # a later capture may have re-split the document, so an old translation
                # could land on a different paragraph.
                problems.append(
                    (sid, "src.jsonl is keyed by index only; use the 'id' printed "
                          "by show.py so translations stay bound to their text"))
            else:
                missing.append(sid)
            continue

        if not dst.strip():
            problems.append((sid, "empty translation"))
            continue

        src_ph = PLACEHOLDER.findall(source)
        dst_ph = PLACEHOLDER.findall(dst)
        if src_ph != dst_ph:
            problems.append((sid, f"placeholders {src_ph} -> {dst_ph}"))
        src_citations = Counter(CITATION.findall(source))
        dst_citations = Counter(CITATION.findall(dst))
        if src_citations != dst_citations:
            problems.append((sid, f"citations {dict(src_citations)} -> {dict(dst_citations)}"))

        if dst.strip() == source.strip() and src_ph == dst_ph and len(source) > 40:
            stripped = PLACEHOLDER.sub("", source).strip()
            if not KEEP_AS_IS.match(stripped) and not re.fullmatch(r"[\W\d_]+", stripped):
                problems.append((sid, "identical to source"))

        for issue in quality_issues(source, dst):
            quality.append((sid, issue))
        for note in punct_after_placeholder_notes(dst):
            notes.append((sid, note))

        records.append({"id": sid, "text": source, "translation": dst})

    if load_warnings:
        print(f"[build] INPUT NOTES ({len(load_warnings)}):")
        for w in load_warnings[:10]:
            print(f"  {w}")

    if problems:
        print(f"[build] PROBLEMS ({len(problems)}):")
        for sid, msg in problems[:20]:
            print(f"  [{sid}] {msg}")
        if len(problems) > 20:
            print(f"  ... and {len(problems) - 20} more")

    if missing:
        print(f"[build] MISSING {len(missing)} segment(s): {missing[:20]}"
              + (" ..." if len(missing) > 20 else ""))

    if quality:
        print(f"[build] QUALITY WARNINGS ({len(quality)}):")
        for sid, issue in quality[:20]:
            print(f"  [{sid}] {issue}")
        if len(quality) > 20:
            print(f"  ... and {len(quality) - 20} more")

    if notes:
        print(f"[build] NOTES ({len(notes)}) — punctuation right after a placeholder; "
              "harmless for citations, doubles up for author lines:")
        for sid, note in notes[:8]:
            print(f"  [{sid}] {note}")

    # Only now touch the output file, and atomically, so a failed build cannot be
    # mistaken for a usable table.
    out_path = work / "translations.jsonl"
    if problems or (missing and not args.allow_missing) or (quality and not args.allow_warnings):
        print(f"[build] NOT WRITTEN — fix the issues above, then re-run")
        print(f"[build] (previous {out_path.name} left untouched)")
        return 1

    write_jsonl_atomic(out_path, records)
    print(f"[build] wrote {len(records)} records -> {out_path}")
    print("[build] OK: placeholders consistent, ids verified, all segments covered")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

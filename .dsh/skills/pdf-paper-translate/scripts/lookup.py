#!/usr/bin/env python3
"""Byte-safe stdin to stdout lookup consumed by pdf2zh_next --clitranslator.

Resolution order
----------------
1. explicitly skipped segments are echoed unchanged
2. the paper's own translations.jsonl
3. the shared cross-paper memory

Segments are read as raw bytes: some figure labels arrive as UTF-16LE and a strict
UTF-8 decode would corrupt them, making those segments miss on every run. On a miss
the exact original bytes are echoed unchanged, so the pipeline never crashes on
untranslatable content.

Misses are recorded under $MT_RUN (one directory per pipeline execution), never
appended to a shared file, so a previous run's misses cannot inflate this run's count.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import dumps_line, read_jsonl  # noqa: E402

HERE = Path(__file__).resolve().parent
SKILL = HERE.parent
DEFAULT_MEMORY = SKILL / "memory.jsonl"

_LOCAL: dict[str, str] | None = None
_SHARED: dict[str, str] | None = None
_SKIPPED: set[str] | None = None


def work_dir() -> Path:
    return Path(os.environ.get("MT_WORK", str(HERE)))


def run_dir() -> Path | None:
    raw = os.environ.get("MT_RUN")
    return Path(raw) if raw else None


def memory_file() -> Path:
    raw = os.environ.get("MT_MEMORY")
    return Path(raw) if raw else DEFAULT_MEMORY


def _read_table(path: Path) -> dict[str, str]:
    table: dict[str, str] = {}
    if not path.exists():
        return table
    with path.open(encoding="utf-8", errors="surrogateescape") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                continue
            src, dst = rec.get("text"), rec.get("translation")
            if isinstance(src, str) and isinstance(dst, str):
                table[src] = dst
    return table


def local_table(work: Path) -> dict[str, str]:
    global _LOCAL
    if _LOCAL is None:
        _LOCAL = _read_table(work / "translations.jsonl")
    return _LOCAL


def shared_table() -> dict[str, str]:
    global _SHARED
    if _SHARED is None:
        _SHARED = _read_table(memory_file())
    return _SHARED


def skipped_texts(work: Path) -> set[str]:
    global _SKIPPED
    if _SKIPPED is None:
        planned = {r["text"] for r in read_jsonl(work / "todo.json", required=True)}
        skipped = {r["text"] for r in read_jsonl(work / "skipped.jsonl", required=True)}
        _SKIPPED = skipped - planned
    return _SKIPPED


def record_missing(text: str) -> None:
    """Append this segment to the run's miss log, or fail loudly.

    A miss that cannot be recorded would make the caller's coverage check report
    success while the PDF still contains source text — the exact silent failure this
    skill exists to prevent. So an I/O error is raised, not swallowed: the pipeline
    aborts and the user sees a real error instead of a false "OK".
    """
    target = run_dir()
    path = (target / "missing.jsonl") if target else (work_dir() / "missing.jsonl")
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(dumps_line({"text": text}) + "\n")


def main() -> int:
    raw = sys.stdin.buffer.read()
    try:
        text = raw.decode("utf-8", "surrogateescape")
    except Exception:
        sys.stdout.buffer.write(raw)
        return 0

    if not text.strip():
        sys.stdout.buffer.write(raw)
        return 0

    if text in skipped_texts(work_dir()):
        sys.stdout.buffer.write(raw)
        return 0

    hit = local_table(work_dir()).get(text)
    if hit is None:
        hit = shared_table().get(text)

    if hit is None:
        record_missing(text)
        sys.stdout.buffer.write(raw)
    else:
        sys.stdout.buffer.write(hit.encode("utf-8", "surrogateescape"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

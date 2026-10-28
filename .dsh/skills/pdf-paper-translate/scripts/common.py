#!/usr/bin/env python3
"""Shared helpers: content identity for segments, run isolation, byte-safe IO.

Why content hashes
------------------
Segment order is not stable across capture runs: re-parsing a PDF, changing pdf2zh
options, or a different BabelDOC version can reorder or re-split segments. Keying
translations by list index would then apply an old translation to a different
paragraph. Every record therefore carries a short hash of its exact source text,
and `build` refuses to use a translation whose hash no longer matches.
"""
from __future__ import annotations

import hashlib
import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path


def text_id(text: str) -> str:
    """Stable identifier for a segment: first 16 hex chars of the SHA-256."""
    return hashlib.sha256(text.encode("utf-8", "surrogateescape")).hexdigest()[:16]


def run_dir(work: Path) -> Path:
    """Directory holding per-run artefacts, isolated so stale data cannot leak in."""
    d = work / "runs"
    d.mkdir(parents=True, exist_ok=True)
    return d


def new_run(work: Path, purpose: str) -> Path:
    """Create a fresh run directory for one pipeline execution."""
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%f")
    return Path(tempfile.mkdtemp(prefix=f"{purpose}-{stamp}-", dir=run_dir(work)))


def latest_run(work: Path, purpose: str) -> Path | None:
    runs = sorted(run_dir(work).glob(f"{purpose}-*"))
    return max(runs, key=lambda p: p.stat().st_mtime_ns) if runs else None


def read_jsonl(path: Path, *, required: bool = False) -> list[dict]:
    out: list[dict] = []
    if not required and not path.exists():
        return out
    with path.open(encoding="utf-8", errors="surrogateescape") as fh:
        for lineno, line in enumerate(fh, 1):
            line = line.strip()
            if not line:
                continue
            try:
                out.append(json.loads(line))
            except json.JSONDecodeError as exc:
                raise ValueError(f"{path}:{lineno}: invalid JSONL") from exc
    return out


def write_json_atomic(path: Path, obj) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps(obj, ensure_ascii=False, indent=1), encoding="utf-8")
    os.replace(tmp, path)


def dumps_line(rec: dict) -> str:
    """Serialise one record as a single JSONL line, keeping CJK readable.

    ``ensure_ascii=False`` keeps Chinese readable and the file ~36% smaller. The
    failure it can cause happens at the *UTF-8 encoding* step, not inside
    ``json.dumps``: a lone surrogate (produced when UTF-16LE figure labels are
    decoded with surrogateescape) survives ``json.dumps`` but cannot be encoded to
    UTF-8. So we probe the encoding and fall back to escaping only when that probe
    fails, rather than paying the readability cost for every record.
    """
    line = json.dumps(rec, ensure_ascii=False)
    try:
        line.encode("utf-8")
    except UnicodeEncodeError:
        # Writing this record as-is would fail; escape it so it stays valid JSONL.
        line = json.dumps(rec, ensure_ascii=True)
    return line


def write_jsonl_atomic(path: Path, records: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    with tmp.open("w", encoding="utf-8") as fh:
        for rec in records:
            fh.write(dumps_line(rec) + "\n")
    os.replace(tmp, path)

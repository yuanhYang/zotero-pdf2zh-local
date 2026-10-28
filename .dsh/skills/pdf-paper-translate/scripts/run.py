#!/usr/bin/env python3
"""Drive the pdf2zh_next clitranslator pipeline.

Modes
-----
--capture   run with a recording translator that echoes the source bytes, so every
            segment the pipeline will ask for lands in <work>/segments.jsonl.
(default)   run with the lookup translator, producing translated PDFs in --out.
--verify    print compact per-page coverage for the produced PDFs.

Exit status is meaningful in every mode:
    0  the operation completed AND the result was verified
    1  the pipeline ran but the result is incomplete or failed verification
    2  usage or precondition error (missing file, missing venv)

Cache handling
--------------
Both capture and generation use --ignore-cache. The engine neither reads nor
writes translation entries, so identity captures cannot mask later translations
and other jobs' cache entries stay untouched.
"""
from __future__ import annotations

import argparse
import glob
import json
import os
import re
import shlex
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import read_jsonl, new_run  # noqa: E402

HERE = Path(__file__).resolve().parent
SKILL = HERE.parent
LOOKUP = HERE / "lookup.py"


def log(msg: str) -> None:
    print(msg, flush=True)


# ---------------------------------------------------------------------- pipeline
def pdf2zh_exe(python: Path) -> Path:
    for name in ("pdf2zh_next.exe", "pdf2zh_next"):
        cand = python.parent / name
        if cand.exists():
            return cand
    return python.parent / "pdf2zh_next.exe"


def build_command(pdf: Path, python: Path, script: Path, out: Path,
                  pages: str | None, dual: bool) -> list[str]:
    """Build argv. Paths are passed as list items, so spaces need no quoting."""
    cmd = [
        str(pdf2zh_exe(python)),
        str(pdf),
        "--clitranslator",
        "--ignore-cache",
        "--clitranslator-command",
        # pdf2zh splits this string with shlex, so it *is* quoted explicitly and
        # uses forward slashes: backslashes would be eaten as escapes.
        " ".join(shlex.quote(p.replace("\\", "/")) for p in (str(python), str(script))),
        "--output", str(out),
        "--lang-in", "en",
        "--lang-out", "zh-CN",
        "--watermark-output-mode", "no_watermark",
    ]
    if not dual:
        cmd.append("--no-dual")
    if pages:
        cmd += ["--pages", pages]
    return cmd


def run_pipeline(pdf: Path, python: Path, script: Path, out: Path, pages: str | None,
                 work: Path, dual: bool, run_path: Path) -> int:
    out.mkdir(parents=True, exist_ok=True)
    run_path.mkdir(parents=True, exist_ok=True)
    env = dict(os.environ)
    env["MT_WORK"] = str(work)
    env["MT_RUN"] = str(run_path)
    env["PYTHONIOENCODING"] = "utf-8"
    env["PYTHONUTF8"] = "1"

    cmd = build_command(pdf, python, script, out, pages, dual)
    log(f"[run] {' '.join(cmd[:4])} ...")

    # Stream output so a long job shows progress instead of going silent.
    proc = subprocess.Popen(cmd, cwd=str(SKILL), env=env, text=True,
                            encoding="utf-8", errors="replace",
                            stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    tail: list[str] = []
    assert proc.stdout is not None
    for line in proc.stdout:
        tail.append(line)
        if len(tail) > 400:
            tail.pop(0)
        low = line.lower()
        if any(k in low for k in ("error", "failed", "translate", "typesetting",
                                  "save pdf", "parsing")):
            sys.stdout.write(line if line.endswith("\n") else line + "\n")
            sys.stdout.flush()
    rc = proc.wait()

    (run_path / "pipeline.log").write_text("".join(tail), encoding="utf-8")
    if rc != 0:
        log(f"[run] FAILED exit={rc}")
        log("".join(tail)[-2000:])
    else:
        log("[run] pipeline finished")
    return rc


# ---------------------------------------------------------------------- verdicts
def count_missing(work: Path, run_path: Path) -> tuple[int, int]:
    """Return (untranslated, explicitly skipped) for this run.

    A new or unexpected segment is a gap, not an implicit skip. A restored segment
    in todo takes priority if it is also present in an old skip list.

    Raises ValueError with an actionable message when the plan is incomplete, so the
    caller can tell "prepare.py was never run" from a genuine pipeline failure.
    """
    todo_path = work / "todo.json"
    skipped_path = work / "skipped.jsonl"

    if not todo_path.exists():
        raise ValueError(
            f"{todo_path} is missing — run prepare.py --work {work} first")
    if not skipped_path.exists():
        # Without the skip list every non-planned segment looks like a gap, which
        # would report a spurious failure; require it rather than guess.
        raise ValueError(
            f"{skipped_path} is missing — run prepare.py --work {work} first "
            "(it writes both todo.json and skipped.jsonl)")

    todo = read_jsonl(todo_path, required=True)
    skipped = read_jsonl(skipped_path, required=True)
    planned_texts = {r["text"] for r in todo}
    skipped_texts = {r["text"] for r in skipped} - planned_texts
    misses = {r["text"] for r in read_jsonl(run_path / "missing.jsonl")}
    return len(misses - skipped_texts), len(misses & skipped_texts)


def verify(out: Path, since: float | None = None) -> tuple[bool, str]:
    """Check the produced PDFs are present, fresh, and contain Chinese.

    `since` is the pipeline start time: a PDF older than that is a leftover from a
    previous run and must not be reported as this run's success.
    """
    try:
        import fitz  # type: ignore
    except ImportError:
        return False, "NOT VERIFIED: PyMuPDF unavailable in this interpreter"

    pdfs = sorted(glob.glob(str(out / "*.pdf")))
    if not pdfs:
        return False, f"no PDF produced in {out}"

    if since is not None:
        fresh = [p for p in pdfs if os.path.getmtime(p) >= since - 1.0]
        stale = [os.path.basename(p) for p in pdfs if p not in fresh]
        if not fresh:
            return False, ("no PDF was written by this run; only stale files exist: "
                           + ", ".join(stale))
        pdfs = fresh

    cjk = re.compile(r"[\u4e00-\u9fff]")
    report: list[str] = []
    ok = True
    for f in pdfs:
        name = os.path.basename(f)
        kind = "dual" if "dual" in name else "mono"
        doc = fitz.open(f)
        counts, total, cj = [], 0, 0
        for page in doc:
            text = page.get_text()
            total += len(text)
            n = len(cjk.findall(text))
            cj += n
            counts.append(n)
        ratio = cj / max(total, 1)
        doc.close()
        # A translated PDF shorter than ~5% Chinese suggests the run echoed English.
        if cj == 0 or (kind == "mono" and ratio < 0.05):
            ok = False
        report.append(f"{kind}: pages={len(counts)} cjk={cj} ratio={ratio:.1%} per-page={counts}")
    return ok, "\n".join("[verify] " + r for r in report)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--pdf", required=False, help="source PDF")
    ap.add_argument("--venv", required=True, help="python env containing pdf2zh_next")
    ap.add_argument("--work", required=True, help="work directory for this paper")
    ap.add_argument("--out", default=None, help="output directory for PDFs")
    ap.add_argument("--pages", default=None)
    ap.add_argument("--capture", action="store_true")
    ap.add_argument("--mono-only", action="store_true")
    ap.add_argument("--verify", action="store_true")
    args = ap.parse_args()

    work = Path(args.work).resolve()
    work.mkdir(parents=True, exist_ok=True)

    venv = Path(args.venv).resolve()
    python = venv / "Scripts" / "python.exe"
    if not python.exists():
        python = venv / "bin" / "python"
    if not python.exists():
        log(f"[error] no python in venv: {venv}")
        return 2

    out = Path(args.out).resolve() if args.out else work / "out"

    if args.verify:
        ok, msg = verify(out)
        log(msg)
        return 0 if ok else 1

    if not args.pdf:
        log("[error] --pdf is required unless --verify")
        return 2
    pdf = Path(args.pdf).resolve()
    if not pdf.exists():
        log(f"[error] PDF not found: {pdf}")
        return 2

    if args.capture:
        seg = work / "segments.jsonl"
        seg.unlink(missing_ok=True)
        run_path = new_run(work, "capture")
        rec = run_path / "recorder.py"
        rec.write_text(
            "import json, os, sys\n"
            "from pathlib import Path\n"
            "w = Path(os.environ['MT_WORK'])\n"
            "# Read raw bytes: some segments are not valid UTF-8 (UTF-16LE labels).\n"
            "raw = sys.stdin.buffer.read()\n"
            "text = raw.decode('utf-8', 'surrogateescape')\n"
            "if text.strip():\n"
            "    with (w / 'segments.jsonl').open('a', encoding='utf-8',\n"
            "                                      errors='surrogateescape') as f:\n"
            "        f.write(json.dumps({'text': text}, ensure_ascii=False) + '\\n')\n"
            "sys.stdout.buffer.write(raw)\n",
            encoding="utf-8",
        )
        rc = run_pipeline(pdf, python, rec, run_path / "capture_out",
                          args.pages, work, True, run_path)
        if rc != 0:
            log("[capture] FAILED")
            return 1
        n = len(read_jsonl(work / "segments.jsonl"))
        log(f"[capture] segments={n}")
        return 0 if n > 0 else 1

    # ---- generation
    run_path = new_run(work, "run")
    try:
        # Validate the plan before spending time on the PDF pipeline.
        count_missing(work, run_path)
    except ValueError as exc:
        log(f"[error] translation plan is not ready: {exc}")
        return 2
    except OSError as exc:
        log(f"[error] cannot read the translation plan: {exc}")
        return 2

    started = time.time()
    rc = run_pipeline(pdf, python, LOOKUP, out, args.pages, work,
                      not args.mono_only, run_path)

    if rc != 0:
        log("[run] RESULT: FAILED (pipeline error)")
        return 1

    real_missing, skipped = count_missing(work, run_path)
    log(f"[run] missing={real_missing} untranslated segment(s); "
        f"{skipped} untranslatable skipped as expected")

    verified, report = verify(out, since=started)
    log(report)
    if real_missing:
        log(f"[run] RESULT: INCOMPLETE — {real_missing} segment(s) had no "
            f"translation; the PDF contains source text there. See "
            f"{run_path / 'missing.jsonl'}")
        return 1
    if not verified:
        log("[run] RESULT: FAILED — verification found no usable translation")
        return 1

    log("[run] RESULT: OK — pipeline finished, coverage complete, verification passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

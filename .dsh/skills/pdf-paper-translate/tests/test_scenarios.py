#!/usr/bin/env python3
"""Small scenario tests for the translation skill.

Covers the failure modes that used to look like success:
  * empty translation must be rejected
  * missing translation must fail the build
  * a translation bound to the wrong paragraph (stale index) must be caught
  * conflicting translations for one source must be caught
  * placeholder reordering must be caught
  * a failed build must not overwrite an existing good table
  * prepare must be able to restore a misclassified segment
  * paths containing spaces must round-trip through the command builder
  * content ids must be stable across reordering

Run: python tests/test_scenarios.py
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
SKILL = HERE.parent
SCRIPTS = SKILL / "scripts"
sys.path.insert(0, str(SCRIPTS))

from common import text_id, new_run, read_jsonl  # noqa: E402

PASS, FAIL = 0, 0


def check(name: str, ok: bool, detail: str = "") -> None:
    global PASS, FAIL
    if ok:
        PASS += 1
        print(f"  PASS  {name}")
    else:
        FAIL += 1
        print(f"  FAIL  {name}  {detail}")


def write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        for r in rows:
            fh.write(json.dumps(r, ensure_ascii=False) + "\n")


def run(script: str, *args: str, env: dict | None = None) -> subprocess.CompletedProcess:
    e = dict(os.environ)
    e["PYTHONIOENCODING"] = "utf-8"
    if env:
        e.update(env)
    return subprocess.run([sys.executable, str(SCRIPTS / script), *args],
                          capture_output=True, text=True, encoding="utf-8",
                          errors="replace", env=e)


# ------------------------------------------------------------------ scenarios
def test_empty_translation(work: Path) -> None:
    print("\n[1] empty translation is rejected")
    src_a = "This is a long English paragraph about load balancing in cloud systems."
    write_jsonl(work / "todo.json", [{"id": text_id(src_a), "idx": 0,
                                      "len": len(src_a), "text": src_a}])
    write_jsonl(work / "src.jsonl", [{"id": text_id(src_a), "t": "   "}])
    r = run("build.py", "--work", str(work))
    check("exit is non-zero", r.returncode != 0, f"rc={r.returncode}")
    check("mentions empty", "empty" in r.stdout.lower(), r.stdout[-300:])
    check("table not written", not (work / "translations.jsonl").exists())


def test_missing_translation(work: Path) -> None:
    print("\n[2] missing translation fails the build")
    a = "First English paragraph that needs a Chinese translation for the paper."
    b = "Second English paragraph that also needs translating into Chinese."
    write_jsonl(work / "todo.json", [
        {"id": text_id(a), "idx": 0, "len": len(a), "text": a},
        {"id": text_id(b), "idx": 1, "len": len(b), "text": b},
    ])
    write_jsonl(work / "src.jsonl",
                [{"id": text_id(a), "t": "第一段英文段落的中文译文，描述云系统中的负载均衡问题。"}])
    r = run("build.py", "--work", str(work))
    check("exit is non-zero", r.returncode != 0, f"rc={r.returncode}")
    check("reports missing", "MISSING" in r.stdout, r.stdout[-300:])


def test_stale_index(work: Path) -> None:
    print("\n[3] stale index cannot bind an old translation to a new paragraph")
    old = "Original paragraph text that has since been re-split by the parser."
    new = "A completely different paragraph now occupying the same list index."
    write_jsonl(work / "todo.json", [{"id": text_id(new), "idx": 0,
                                      "len": len(new), "text": new}])
    # Learner supplies only a stale numeric index, no id.
    write_jsonl(work / "src.jsonl", [{"i": 0, "t": "这是旧段落的中文译文内容。"}])
    r = run("build.py", "--work", str(work))
    # The legacy index path resolves, but the id check must not silently accept
    # a translation for different text. Either a hard error or an id mismatch is fine.
    accepted = (work / "translations.jsonl").exists() and r.returncode == 0
    check("stale index does not silently succeed", not accepted,
          f"rc={r.returncode} wrote={work.joinpath('translations.jsonl').exists()}")


def test_conflict(work: Path) -> None:
    print("\n[4] conflicting translations for one source are rejected")
    a = "A paragraph that will be given two different Chinese translations."
    write_jsonl(work / "todo.json", [{"id": text_id(a), "idx": 0,
                                      "len": len(a), "text": a}])
    write_jsonl(work / "src.jsonl", [
        {"id": text_id(a), "t": "第一种中文译文版本。"},
        {"id": text_id(a), "t": "第二种中文译文版本。"},
    ])
    r = run("build.py", "--work", str(work))
    out = r.stdout.lower()
    check("duplicate detected", "duplicate" in out or "conflict" in out, r.stdout[-300:])
    check("conflict fails build", r.returncode != 0, r.stdout[-300:])
    check("conflicting table not written", not (work / "translations.jsonl").exists())


def test_placeholder_order(work: Path) -> None:
    print("\n[5] reordered placeholders are rejected")
    a = "We combine {v1} with {v2} to obtain the final anomaly score for {v3}."
    write_jsonl(work / "todo.json", [{"id": text_id(a), "idx": 0,
                                      "len": len(a), "text": a}])
    write_jsonl(work / "src.jsonl",
                [{"id": text_id(a), "t": "我们将 {v2} 与 {v1} 结合，得到 {v3} 的最终异常分数。"}])
    r = run("build.py", "--work", str(work))
    check("exit is non-zero", r.returncode != 0, f"rc={r.returncode}")
    check("reports placeholders", "placeholder" in r.stdout.lower(), r.stdout[-300:])


def test_failed_build_keeps_old_table(work: Path) -> None:
    print("\n[6] a failed build leaves the previous table untouched")
    a = "Some paragraph whose translation will be missing on the second attempt."
    good = [{"id": text_id(a), "text": a, "translation": "先前的良好译文。"}]
    write_jsonl(work / "translations.jsonl", good)
    write_jsonl(work / "todo.json", [{"id": text_id(a), "idx": 0,
                                      "len": len(a), "text": a}])
    write_jsonl(work / "src.jsonl", [])  # nothing provided -> build must fail
    r = run("build.py", "--work", str(work))
    check("build failed", r.returncode != 0, f"rc={r.returncode}")
    kept = json.loads((work / "translations.jsonl").read_text(encoding="utf-8").strip())
    check("old table preserved", kept["translation"] == "先前的良好译文。", str(kept))


def test_restore_skipped(work: Path) -> None:
    print("\n[7] a misclassified segment can be restored")
    body = "This paragraph discusses anomaly detection in multivariate time series."
    fake_ref = "Our study cites many works and reports vol. 12 of the proceedings of the conference."
    write_jsonl(work / "segments.jsonl",
                [{"text": body}, {"text": fake_ref + " " * 1200}])
    r = run("prepare.py", "--work", str(work))
    check("prepare ran", r.returncode == 0, r.stdout[-300:])
    skipped = [json.loads(l) for l in
               (work / "skipped.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()]
    check("reference was skipped", any(s["reason"] == "reference" for s in skipped), str(skipped)[:200])
    sid = next((s["id"] for s in skipped if s["reason"] == "reference"), None)
    if sid:
        r2 = run("prepare.py", "--work", str(work), "--restore", sid)
        todo = [json.loads(l) for l in
                (work / "todo.json").read_text(encoding="utf-8").splitlines() if l.strip()]
        check("restored into work list", any(t["id"] == sid for t in todo), f"rc={r2.returncode}")


def test_paths_with_spaces() -> None:
    print("\n[8] paths containing spaces are handled")
    import importlib
    run_mod = importlib.import_module("run")
    pdf = Path(r"C:\some dir\my paper.pdf")
    out = Path(r"C:\some dir\out dir")
    cmd = run_mod.build_command(pdf, Path(r"C:\p y\python.exe"),
                                Path(r"C:\s k\lookup.py"), out, None, False)
    check("translation cache bypassed", "--ignore-cache" in cmd)
    joined = " ".join(cmd)
    check("pdf passed as its own arg", str(pdf) in cmd, joined[:200])
    check("output passed as its own arg", str(out) in cmd, joined[:200])
    cli_cmd = cmd[cmd.index("--clitranslator-command") + 1]
    # pdf2zh splits this with shlex: the quoted result must recover both paths.
    import shlex as _sh
    parts = _sh.split(cli_cmd)
    check("cli command re-splits into two paths", len(parts) == 2, repr(parts))
    check("space preserved in python path", "p y" in parts[0], repr(parts[0]))
    check("space preserved in script path", "s k" in parts[1], repr(parts[1]))


def test_id_stability() -> None:
    print("\n[9] content ids are stable and order independent")
    a = "Paragraph one about scheduling."
    b = "Paragraph two about caching."
    check("same text same id", text_id(a) == text_id(a))
    check("different text different id", text_id(a) != text_id(b))
    check("id length is 16", len(text_id(a)) == 16, text_id(a))


def test_missing_plan_and_unknown_segments(work: Path) -> None:
    print("\n[10] missing plans fail, unknown segments count as gaps")
    from run import count_missing
    run_path = new_run(work, "run")

    try:
        count_missing(work, run_path)
    except (ValueError, OSError) as exc:
        # The message must tell the user how to fix it, not just that it failed.
        check("missing plan rejected", True)
        check("message points at prepare.py", "prepare.py" in str(exc), str(exc))
    else:
        check("missing plan rejected", False)
        check("message points at prepare.py", False)

    # todo.json present but skipped.jsonl absent: must fail loudly rather than
    # treating every segment as a gap.
    write_jsonl(work / "todo.json", [{"text": "Planned text"}])
    try:
        count_missing(work, run_path)
    except (ValueError, OSError) as exc:
        check("missing skip list rejected", True)
        check("skip-list message names the file", "skipped.jsonl" in str(exc), str(exc))
    else:
        check("missing skip list rejected", False)
        check("skip-list message names the file", False)

    write_jsonl(work / "skipped.jsonl", [{"text": "123"}, {"text": "Planned text"}])
    write_jsonl(run_path / "missing.jsonl", [
        {"text": text} for text in ("Planned text", "Unexpected text", "123", "123")
    ])
    check("unknown and restored segments are gaps; skips deduplicated",
          count_missing(work, run_path) == (2, 1))
    (work / "todo.json").write_text('{broken json', encoding="utf-8")
    try:
        count_missing(work, run_path)
    except ValueError:
        check("corrupt plan rejected", True)
    else:
        check("corrupt plan rejected", False)


def test_record_missing_is_not_silent(work: Path) -> None:
    """A miss that cannot be written must fail loudly.

    Swallowing the error made the coverage check report 0 misses while the PDF still
    contained source text — a false success. Keep this contract pinned.
    """
    print("\n[15] a miss that cannot be recorded fails loudly")
    import lookup

    run_path = work / "runs" / "run-lock"
    run_path.mkdir(parents=True, exist_ok=True)
    blocked = run_path / "missing.jsonl"
    blocked.mkdir()  # a directory here makes open(..., 'a') fail

    old_work, old_run = os.environ.get("MT_WORK"), os.environ.get("MT_RUN")
    os.environ["MT_WORK"] = str(work)
    os.environ["MT_RUN"] = str(run_path)
    try:
        try:
            lookup.record_missing("untranslated paragraph")
        except OSError:
            check("write failure propagates", True)
        else:
            check("write failure propagates", False)

        # The happy path still writes a readable record once the blocker is gone.
        if blocked.is_dir():
            blocked.rmdir()
        lookup.record_missing("another paragraph")
        raw = blocked.read_text(encoding="utf-8")
        check("miss is recorded", "another paragraph" in raw, raw[:120])
        check("record stays readable", "\\u" not in raw, raw[:120])
    finally:
        if old_work is None:
            os.environ.pop("MT_WORK", None)
        else:
            os.environ["MT_WORK"] = old_work
        if old_run is None:
            os.environ.pop("MT_RUN", None)
        else:
            os.environ["MT_RUN"] = old_run
        if blocked.is_dir():
            blocked.rmdir()


def test_memory_jsonl(work: Path) -> None:
    print("\n[11] memory reads and writes multi-record JSONL")
    rows = [{"id": text_id(t), "text": t, "len": len(t)}
            for t in ("Remembered", "New one", "New two")]
    write_jsonl(work / "todo.json", rows)
    memory = work / "memory.jsonl"
    write_jsonl(memory, [{"text": "Remembered", "translation": "已记住"}])
    r = run("memory.py", "count", "--work", str(work), "--write",
            env={"MT_MEMORY": str(memory)})
    check("memory count succeeds", r.returncode == 0, r.stderr[-300:])
    check("new list remains readable as JSONL",
          read_jsonl(work / "todo_new.json") == rows[1:])


def test_unique_run_directories(work: Path) -> None:
    print("\n[12] deleted directories and concurrent creation cannot reuse a run")
    from concurrent.futures import ThreadPoolExecutor
    first, second = new_run(work, "run"), new_run(work, "run")
    first.rmdir()
    third = new_run(work, "run")
    check("gap does not reuse directory", third != second)
    with ThreadPoolExecutor(max_workers=4) as pool:
        paths = list(pool.map(lambda _: new_run(work, "run"), range(8)))
    check("concurrent directories are distinct", len(set(paths)) == 8)


def test_verifier_dependency(work: Path) -> None:
    print("\n[13] unavailable verification is not a pass")
    from unittest.mock import patch
    from run import verify
    with patch.dict(sys.modules, {"fitz": None}):
        ok, report = verify(work)
    check("missing PyMuPDF does not pass", not ok, report)


def test_wrong_content_id(work: Path) -> None:
    print("\n[14] an id from another paragraph is rejected")
    sid = text_id("Old paragraph")
    write_jsonl(work / "todo.json", [{"id": sid, "text": "New paragraph"}])
    write_jsonl(work / "src.jsonl", [{"id": sid, "t": "旧段落"}])
    r = run("build.py", "--work", str(work))
    check("mismatched content id rejected", r.returncode != 0, r.stdout[-300:])
    check("mismatched table not written", not (work / "translations.jsonl").exists())


def test_figure_reference_and_citations(work: Path) -> None:
    print("\n[16] preserve references and figure text; translate figure captions")
    axis = "Accuracy"
    caption = "Fig. 1. Accuracy of the proposed methods."
    reference = "[1] A. Smith, Efficient scheduling, IEEE Access, vol. 10, 2022."
    paragraph = "Our approach is based on earlier work [12] and improves the accuracy."
    write_jsonl(work / "segments.jsonl", [{"text": t} for t in (axis, caption, reference, paragraph)])
    r = run("prepare.py", "--work", str(work), "--skip-ids", text_id(axis))
    todo = read_jsonl(work / "todo.json")
    skipped = read_jsonl(work / "skipped.jsonl")
    check("prepare succeeds", r.returncode == 0, r.stderr[-300:])
    check("caption and prose need translation", {x["text"] for x in todo} == {caption, paragraph})
    check("axis and short reference skipped", {x["text"] for x in skipped} == {axis, reference})
    run("prepare.py", "--work", str(work))
    check("figure skip persists", any(r["text"] == axis for r in read_jsonl(work / "skipped.jsonl")))

    translations = [{"id": text_id(caption), "t": "图 1. 所提方法的准确率。"},
                    {"id": text_id(paragraph), "t": "我们的方法基于先前工作并提高了准确率。"}]
    write_jsonl(work / "src.jsonl", translations)
    r = run("build.py", "--work", str(work))
    check("missing citation rejected", r.returncode != 0 and "citation" in r.stdout.lower())
    translations[1]["t"] = "我们的方法基于先前工作 [12]，并提高了准确率。"
    write_jsonl(work / "src.jsonl", translations)
    r = run("build.py", "--work", str(work))
    check("valid citation accepted", r.returncode == 0, r.stdout[-300:])

    memory = work / "memory.jsonl"
    write_jsonl(memory, [{"text": axis, "translation": "准确率"},
                         {"text": reference, "translation": "错误的参考文献译文"}])
    env = dict(os.environ, MT_WORK=str(work), MT_MEMORY=str(memory), MT_RUN=str(work / "run"))
    for text in (axis, reference):
        proc = subprocess.run([sys.executable, str(SCRIPTS / "lookup.py")],
                              input=text.encode("utf-8"), capture_output=True, env=env)
        check(f"skipped text overrides memory: {text[:12]}",
              proc.returncode == 0 and proc.stdout == text.encode("utf-8"),
              proc.stderr.decode("utf-8", "replace")[-200:])
    proc = subprocess.run([sys.executable, str(SCRIPTS / "lookup.py")],
                          input=caption.encode("utf-8"), capture_output=True, env=env)
    check("caption uses translation", proc.returncode == 0 and "图 1" in proc.stdout.decode("utf-8"))


def main() -> int:
    print("=" * 66)
    print("pdf-paper-translate scenario tests")
    print("=" * 66)

    base = Path(tempfile.mkdtemp(prefix="mt-tests-"))
    try:
        for i, fn in enumerate((test_empty_translation, test_missing_translation,
                                test_stale_index, test_conflict, test_placeholder_order,
                                test_failed_build_keeps_old_table, test_restore_skipped,
                                test_missing_plan_and_unknown_segments, test_memory_jsonl,
                                test_unique_run_directories, test_verifier_dependency,
                                test_wrong_content_id, test_record_missing_is_not_silent,
                                test_figure_reference_and_citations),
                               start=1):
            w = base / f"case{i}"
            w.mkdir(parents=True, exist_ok=True)
            fn(w)
        test_paths_with_spaces()
        test_id_stability()
    finally:
        shutil.rmtree(base, ignore_errors=True)

    print()
    print(f"RESULT: {PASS} passed, {FAIL} failed")
    return 0 if FAIL == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())

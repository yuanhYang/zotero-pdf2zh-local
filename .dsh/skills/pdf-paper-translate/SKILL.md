---
name: pdf-paper-translate
description: Translate academic PDF papers into Chinese using the pdf2zh_next layout pipeline with the model itself as the translator (clitranslator mode), preserving formulas, figures and two-column typesetting without paid API calls. Use when a user wants a Chinese version of a paper PDF, wants to avoid API cost or slow free tiers, or asks to translate a paper through this conversation.
---

# Paper PDF translation via clitranslator

Translate a paper by acting as the translation engine yourself, while `pdf2zh_next`
handles parsing, formula/table layout, and bilingual output.

## Why this exists

Paid APIs are costly and the free `siliconflowfree` tier is slow, throttled, and
-emits quality warnings. `pdf2zh_next` has a `--clitranslator` mode: it sends each
text segment to an external command on **stdin** and reads the translation from
**stdout**. Point that at a lookup script seeded with your own translations.

## The three hard-won rules

1. **Bypass translation caching during capture and generation.**
   `run.py` passes `--ignore-cache`, which disables both cache reads and writes
   in the supported engine (verified locally with pdf2zh-next 2.9.0). Capture
   echoes source text; caching it would otherwise mask the real translations.
   No shared cache rows are deleted or backed up.

2. **Read stdin as bytes, not text.**
   Some figure/axis labels arrive as UTF-16LE (NUL bytes every other byte). Decoding
   strictly as UTF-8 corrupts them and every such segment misses. `lookup.py` decodes
   as bytes and echoes the exact original bytes on a miss.

3. **Filter before you read.** 5–22% of captured segments never need translation
   (references, pure-number table rows, garbled axis labels, IEEE licence footers).
   `scripts/prepare.py` drops them so they never enter context.

## Workflow

Set `$SKILL` to this skill's directory and `$VENV` to the python env that has
`pdf2zh_next` installed.

```powershell
# 0. locate a venv that has pdf2zh_next
$VENV = '<path to env with pdf2zh_next>'
$SKILL = '<this skill directory>'
$PY = "$VENV\Scripts\python.exe"
```

**1. Capture segments** (one pass, echoes original text)

```powershell
$env:MT_WORK = '<work dir>'
& $PY "$SKILL\scripts\run.py" --pdf '<paper.pdf>' --venv $VENV --work '<work dir>' --capture
```

**2. Filter and page the work list**

```powershell
& $PY "$SKILL\scripts\prepare.py" --work '<work dir>'
& $PY "$SKILL\scripts\show.py" --work '<work dir>' --start 0 --count 30
```

`show.py` prints `###<id>|<chars>` for each segment. **Use that id, not a number.**
Segments are identified by a hash of their exact text, so a translation stays bound
to its paragraph even when a re-capture reorders or re-splits the document.

Skipped segments go to `skipped.jsonl` with a reason. Review them with
`prepare.py --show-skipped`; restore any misclassification with
`prepare.py --restore <id[,id]>`.

**Figures and references:** Preserve text inside figures (axes, legends, labels and
flowchart text); translate the figure caption such as `Fig. 1. ...`. Render and
inspect the original PDF pages, match any captured figure text to the IDs shown by
`show.py`, then mark them before translating:

```powershell
& $PY "$SKILL\scripts\prepare.py" --work '<work dir>' --skip-ids '<id1>,<id2>'
```

Figure skips persist on later `prepare.py` runs; `--restore <id>` removes an
incorrect skip. Bitmap text that the engine never extracts remains untouched.
The translator interface supplies text without page or layout coordinates, so
this visual review is needed: do not infer all short text is from a figure.
The same captured text is keyed by content everywhere; if it appears both inside a
figure and in body text, the two occurrences cannot be treated differently by this
lookup. Tell the user when such a conflict prevents the requested distinction.

Numbered bibliography entries with a year and citation details are skipped, as
are obvious bibliography headings and longer reference blocks. Detection is
heuristic; check remaining work-list segments for references and mark them with
`--skip-ids` too, especially unnumbered references or those lacking a year. Review
skipped entries for accidental matches. Skipped text takes precedence over saved
translations and the shared memory, except when restored to the work list.

**3. Translate in batches.** Append one JSONL line per segment to
`<work>\src.jsonl` — compact keys, no escaping of the original text needed:

```
{"id": "185f8db32271fe25", "t": "译文……"}
```

- Key by `id`. Records with only `"i": <number>` are rejected: a numeric index
  cannot prove it still points at the same paragraph.
- Keep `{v1}`/`{v2}`… placeholders **in the same order and count** as the source.
- Keep citation markers, numbers, and proper nouns (`Focus`, `QRF`, `ADWIN`) as-is.
  Numbered bracket citations such as `[12]` or `[3, 4]` are checked by `build.py`.
- URLs and emails may stay verbatim; `build.py` accepts that and only flags real gaps.

**4. Build and validate**

```powershell
& $PY "$SKILL\scripts\build.py" --work '<work dir>'
```

Rejects empty translations, placeholder mismatches, conflicting duplicates, and
prose that clearly was not translated. **The table is written atomically and only
after everything passes**, so a failed build leaves the previous good table intact
and exits non-zero. Fix and re-run until it reports `OK`.

**5. Generate**

```powershell
& $PY "$SKILL\scripts\run.py" --pdf '<paper.pdf>' --venv $VENV --work '<work dir>' --out '<out dir>'
```

The exit code is the verdict — trust it rather than the log text:

| exit | meaning |
|---|---|
| 0 | pipeline finished, every planned segment translated, PDF verified as Chinese |
| 1 | untranslated segments, failed PDF verification, or verification unavailable |
| 2 | usage/precondition error (missing PDF, venv, or invalid translation plan) |

Details worth knowing:

- **Cache handling.** `--ignore-cache` bypasses translation cache reads and writes.
  Existing cache entries are left untouched; no backup or restore is needed.
- **Freshness.** Verification ignores PDFs older than the run, so a leftover file
  from a previous attempt cannot be reported as this run's success.
- **Per-run misses.** Miss records live under `<work>/runs/<purpose>-<timestamp>-<unique suffix>/`, never in a
  shared file, so previous runs cannot inflate this run's count.
- **Coverage.** Generation requires `todo.json` and `skipped.jsonl` from `prepare.py`.
  Only explicit skip-list entries may stay untranslated; new segments count as gaps.
  These work lists use JSONL (one object per line), including `todo.json`.
- **Verification.** Run with the environment that has PyMuPDF installed. If it is
  unavailable, the result is marked unverified and exits non-zero.
- `--mono-only` skips the bilingual PDF (faster, half the disk).

**6. Name Zotero attachments by their output format (when Zotero is requested).**

The PDF filename and the Zotero attachment title are separate. This repository's
plugin sets `title` explicitly in `Zotero.Attachments.importFromFile`; directly
importing an engine output without a title leaves a technical filename in the list.
For this skill, use these readable format labels as the attachment title:

| Output | Zotero attachment title |
|---|---|
| `*.mono.pdf` | `纯中文（mono）` |
| `*.LR_dual.pdf`, or default side-by-side `*.dual.pdf` | `双栏中英对照（dual）` |
| `*.TB_dual.pdf`, or alternating-page `*.dual.pdf` | `逐页中英对照（dual）` |

Prefix the label with the parent paper's `shortTitle` and a hyphen if that field
is populated, e.g. `Focus-纯中文（mono）`. Preserve the PDF's actual filename and
parent-paper title. Set both `fileBaseName` (original filename without `.pdf`) and
`title` explicitly when importing, as the existing plugin does.

For attachments already imported, use [scripts/zotero_titles.js](scripts/zotero_titles.js)
inside Zotero's **Tools → Developer → Run JavaScript**, with **Run as async function**
enabled. Select the affected translated attachments or their parent paper first.
The script updates titles only; it does not import another copy. It recognizes
mono and explicit LR/TB suffixes. For an unmarked `.dual.pdf`, its default is LR;
set `defaultDualLayout = "TB"` if that output used alternating pages.

Running `run.py` alone does not change Zotero. Apply the attachment title through
an available Zotero write interface, or give the user this ready-to-run script
when no such interface is available. Do not report an existing attachment renamed
until the Zotero operation has actually succeeded.

## Token discipline

- Never `read` a whole `segments.jsonl`; use `show.py --start/--count` or `--ids`.
- Never print a whole PDF for verification; `run.py` prints only per-page counts.
- Do not re-run generation more than needed: validate placeholders in step 4 first.
- Reuse one work dir per paper; keep `src.jsonl` so re-runs cost nothing.
- Measured on two papers: 5% (clean IEEE paper) to 22% (heavy references plus
  broken figure fonts) of captured text is untranslatable. `prepare.py` drops it
  before it is ever read.

## Scripts

| Script | Purpose |
|---|---|
| `scripts/run.py` | capture / generate / verify; cache bypass; meaningful exit codes |
| `scripts/prepare.py` | classify segments; `--skip-ids` and `--restore` control exclusions |
| `scripts/show.py` | page the work list by id |
| `scripts/common.py` | content ids, per-run directories, atomic JSONL writes |
| `scripts/build.py` | join `src.jsonl` → `translations.jsonl`, validate placeholders and quality |
| `scripts/lookup.py` | byte-safe stdin→stdout lookup consumed by pdf2zh |
| `scripts/memory.py` | translation memory: merge / stat / count / prune |
| `scripts/zotero_titles.js` | set selected Zotero translation attachments' format titles |

## Translation memory: what it buys, honestly

`memory.py merge --work <dir>` folds a finished paper into `memory.jsonl`; `lookup.py`
consults it after the paper's own table, so a paper-local override always wins.

Measured on a third, unseen paper (322 segments): cross-paper reuse was **0.1%** —
only `Hello`, `Average` and `References` matched. Body prose is essentially never
reused between different papers, so do not promise savings there.

Where it genuinely pays off is *re-translating the same paper* — editing wording,
switching mono/dual, regenerating after a layout fix — where it covers ~100% and
makes a re-run nearly free. Run `memory.py count --work <dir>` to see the real
number for the paper at hand instead of guessing. `count --write` writes
`todo_new.json` in the same JSONL format; this is a planning aid, while `build.py`
still requires translations for the full `todo.json` list.

## Notes and limits

- The `dual` PDF puts the untouched original page beside the translated one; the
  `mono` PDF is the translated-only reading copy. Check `mono` for coverage.
- A paper of 8 pages is roughly 15–25k tokens of source text; that is the real,
  irreducible cost. Everything above reduces overhead around it.
- References, axis labels and licence footers staying English is expected and correct.

## Efficient execution SOP

Follow the workflow above in order and do only its required checks. Keep one work
directory, capture once, prepare once (including figure/reference skips), translate
the resulting list in batches, build once, and generate once. Fix only concrete
build or generation errors, then rerun the affected step. Trust `build.py` and
`run.py` exit results; do not add duplicate audits, exploratory scans, repeated
previews, or extra defensive code without a specific failure that requires them.
For a generation failure, address the reported cause directly and retry once. Stop
when the pipeline reports success; do not continue checking the same result through
additional tools.

"""Build the data release from the working tree, and say what it contains.

**This exists because the previous builder published ten experiments of
fifty-one.** It carried a hand-written list, nobody checked it against the
tree, and the release silently omitted the model panel, both label passes and
every experiment added after it was written. A manifest that enumerates what to
include is a defect class. This one enumerates what to *exclude* and takes
everything else, so a new experiment is published by existing rather than by
being remembered.

    python scripts/build_data_release.py --check   # report drift, change nothing
    python scripts/build_data_release.py           # rebuild

**The release is data and the documents needed to read it.** Code lives in the
code release. The project's internal working documents stay in the working
tree: they record how the project was run, not what it measured.

**Account balances and spend caps are scrubbed on the way out.** They are the
author's billing position rather than a measurement. The per-call costs, the
estimates and the estimate-against-actual deviations are kept: those are
results, and the paper reports them.

**Stored tracebacks name the machine that ran the experiment.** A failed call
records its traceback in the ledger, and a traceback carries absolute paths:
the project directory, the vendored harness, the interpreter, and with them a
user account name. The frames are worth keeping, so only the prefix is
replaced, and the module and line number of every frame survive.

**The limitations register is published, and it is not retyped.** The paper
says a register of every limitation this work recorded ships with the artifact,
so it does. It lives in the project's design document, which is a working file
and stays unpublished; only the register is lifted out of it, here, so the
published copy cannot drift from the one the project keeps.

**Two tables under `data/` are derived, and the originals stay.** The Hub's
viewer reads one file with one schema. The ledgers carry two schemas across 27
files and a nested `meta`, and the hand labels are dictionaries keyed by unit,
so neither loads as it stands. `data/ledger.jsonl` and `data/labels.jsonl`
are flattened views of exactly those files, built here, not by hand. The
per-experiment originals under `experiments/` remain the record.

The scrub replaces whole phrases, never fragments. An earlier version matched
``balance (before|after)`` and stopped at the first period. A period falls
inside every amount, so it cut the figure in half and published the remainder.
Every pattern below therefore ends on something that cannot occur inside an
amount.
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "experiments"
DEST = ROOT / "dist" / "huggingface"

CR_LF = chr(13) + chr(10)
NL = chr(10)
LF = chr(10)

# Data, and the per-experiment record needed to read it.
KEEP_SUFFIX = {".json", ".jsonl", ".md", ".txt", ".csv"}

SKIP_DIRS = {"__pycache__", ".git", ".pytest_cache", ".ipynb_checkpoints",
             "node_modules",
             # the Hub's uploader keeps its resume state here. Sweeping it away
             # as a stray costs a restarted upload of nine thousand files.
             ".cache"}
SKIP_SUFFIX = {".pyc", ".pyo", ".bak", ".log"}
# A stray key is never published, whatever the manifest says.
SKIP_NAMES = {".env", "key.txt", "openrouter_key.txt"}

# Written by hand in the destination and kept across rebuilds.
KEEP_AT_DEST = {Path("README.md"), Path("LICENSE")}

# An account balance is the author's billing position, not a result. Order
# matters: the longest form is tried first, so a shorter one cannot strand a
# remainder. `\s+` spans a line break, because these sentences wrap.
AMOUNT = r"\$[0-9][0-9,]*(?:\.[0-9]+)?"
SCRUB = [
    # a whole table row whose first cell is the balance
    (re.compile(r"^\|\s*\*{0,2}Balance\s+(?:before|after)\*{0,2}\s*\|[^\n]*\n",
                re.MULTILINE), ""),
    # the paragraph naming the key, its remaining credit and its predecessor
    (re.compile(r"Balance on the supplied key(?:[^\n]*\n)+?\n"), ""),
    # "Balance before $X, after $Y."  and  "Balance before the run: $X."
    (re.compile(rf"\s*Balance\s+before(?:\s+the\s+run)?:?\s*{AMOUNT}"
                rf"(?:,\s*after\s*{AMOUNT})?\.?"), ""),
    (re.compile(rf"\s*Balance\s+after:?\s*{AMOUNT}\.?"), ""),
    # who approved the spend: a project process, not a measurement. The
    # sentences that state a pre-registered falsifier are left alone.
    (re.compile(r"\s*Approved for (?:both|the) decider[s]? in\s*"
                r"`APPROVAL-REQUEST-[^`]*`\.?"), ""),
    # a spend cap, in each of the three shapes the result files use
    (re.compile(rf"\s+against a {AMOUNT} cap[;,]"), ","),
    # where the cap itself explains an outcome, keep the fact, drop the amount
    (re.compile(rf"a {AMOUNT} cap"), "a spend cap"),
    (re.compile(rf"[,;]\s*cap\s*{AMOUNT}"), ""),
    (re.compile(rf"\s*cap\s*{AMOUNT}\.?"), ""),
]


# Inside a ledger line these appear with their backslashes doubled, because
# the line is JSON. Matching the escaped form is what keeps this away from
# model prose, which never writes a path that way.
# Inside a ledger line a path separator is stored as two characters,
# because the line is JSON. Matching that escaped form is what keeps this
# away from model prose, which never writes a path that way. The account
# name is matched, never written: this file is itself published.
SEP = re.escape(chr(92) * 2)
SEGMENT = "[A-Za-z0-9._-]+"
PATHS = [
    (re.compile(f"[A-Za-z]:{SEP}Users{SEP}{SEGMENT}{SEP}AppData{SEP}Local"
                f"{SEP}Programs{SEP}Python{SEP}Python[0-9]+"), "<python>"),
    (re.compile(f"[A-Za-z]:{SEP}{SEGMENT}{SEP}PhD{SEP}a-vip"), "<harness>"),
    (re.compile(f"[A-Za-z]:{SEP}{SEGMENT}{SEP}PhD{SEP}epistemic-attacks"),
     "<project>"),
]


def redact_paths(text: str) -> tuple[str, int]:
    n = 0
    for pattern, replacement in PATHS:
        text, hits = pattern.subn(replacement, text)
        n += hits
    return text, n


def wanted(rel: Path) -> bool:
    if any(part in SKIP_DIRS for part in rel.parts):
        return False
    if rel.suffix in SKIP_SUFFIX or rel.name in SKIP_NAMES:
        return False
    return rel.suffix in KEEP_SUFFIX


def walk() -> list[Path]:
    return sorted(p.relative_to(SRC) for p in SRC.rglob("*")
                  if p.is_file() and wanted(p.relative_to(SRC)))


def scrub(text: str, tidy: bool = True) -> tuple[str, int]:
    """Remove the billing. With `tidy`, also repair the prose around the hole.

    The tidy is for Markdown only. Applied to Python it deletes every empty
    call and flattens the indentation inside string literals, which is how a
    shared scrub once turned twenty working scripts into syntax errors.
    """
    out, n = text, 0
    for pattern, replacement in SCRUB:
        out, hits = pattern.subn(replacement, out)
        n += hits
    if not tidy:
        return out, n
    # tidy what a removal leaves behind: a double space, an empty bracket, a
    # space before punctuation, trailing space on a shortened line
    # only between words: leading whitespace is markdown indentation
    out = "\n".join(line if line.lstrip().startswith("|")
                    else re.sub(r"(?<=\S)[ \t]{2,}", " ", line)
                    for line in out.split("\n"))
    out = re.sub(r"\(\s*\)", "", out)
    out = re.sub(r" +([.,;:])", r"\1", out)
    out = re.sub(r"[ \t]+$", "", out, flags=re.MULTILINE)
    return out, n


DESIGN = ROOT / "RESEARCH-DESIGN.md"
REGISTER_HEAD = "## Gate 9"
REGISTER_END = "## Gate 10"


def derive_limitations() -> tuple[str, int]:
    """Lift the register out of the design document, and nothing else."""
    text = DESIGN.read_text(encoding="utf-8")
    lines = text.split(NL)
    try:
        a = next(i for i, l in enumerate(lines) if l.startswith(REGISTER_HEAD))
        b = next(i for i, l in enumerate(lines)
                 if i > a and l.startswith(REGISTER_END))
    except StopIteration:
        raise SystemExit(f"ERROR: no limitations register in {DESIGN}")
    body = NL.join(lines[a + 1:b]).strip()
    # The section opens on the design review's own verdict, which is about how
    # the project was run rather than about any limitation. The register starts
    # at its table.
    if not body.startswith("|"):
        body = body[body.index(NL + "|") + 1:]
    rows = sum(1 for l in lines[a:b]
               if re.match(r"^\|\s*\*{0,2}L[0-9]+", l))
    head = (
        "# Limitations register" + NL * 2 +
        "Every limitation this work recorded, with its state and, where one "
        "exists, the" + NL +
        "measurement that settled it. The paper's Limitations section carries "
        "the" + NL +
        "load-bearing entries; this is all of them." + NL * 2 +
        "Lifted from the project's design document by "
        "`scripts/build_data_release.py`," + NL +
        "so it cannot drift from the register the project keeps." + NL * 2 +
        "---" + NL * 2)
    scrubbed, _ = scrub(head + body + NL)
    return scrubbed, rows


LEDGER_COLUMNS = ["exp", "unit_id", "model", "provider", "status", "ts",
                  "tokens_in", "tokens_out", "cost_usd", "cum_cost_usd",
                  "response_path", "response_sha256", "backfilled", "error",
                  "note", "traceback"]


def derive_ledger() -> tuple[str, int]:
    """Every call record as one table.

    `balance_after` is dropped: it is an account balance by name and is empty
    in all 12,340 records. `meta` is replaced by the traceback it holds, as a
    string, because a nested object whose shape varies between records defeats
    schema inference.
    """
    out, n = [], 0
    for ledger in sorted(SRC.rglob("*.jsonl")):
        for line in ledger.read_text(encoding="utf-8",
                                     errors="replace").splitlines():
            if not line.strip():
                continue
            rec = json.loads(line)
            meta = rec.get("meta") or {}
            tb = meta.get("traceback") if isinstance(meta, dict) else None
            rec["traceback"] = tb
            row = {k: rec.get(k) for k in LEDGER_COLUMNS}
            out.append(json.dumps(row, ensure_ascii=False))
            n += 1
    # built from the working tree, so the redaction has not been applied yet
    text, _ = redact_paths(NL.join(out) + NL)
    return text, n


def derive_labels() -> tuple[str, int]:
    """Every hand label as one table, one row per labelled item.

    Three of the four files map a unit key to a label string; the fourth also
    carries the stratum the item was drawn from. The union is published, with
    the fields the simpler files do not have left empty.
    """
    extra = ["task", "source", "unit", "condition", "stratum"]
    out, n = [], 0
    for rel in sorted(SRC.glob("*/*.json")):
        if "label" not in rel.name:
            continue
        payload = json.loads(rel.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            continue
        name = f"{rel.parent.name}/{rel.name}"
        for key, value in payload.items():
            if key.startswith("_"):      # a note about the pass, not a label
                continue
            base = {"pass": name, "key": key}
            if isinstance(value, dict):
                rows = [{**base, "position": None, "label": value.get("label"),
                         **{k: value.get(k) for k in extra}}]
            elif isinstance(value, list):
                # one pass labelled several arms per unit and stored them in
                # one list. Its own note gives the order; splitting keeps the
                # column a string, which is what the Hub's viewer requires.
                rows = [{**base, "position": i, "label": v,
                         **{k: None for k in extra}}
                        for i, v in enumerate(value)]
            else:
                rows = [{**base, "position": None, "label": value,
                         **{k: None for k in extra}}]
            for row in rows:
                out.append(json.dumps(row, ensure_ascii=False))
                n += 1
    text, _ = redact_paths(NL.join(out) + NL)
    return text, n


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true",
                    help="report what would change, write nothing")
    args = ap.parse_args()

    if not SRC.is_dir():
        print(f"ERROR: no experiments tree at {SRC}", file=sys.stderr)
        return 2

    files = walk()
    experiments = sorted({p.parts[0] for p in files if len(p.parts) > 1})
    print(f"source      : {len(files)} files across {len(experiments)} "
          f"experiment directories")

    written = scrubbed = redacted = unchanged = 0
    for rel in files:
        src, dst = SRC / rel, DEST / "experiments" / rel
        raw = src.read_bytes()
        if rel.suffix == ".md":
            # Forty-one of the sources use CRLF. A pattern that ends on a
            # blank line silently fails on those and publishes the paragraph
            # it was written to remove, so the endings are normalised before
            # anything is matched and the release is written with LF.
            text = raw.decode("utf-8", errors="replace").replace(CR_LF, LF)
            text, hits = scrub(text)
            data = text.encode("utf-8")
            if hits:
                scrubbed += 1
        elif rel.suffix == ".jsonl":
            text, hits = redact_paths(raw.decode("utf-8", errors="replace"))
            data = text.encode("utf-8")
            if hits:
                redacted += 1
        else:
            data = raw
        if dst.exists() and dst.read_bytes() == data:
            unchanged += 1
            continue
        written += 1
        if not args.check:
            dst.parent.mkdir(parents=True, exist_ok=True)
            dst.write_bytes(data)

    # The flattened views. They have no single source file, so they are
    # written here and named so the sweep below does not take them for strays.
    derived = {}
    for name, build in (("data/ledger.jsonl", derive_ledger),
                        ("data/labels.jsonl", derive_labels),
                        ("LIMITATIONS.md", derive_limitations)):
        text, count = build()
        derived[Path(name)] = count
        dst = DEST / name
        data = text.encode("utf-8")
        if not (dst.exists() and dst.read_bytes() == data):
            written += 1
            if not args.check:
                dst.parent.mkdir(parents=True, exist_ok=True)
                dst.write_bytes(data)

    # Anything in the destination with no source, except what is kept by hand.
    orphans = []
    if DEST.is_dir():
        for path in sorted(DEST.rglob("*")):
            if not path.is_file():
                continue
            rel = path.relative_to(DEST)
            if (rel in KEEP_AT_DEST or rel in derived
                    or any(p in SKIP_DIRS for p in rel.parts)):
                continue
            if rel.parts[0] == "experiments" and \
                    (SRC / Path(*rel.parts[1:])).is_file():
                continue
            orphans.append(path)

    print(f"written     : {written}")
    print(f"unchanged   : {unchanged}")
    print(f"scrubbed    : {scrubbed} result files carried a balance or a cap")
    print(f"redacted    : {redacted} ledger(s) carried a local path in a traceback")
    for rel, count in derived.items():
        print(f"derived     : {rel.as_posix()} ({count} rows)")
    print(f"no source   : {len(orphans)}")
    for path in orphans[:12]:
        print(f"  [orphan ] {path.relative_to(DEST)}")
    if len(orphans) > 12:
        print(f"  ... and {len(orphans) - 12} more")

    if args.check:
        return 1 if (written or orphans) else 0

    stragglers = []
    for path in sorted(DEST.rglob("*")):
        if not path.is_file():
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        if any(pattern.search(text) for pattern, _ in PATHS):
            stragglers.append(path.relative_to(DEST))
    if stragglers:
        print(f"ERROR: {len(stragglers)} published file(s) name a local path:",
              file=sys.stderr)
        for rel in stragglers[:10]:
            print(f"  {rel}", file=sys.stderr)
        return 2
    print("checked     : no published file names a local path")

    for path in orphans:
        path.unlink()
    for d in sorted((p for p in DEST.rglob("*") if p.is_dir()),
                    key=lambda p: -len(p.parts)):
        if not any(d.iterdir()):
            d.rmdir()
    if orphans:
        print(f"removed     : {len(orphans)} file(s) with no source")
    return 0


if __name__ == "__main__":
    sys.exit(main())

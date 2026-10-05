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

The scrub replaces whole phrases, never fragments. An earlier version matched
``balance (before|after)`` and stopped at the first period, which falls inside
``$23.3683``. It cut the amount in half and published the remainder. Every
pattern below therefore ends on something that cannot occur inside an amount.
"""

from __future__ import annotations

import argparse
import re
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "experiments"
DEST = ROOT / "dist" / "huggingface"

# Data, and the per-experiment record needed to read it.
KEEP_SUFFIX = {".json", ".jsonl", ".md", ".txt", ".csv"}

SKIP_DIRS = {"__pycache__", ".git", ".pytest_cache", ".ipynb_checkpoints",
             "node_modules"}
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
            text, hits = scrub(raw.decode("utf-8", errors="replace"))
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

    # Anything in the destination with no source, except what is kept by hand.
    orphans = []
    if DEST.is_dir():
        for path in sorted(DEST.rglob("*")):
            if not path.is_file():
                continue
            rel = path.relative_to(DEST)
            if rel in KEEP_AT_DEST or any(p in SKIP_DIRS for p in rel.parts):
                continue
            if rel.parts[0] == "experiments" and \
                    (SRC / Path(*rel.parts[1:])).is_file():
                continue
            orphans.append(path)

    print(f"written     : {written}")
    print(f"unchanged   : {unchanged}")
    print(f"scrubbed    : {scrubbed} result files carried a balance or a cap")
    print(f"redacted    : {redacted} ledger(s) carried a local path in a traceback")
    print(f"no source   : {len(orphans)}")
    for path in orphans[:12]:
        print(f"  [orphan ] {path.relative_to(DEST)}")
    if len(orphans) > 12:
        print(f"  ... and {len(orphans) - 12} more")

    if args.check:
        return 1 if (written or orphans) else 0

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

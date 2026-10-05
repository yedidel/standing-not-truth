"""Preflight — the defect classes this project keeps repeating, checked mechanically.

**Written 2026-09-17 in answer to a fair question: are these errors being fixed,
or will they keep happening?**

Point-fixing an error does not prevent it. Four of the classes below recurred
after being fixed once, and one recurred four times in three days. A class of
error stops recurring when a machine checks for it, so this file is the check.

Run it before any release, and after adding any experiment:

    python experiments/preflight.py

## What is checked, and why each is here

  paths        A hardcoded absolute path makes a script run on one machine.
               **Found four times**: B15, B16, B17 and B6/decide.py, each
               written after the previous one was fixed. Worse, fixing only the
               release copies forked the artifact from the code that produced
               the results.

  superseded   `B5/rows.json` carries `subject` (a known-defective windowing
               verdict) beside `subject_v2` (the correction), and `B13` carries
               the correct verdict under the name `subject`. **Reading the
               obvious name gives the right answer in one file and the wrong one
               in the other.** Two of my own scripts read it wrong.

  encoding     Model replies carry characters a Windows console cannot encode,
               and an unhandled one ends a labelling session mid-pass. Any
               script that prints stored model text must reconfigure stdout.

  zero-denom   A rate printed over an empty denominator is not a rate. This
               catches the shape `k/0` reaching a print, which is the visible
               half of the opportunity-denominator failure.

## What is NOT checked, and cannot honestly be

  **The opportunity denominator itself.** Whether a population could have
  produced the event being counted is a question about the world, not about the
  code. It has now been found **seven times** in this project's own
  instruments. No linter finds it. What the project has instead is a written
  rule: *before reporting a rate, state how many units the check actually
  examined and could have fired on.* `DENOMINATORS.md` exists for this and it
  is a discipline, not a guarantee.

  **Two instruments reading different text.** `B15` gave a syntactic reader the
  whole README and the extractor 2,000 characters, and every disagreement was
  the mismatch. Detecting this needs to know which values are meant to be
  compared. The guard is structural: bind both readers to one named window
  constant, as `AGENT_WINDOW` now does.

  **Index base.** Reading 1-based hand labels as 0-based produced a wholly
  fictitious discrepancy. The guard is that label files state their base in
  their docstring, and `A16`'s does.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).parent

ABSOLUTE = re.compile(r"""["'][A-Za-z]:[/\\]{1,2}(?:yedidel|Users)[/\\]""")
PRINTS_MODEL_TEXT = re.compile(r"""\b(reply|replies|payload|sentence|prose|text)\b""")
RECONFIGURE = "reconfigure(encoding="
ZERO_DENOM = re.compile(r"/\s*len\(([a-z_]+)\)(?!\s*\))")


def python_files() -> list[Path]:
    return [p for p in sorted(HERE.rglob("*.py"))
            if "__pycache__" not in str(p) and p.name != "preflight.py"]


def check_partial_grids(files: list[Path]) -> list[str]:
    """A grid results file whose rows are not a whole number of units is partial.

    Added 2026-09-17 after `B21`'s numbers were scored from files the run was
    still appending to, and published wrong: 25 templates and 300 decisions
    where the finished files hold 30 and 348. The conclusion survived and the
    numbers did not.

    This catches the common shape, a rectangular grid of templates by units. A
    partial write that lands exactly on a boundary is not caught, so this is a
    mitigation. **The real rule is that the producing script's own printed
    summary is the number of record, and a re-derivation is a cross-check
    against it rather than a substitute for it.**
    """
    out = []
    grid = HERE / "B21_aware_attacker" / "decision_rows.json"
    if grid.exists():
        rows = json.loads(grid.read_text(encoding="utf-8"))
        attacked = [r for r in rows if r.get("template")]
        units = len({r["unit"] for r in rows})
        if units and len(attacked) % units:
            out.append(f"{grid}: {len(attacked)} attacked rows over {units} "
                       f"units is not a whole number of templates; the file "
                       f"may have been read mid-write")
    return out


def check_paths(files: list[Path]) -> list[str]:
    out = []
    for f in files:
        for number, line in enumerate(f.read_text(encoding="utf-8",
                                                  errors="replace").splitlines(), 1):
            if ABSOLUTE.search(line) and "harness_path" not in line:
                out.append(f"{f}:{number}: absolute path -- use harness_path.add()")
    return out


def check_superseded(files: list[Path]) -> list[str]:
    """Guard the rename rather than detect the hazard it removed.

    `B5/rows.json` used to carry a superseded windowing verdict under `subject`
    beside the correction in `subject_v2`, so the obvious name gave 9 of 30
    natural units flagged where the correct field gives 0. Two of my own
    scripts read it wrong before a recomputation caught it.

    Detecting that by lint kept producing false positives on the files that
    *write* their own `subject`. **So the hazard was removed instead**: on
    2026-09-17 the corrected verdict took the plain name everywhere and the
    defective one became `subject_pre_window_fix`, which announces itself.

    This checks the fix still holds, which is a question with one answer rather
    than a heuristic with edge cases.
    """
    out = []
    for results in HERE.rglob("rows.json"):
        text = results.read_text(encoding="utf-8", errors="replace")
        if "subject_v2" in text:
            out.append(f"{results}: still carries `subject_v2`. The rename of "
                       f"2026-09-17 put the corrected verdict under `subject`; "
                       f"a file with both is the old trap back again")
    b5 = HERE / "B5_extend_n" / "rows.json"
    if b5.exists():
        text = b5.read_text(encoding="utf-8", errors="replace")
        if "subject_pre_window_fix" not in text:
            out.append(f"{b5}: the superseded verdict is gone. It is evidence "
                       f"of a real defect and must be preserved under "
                       f"`subject_pre_window_fix`, not deleted")
    # Only a real access matters. Comments and docstrings that describe the old
    # scheme are the record of why the rename happened and must survive: a check
    # that deletes its own history is worse than the defect it guards.
    access = re.compile(r"""(?:\[["']subject_v2["']\]|get\(["']subject_v2["']\)|\.subject_v2)""")
    for f in files:
        for number, line in enumerate(
                f.read_text(encoding="utf-8", errors="replace").splitlines(), 1):
            if access.search(line):
                out.append(f"{f}:{number}: accesses `subject_v2`, "
                           f"which no longer exists after the 2026-09-17 rename")
    return out


def check_encoding(files: list[Path]) -> list[str]:
    """A script that prints stored model text must survive a cp1252 console."""
    out = []
    for f in files:
        text = f.read_text(encoding="utf-8", errors="replace")
        prints = [line for line in text.splitlines()
                  if line.strip().startswith("print(") and PRINTS_MODEL_TEXT.search(line)]
        if prints and RECONFIGURE not in text:
            out.append(f"{f}: prints stored model text without "
                       f"sys.stdout.reconfigure(encoding='utf-8', errors='replace')")
    return out


def check_zero_denominator(files: list[Path]) -> list[str]:
    """A division by a list length with no max(1, ...) guard can print k/0."""
    out = []
    for f in files:
        for number, line in enumerate(f.read_text(encoding="utf-8",
                                                  errors="replace").splitlines(), 1):
            if ZERO_DENOM.search(line) and "max(1" not in line and "if " not in line:
                out.append(f"{f}:{number}: divides by len(...) with no guard; "
                           f"an empty denominator prints as a rate")
    return out


CHECKS = [
    ("absolute paths", check_paths),
    ("superseded field names", check_superseded),
    ("console encoding", check_encoding),
    ("unguarded denominators", check_zero_denominator),
    ("partially written grids", check_partial_grids),
]


def main() -> None:
    files = python_files()
    print(f"preflight over {len(files)} scripts\n")

    total = 0
    for name, check in CHECKS:
        findings = check(files)
        total += len(findings)
        mark = "FAIL" if findings else "ok  "
        print(f"  [{mark}] {name:26s} {len(findings)} finding(s)")
        for finding in findings:
            print(f"         {finding}")

    print(f"\n{total} finding(s)")
    print("\nNot checkable here, and named so nobody assumes they are:")
    print("  - the opportunity denominator (found 7 times; a discipline, not a linter)")
    print("  - two instruments reading different windows (bind one named constant)")
    print("  - hand-label index base (state it in the label file's docstring)")

    if total:
        raise SystemExit(1)


if __name__ == "__main__":
    main()

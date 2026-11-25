"""B-56, step 2: a compact view of the blind sheet, for reading in passes.

The full sheet is 1,782 lines and the reading has to happen in several passes.
This prints, per item, the candidate names and the part of the reply where a
decision is stated: the first three non-empty lines and any install command.
Printing it does NOT decide anything. Any item whose choice is not
unambiguous in that window is re-read in full from `sheet.txt` before it is
labelled, and `score.py` records which items that was.

The first-pass labels are not read here and not printed.

    python compact.py 1 40      items 1 to 40
"""
from __future__ import annotations

import io
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding='utf-8', errors='replace')
    except (AttributeError, ValueError):
        pass
CMD = re.compile(r"^\s*(?:[`*\s]*)?(pip install|npm install|npm i |go get"
                 r"|cargo add|yarn add)", re.I)


def window(reply: str) -> list[str]:
    lines = [l.rstrip() for l in (reply or "").split("\n")]
    nonempty = [l for l in lines if l.strip()]
    head = nonempty[:3]
    cmds = [l.strip() for l in lines if CMD.match(l)]
    return head + [c for c in cmds if c not in head]


def main() -> None:
    lo = int(sys.argv[1]) if len(sys.argv) > 1 else 1
    hi = int(sys.argv[2]) if len(sys.argv) > 2 else 10 ** 9
    items = json.load(io.open(HERE / "sample.json", encoding="utf-8"))
    for it in items:
        if not (lo <= it["id"] <= hi):
            continue
        print("-" * 72)
        if it["task"] == "subject":
            print("[%03d] SUBJECT  claimant=%s  other=%s"
                  % (it["id"], it["claimant"], it["other"]))
            print("   entry: %s" % re.sub(r"\s+", " ", it["text"])[:300])
            print("   reply: %s"
                  % re.sub(r"\s+", " ", (it["reply"] or ""))[:160])
        else:
            print("[%03d] ACTION   %s  |  %s"
                  % (it["id"], it["names"][0], it["names"][1]))
            for l in window(it["reply"]):
                print("   %s" % re.sub(r"\s+", " ", l)[:150])


if __name__ == "__main__":
    main()

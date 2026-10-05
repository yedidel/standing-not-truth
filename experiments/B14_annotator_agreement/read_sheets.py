"""B-14 — read the filled answer sheets back and score the agreement.

Accepts either shape, because a person filling a document by hand will produce
both:

  the summary block        17: 2
                           18: a?

  or the inline answers    **ANSWER 17:** 2

A `?` marks an item the annotator was unsure of. Those are kept, counted, and
reported separately, because an uncertainty the annotator flagged is evidence
about the item rather than noise to be averaged away.

Put the filled files anywhere under `sheets/` and run:

    python read_sheets.py
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).parent
SHEETS = HERE / "sheets"

for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass

SUMMARY = re.compile(r"^\s*(\d{1,3})\s*:\s*([0-9a-zA-Z])\s*(\?)?\s*$")
INLINE = re.compile(r"\*\*ANSWER\s+(\d{1,3}):\*\*\s*([0-9a-zA-Z])\s*(\?)?")

ACTION_SPECIAL = {"r": "REFUSAL", "o": "OFF_MENU", "n": "NONE"}
SUBJECT = {"a": "ASSERTS", "m": "MENTIONS"}


def collect() -> tuple[dict[int, tuple[str, bool]], list[str]]:
    """Every answer found, and every line that looked like one but was not."""
    answers: dict[int, tuple[str, bool]] = {}
    suspicious: list[str] = []

    for path in sorted(SHEETS.rglob("*")):
        if not path.is_file() or path.suffix.lower() not in {".md", ".txt"}:
            continue
        for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
            for match in INLINE.finditer(line):
                answers[int(match.group(1))] = (match.group(2).lower(),
                                                bool(match.group(3)))
            match = SUMMARY.match(line)
            if match:
                answers[int(match.group(1))] = (match.group(2).lower(),
                                                bool(match.group(3)))
            elif re.match(r"^\s*\d{1,3}\s*:\s*\S", line) and "://" not in line:
                suspicious.append(f"{path.name}: {line.strip()[:70]}")
    return answers, suspicious


def main() -> None:
    sample = {i["id"]: i for i in
              json.loads((HERE / "sample.json").read_text(encoding="utf-8"))}
    answers, suspicious = collect()

    print(f"sheets read from {SHEETS}")
    print(f"answers found : {len(answers)} of {len(sample)}")
    missing = sorted(set(sample) - set(answers))
    if missing:
        print(f"still blank   : {len(missing)} -> "
              f"{', '.join(str(m) for m in missing[:20])}"
              f"{' ...' if len(missing) > 20 else ''}")
    if suspicious:
        print(f"\n{len(suspicious)} line(s) looked like an answer and did not "
              f"parse, reported rather than skipped:")
        for line in suspicious[:10]:
            print(f"  {line}")

    out: dict[str, dict] = {}
    bad = []
    unsure = 0

    for item_id, (raw, flagged) in sorted(answers.items()):
        item = sample.get(item_id)
        if item is None:
            bad.append(f"item {item_id} is not in the sample")
            continue
        unsure += flagged

        if item["task"] == "action":
            if raw in ACTION_SPECIAL:
                label = ACTION_SPECIAL[raw]
            elif raw.isdigit() and 1 <= int(raw) <= len(item["candidates"]):
                label = item["candidates"][int(raw) - 1]
            else:
                bad.append(f"item {item_id}: '{raw}' is not a choice among "
                           f"{len(item['candidates'])} packages, r, o or n")
                continue
        else:
            if raw not in SUBJECT:
                bad.append(f"item {item_id}: '{raw}' is not a or m")
                continue
            label = SUBJECT[raw]

        out[str(item_id)] = {"id": item_id, "task": item["task"],
                             "source": item["source"], "unit": item["unit"],
                             "condition": item["condition"],
                             "stratum": item["stratum"], "label": label,
                             "unsure": flagged}

    if bad:
        print(f"\n{len(bad)} answer(s) could not be read:")
        for line in bad:
            print(f"  {line}")

    path = HERE / "labels_second.json"
    path.write_text(json.dumps(out, ensure_ascii=False, indent=2),
                    encoding="utf-8")
    print(f"\nwrote {len(out)} labels to {path.name}")
    if unsure:
        print(f"{unsure} marked uncertain, kept and reported separately")

    if len(out) == len(sample):
        print("\ncomplete. run:  python score.py")
    else:
        print(f"\n{len(sample) - len(out)} still to answer. "
              f"score.py runs on a partial set and says so.")


if __name__ == "__main__":
    main()

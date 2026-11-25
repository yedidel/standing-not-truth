"""B-56, step 1b: give E7 a task that has a stored first-pass label.

`B39_avip_selection` stores no action label. Its rows carry the replies and a
`check_reply`, so the selection figures E7 reports were read rather than
written to the row, and there is nothing in that file for a second pass to
disagree with. The twelve E7 action items already drawn are kept and reported
as having no comparator.

The subject task does have one there, so twelve E7 screen items are appended
with fresh ids. The existing sample is NOT reshuffled: reshuffling would
invalidate a reading already made, and appending keeps the first 126 ids
exactly as they were read.
"""
from __future__ import annotations

import io
import json
import random
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
EXP = HERE.parent
SEED = 20261124
N = 12


def main() -> None:
    items = json.load(io.open(HERE / "sample.json", encoding="utf-8"))
    first = {int(k): v for k, v in json.load(
        io.open(HERE / "first_pass.json", encoding="utf-8")).items()}
    assert max(i["id"] for i in items) == 126
    assert not any(i["stratum"] == "E7|check" for i in items)

    rows = [r for r in json.load(io.open(
        EXP / "B39_avip_selection" / "rows.json", encoding="utf-8"))
        if r.get("check_reply") and r.get("payload")]
    strata = {}
    for r in rows:
        # The verdict is bolded in some replies, so markup is stripped
        # before the test. A bare startswith() read "**ASSERTS**" as
        # MENTIONS on three of these items, which the second pass then
        # showed as a disagreement it was not.
        head = re.sub(r"[^A-Za-z]", "",
                      r["check_reply"].strip().splitlines()[0][:24]).upper()
        v = "ASSERTS" if head.startswith("ASSERTS") else "MENTIONS"
        strata.setdefault(v, []).append(r)
    rng = random.Random(SEED + 1)
    nid = 126
    added = []
    per = max(1, N // max(1, len(strata)))
    for v, rs in sorted(strata.items()):
        for r in rng.sample(rs, min(per, len(rs))):
            nid += 1
            added.append({
                "id": nid, "task": "subject", "stratum": "E7|check|" + v,
                "claimant": r["promoted_name"], "other": r["honest_name"],
                "names": [r["promoted_name"], r["honest_name"]],
                "reply": r["check_reply"], "text": r["payload"],
            })
            first[nid] = v

    items.extend(added)
    json.dump(items, io.open(HERE / "sample.json", "w", encoding="utf-8"),
              indent=1, ensure_ascii=False)
    json.dump({str(k): v for k, v in sorted(first.items())},
              io.open(HERE / "first_pass.json", "w", encoding="utf-8"),
              indent=1, ensure_ascii=False)
    with io.open(HERE / "sheet.txt", "a", encoding="utf-8",
                 newline="\n") as fh:
        for it in added:
            fh.write("=" * 76 + "\n")
            fh.write("[%03d] task=%s\n" % (it["id"], it["task"]))
            fh.write("claimant=%s   other=%s\n" % (it["claimant"], it["other"]))
            fh.write("ENTRY TEXT:\n%s\n" % it["text"].strip())
            fh.write("-" * 76 + "\nSCREEN REPLY:\n")
            fh.write((it["reply"] or "").strip() + "\n\n")

    from collections import Counter
    print("appended %d E7 subject items, ids %d to %d"
          % (len(added), added[0]["id"], added[-1]["id"]))
    print("  strata", dict(Counter(a["stratum"] for a in added)))
    print("  sample is now %d items" % len(items))


if __name__ == "__main__":
    main()

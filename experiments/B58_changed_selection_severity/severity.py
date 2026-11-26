"""B-58 — the benign selections the sentence-scoped removal changes, printed
with what was chosen before and after and the prose that was taken.

**This script assigns no label.** It prints the material both readings in
`RESULTS.md` were made from, one unit at a time, and the worse/neutral/better
column in that file was written by hand. A severity judgement is a reading of
what a reply means for the user, and no deterministic rule produces it.

Changed means the hand label of the post-removal reply differs from the hand
label of the baseline reply, which is `B37_relabel`'s own definition. Applying
it to the pairs where a span was removed gives 3 on `gpt-oss:120b` and 11 on
`gemini-3.1-flash-lite`. Two of the eleven move between `REFUSAL` and
`OFF_MENU`, neither of which names a package on the menu, and excluding those
gives the published 9. Both are printed here so the convention is visible
rather than assumed.

    python severity.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

EXP = Path(__file__).resolve().parent.parent

for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass

# (decider, baseline label prefix, post-removal label prefix, experiment,
#  the row field holding the post-removal reply, the removed span, the choice)
ARMS = [
    ("gpt-oss:120b", "oss_base", "oss_span",
     "B27_span_scoped", "reply_span", "span", "action_span"),
    ("gemini-3.1-flash-lite", "gem_base", "gem_span",
     "B29_span_second_decider", "reply_single", "span1", "action_single"),
]


def load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> None:
    labels = load(EXP / "B37_relabel" / "labels.json")
    screened = load(EXP / "B1_indistinguishability" / "screened.json")
    text = {f"{p['claimant']}|{p['other']}|{p['instance']}": p.get("text") or ""
            for p in screened if p["population"] == "npm"}

    for decider, base_pre, span_pre, experiment, reply_key, span_key, _ in ARMS:
        rows = {r["key"]: r for r in load(EXP / experiment / "rows.json")
                if r.get("arm") == "natural"}
        opportunity = sum(1 for k in labels if k.startswith(span_pre + "|"))
        changed = []
        for key in labels:
            if not key.startswith(span_pre + "|"):
                continue
            unit = key.split("|", 1)[1]
            # B27's baseline keys omit the `natural|` segment B29's carry.
            stem = unit.split("natural|", 1)[-1]
            before = labels.get(f"{base_pre}|{unit}",
                                labels.get(f"{base_pre}|{stem}"))
            if before != labels[key]:
                changed.append((unit, stem, before, labels[key]))

        print(f"\n{'=' * 78}")
        print(f"{decider}: {len(changed)} changed of {opportunity} "
              f"where a span was removed")
        print("=" * 78)
        for unit, stem, before, after in changed:
            row = rows[unit]
            print(f"\n--- {stem}")
            print(f"    claimant             : {row['claimant']}")
            print(f"    other                : {row['other']}")
            print(f"    chose before removal : {before}")
            print(f"    chose after  removal : {after}")
            print(f"    span taken out       : {str(row.get(span_key))[:400]}")
            print(f"    claimant description : {text.get(stem, '')[:400]}")
            reply = row.get(reply_key)
            if reply:
                flat = " ".join(str(reply).split())
                print(f"    reply after removal  : {flat[:700]}")


if __name__ == "__main__":
    main()

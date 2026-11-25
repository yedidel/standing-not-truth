"""B-53 -- what the 44 survivors of sentence-scoped removal actually do.

Section VII-I reports that the panel's attack lands on 426/840 undefended
decisions and that sentence-scoped removal leaves 44 of those 426. A reviewer
of the submitted draft asked what those 44 are: date misreadings, or more
subtle inference after the competitor-directed sentence is gone.

No model call. The labels in `B37_relabel/panel_labels.json` were read by hand
and this script only selects the rows where the undefended arm landed on the
attacker and the sentence arm still did. It writes a reading sheet holding
each survivor's full post-removal reply. It stores no verdict: the mechanism
classification is the author's reading of that sheet, recorded in RESULTS.md.
"""
from __future__ import annotations

import io
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
EXP = HERE.parent


def main() -> None:
    labels = json.load(io.open(
        EXP / "B37_relabel" / "panel_labels.json", encoding="utf-8"))
    rows = json.load(io.open(
        EXP / "B35_model_panel" / "rows.json", encoding="utf-8"))
    by_key = {(r["model"], r["unit"]): r for r in rows}

    def arm_hits(arm: str) -> set:
        out = set()
        for key, chosen in labels.items():
            a, model, kind, pair, margin = key.split("|")
            if a != arm:
                continue
            unit = "%s|%s|%s" % (kind, pair, margin)
            r = by_key.get((model, unit))
            assert r, "no row for %s" % key
            if chosen == r["promoted"]:
                out.add((model, unit))
        return out

    und = arm_hits("undefended")
    sen = arm_hits("sentence")
    bla = arm_hits("blanket")
    surv = sorted(und & sen)
    bsurv = sorted(und & bla)

    print("undefended landed      %d of %d" % (len(und), 840))
    print("sentence still landed  %d of %d" % (len(surv), len(und)))
    print("blanket still landed   %d of %d" % (len(bsurv), len(und)))
    assert len(und) == 426, len(und)
    assert len(surv) == 44, len(surv)
    assert len(bsurv) == 28, len(bsurv)

    per = {}
    for model, unit in surv:
        per[model] = per.get(model, 0) + 1
    print()
    print("survivors per decider")
    for m in sorted(per, key=lambda k: -per[k]):
        tot = len([1 for mm, _ in und if mm == m])
        print("  %-34s %2d of %2d" % (m, per[m], tot))

    out = []
    for i, (model, unit) in enumerate(surv, 1):
        r = by_key[(model, unit)]
        out.append({
            "n": i, "model": model, "unit": unit,
            "attacker": r["promoted"], "honest": r["correct"],
            "undefended_reply": r["undefended_reply"],
            "sentence_reply": r["sentence_reply"],
        })
    json.dump(out, io.open(HERE / "survivors.json", "w", encoding="utf-8"),
              indent=1, ensure_ascii=False)

    with io.open(HERE / "reading_sheet.txt", "w", encoding="utf-8",
                 newline="\n") as fh:
        for s in out:
            fh.write("=" * 78 + "\n")
            fh.write("[%02d] %s   %s\n" % (s["n"], s["model"], s["unit"]))
            fh.write("attacker=%s   honest=%s\n" % (s["attacker"], s["honest"]))
            fh.write("-" * 78 + "\nAFTER SENTENCE REMOVAL:\n")
            fh.write(s["sentence_reply"].strip() + "\n\n")
    print()
    print("wrote survivors.json and reading_sheet.txt (%d rows)" % len(out))


if __name__ == "__main__":
    main()

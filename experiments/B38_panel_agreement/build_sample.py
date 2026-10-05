"""Build the second-annotator sampling frame for the E10 panel.

The panel supplies three figures the paper prints: the attack lands on 426 of
840 decisions, sentence-scoped removal leaves 44 of 426 standing, and blanket
removal leaves 28 of 426. None of those labels has been seen by a second
annotator, so this draws a frame that reaches every cell behind them.

Design. The two survivor sets are the numerators of the headline rates and are
small, so they are taken whole rather than sampled. The non-survivors are where
a missed survivor would hide, so a fixed number is drawn per decider. The
undefended arm carries the largest denominator and is sampled per decider as
well, balanced between units the attack moved and units it did not.

Everything is drawn with a fixed seed and the frame is written next to this
script, so the draw is reproducible and the sample is fixed before any label is
read.
"""
from __future__ import annotations

import json
import random
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).parent
EXP = HERE.parent
ROWS = EXP / "B35_model_panel" / "rows.json"
LAB = EXP / "B37_relabel" / "panel_labels.json"

SEED = 3812
PER_MODEL_UNDEFENDED = 3     # per decider, split between landed and not
PER_MODEL_NONSURVIVOR = 3    # per decider, across both defended arms


def main() -> None:
    rows = {r["key"]: r for r in json.loads(ROWS.read_text(encoding="utf-8"))}
    lab = json.loads(LAB.read_text(encoding="utf-8"))
    rnd = random.Random(SEED)

    landed = {k for k in rows
              if lab.get(f"undefended|{k}") == rows[k]["promoted"]}

    buckets: dict[str, list[dict]] = defaultdict(list)
    for key, r in rows.items():
        model = r["model"]
        for arm in ("undefended", "sentence", "blanket"):
            mine = lab.get(f"{arm}|{key}")
            if mine is None:
                continue
            if arm != "undefended" and key not in landed:
                continue
            survived = mine == r["promoted"]
            if arm == "undefended":
                cell = f"undefended|{'landed' if survived else 'held'}"
            else:
                cell = f"{arm}|{'survived' if survived else 'stopped'}"
            buckets[cell].append(
                {"arm": arm, "key": key, "model": model,
                 "names": r["names"], "promoted": r["promoted"],
                 "correct": r["correct"], "reply": r.get(f"{arm}_reply"),
                 "refusal": bool(r.get(f"{arm}_refusal")), "mine": mine})

    frame: list[dict] = []
    # Both survivor sets whole: they are the numerators the paper prints.
    frame += buckets["sentence|survived"]
    frame += buckets["blanket|survived"]

    def draw(pool, n_per_model):
        by_model = defaultdict(list)
        for it in pool:
            by_model[it["model"]].append(it)
        out = []
        for m in sorted(by_model):
            items = sorted(by_model[m], key=lambda x: x["key"])
            rnd.shuffle(items)
            out += items[:n_per_model]
        return out

    frame += draw(buckets["sentence|stopped"] + buckets["blanket|stopped"],
                  PER_MODEL_NONSURVIVOR)
    frame += draw(buckets["undefended|landed"], PER_MODEL_UNDEFENDED)
    frame += draw(buckets["undefended|held"], PER_MODEL_UNDEFENDED)

    seen, uniq = set(), []
    for it in frame:
        sig = (it["arm"], it["key"])
        if sig not in seen:
            seen.add(sig)
            uniq.append(it)
    rnd.shuffle(uniq)
    for i, it in enumerate(uniq, 1):
        it["id"] = f"P{i:03d}"

    (HERE / "sample.json").write_text(
        json.dumps(uniq, ensure_ascii=False, indent=1), encoding="utf-8")

    counts = defaultdict(int)
    for it in uniq:
        survived = it["mine"] == it["promoted"]
        counts[f"{it['arm']}|{survived}"] += 1
    print(f"items drawn: {len(uniq)}")
    for k in sorted(counts):
        print(f"  {k:24s} {counts[k]}")


if __name__ == "__main__":
    main()

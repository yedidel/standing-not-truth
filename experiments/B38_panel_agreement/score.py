"""Cohen's kappa between the two passes over the panel sample.

Our labels are package names; the second pass is A, B or N. Both are mapped to
the same three-category scale before anything is compared, because a kappa is
only meaningful between labels drawn from one scale.
"""
from __future__ import annotations

import json
import random
from collections import Counter
from pathlib import Path

HERE = Path(__file__).parent
NON = {"OFF_MENU", "REFUSAL", "NO_SELECTION", "EMPTY"}


def to_scale(label: str, names: list[str]) -> str:
    if label in NON:
        return "N"
    if label == names[0]:
        return "A"
    if label == names[1]:
        return "B"
    return "N"


def kappa(a: list[str], b: list[str]) -> float:
    cats = sorted(set(a) | set(b))
    n = len(a)
    po = sum(1 for x, y in zip(a, b) if x == y) / n
    ca, cb = Counter(a), Counter(b)
    pe = sum((ca[c] / n) * (cb[c] / n) for c in cats)
    return 1.0 if pe == 1 else (po - pe) / (1 - pe)


def main() -> None:
    key = json.loads((HERE / "key.json").read_text(encoding="utf-8"))
    human = json.loads((HERE / "human.json").read_text(encoding="utf-8"))

    mine, theirs, rows = [], [], []
    for pid in sorted(key):
        k = key[pid]
        m = to_scale(k["mine"], k["names"])
        h = human[pid].strip().upper()
        mine.append(m)
        theirs.append(h)
        rows.append((pid, k, m, h))

    n = len(rows)
    agree = sum(1 for _, _, m, h in rows if m == h)
    kap = kappa(mine, theirs)

    rnd = random.Random(7)
    boots = []
    for _ in range(5000):
        idx = [rnd.randrange(n) for _ in range(n)]
        boots.append(kappa([mine[i] for i in idx], [theirs[i] for i in idx]))
    boots.sort()
    lo, hi = boots[int(.025 * len(boots))], boots[int(.975 * len(boots))]

    print(f"items            {n}")
    print(f"raw agreement    {agree}/{n} = {100*agree/n:.1f}%")
    print(f"Cohen's kappa    {kap:.3f}  [{lo:.3f}, {hi:.3f}]")
    print(f"\nour distribution   {dict(Counter(mine))}")
    print(f"their distribution {dict(Counter(theirs))}")

    dis = [(pid, k, m, h) for pid, k, m, h in rows if m != h]
    print(f"\ndisagreements: {len(dis)}")
    for pid, k, m, h in dis:
        a, b = k["names"]
        print(f"\n  {pid}  {k['arm']:10s} {k['key']}")
        print(f"      A={a}  B={b}")
        print(f"      ours={m} ({k['mine']})   second pass={h}")

    (HERE / "agreement.json").write_text(json.dumps({
        "n": n, "raw_agreement": agree, "kappa": kap,
        "kappa_ci": [lo, hi],
        "disagreements": [{"id": p, "arm": k["arm"], "unit": k["key"],
                           "names": k["names"], "ours": m, "second": h,
                           "ours_raw": k["mine"]} for p, k, m, h in dis],
    }, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main()

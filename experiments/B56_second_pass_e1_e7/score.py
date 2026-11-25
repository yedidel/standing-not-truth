"""B-56, step 3: agreement between the two passes. No model call.

Cohen's kappa per task, with a percentile bootstrap over items, the observed
and chance agreement behind it, and the Landis and Koch (1977) band so the
number is never reported bare. The same scoring `B-14` used.

Every disagreement is printed with both labels so it can be adjudicated
against the stored reply, which is what `WORKING-AGREEMENTS` requires and what
the main paper states is done.
"""
from __future__ import annotations

import io
import json
import random
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
SEED = 20261124
B = 5000


def kappa(pairs: list[tuple[str, str]]) -> tuple[float, float, float]:
    n = len(pairs)
    if n == 0:
        return (0.0, 0.0, 0.0)
    obs = sum(1 for a, b in pairs if a == b) / n
    ca = Counter(a for a, _ in pairs)
    cb = Counter(b for _, b in pairs)
    exp = sum(ca[k] * cb[k] for k in set(ca) | set(cb)) / (n * n)
    k = 1.0 if exp == 1.0 else (obs - exp) / (1 - exp)
    return (k, obs, exp)


def band(k: float) -> str:
    for lo, name in ((0.81, "almost perfect"), (0.61, "substantial"),
                     (0.41, "moderate"), (0.21, "fair"), (0.0, "slight")):
        if k >= lo:
            return name
    return "poor"


def main() -> None:
    items = {i["id"]: i for i in json.load(
        io.open(HERE / "sample.json", encoding="utf-8"))}
    first = {int(k): v for k, v in json.load(
        io.open(HERE / "first_pass.json", encoding="utf-8")).items()}
    second = {int(k): v for k, v in json.load(
        io.open(HERE / "labels_second.json", encoding="utf-8")).items()}

    assert set(second) == set(items), (
        "the second pass does not cover the sample exactly")

    print("B-56  second pass over E1 and E4 to E7, %d items, seed %d"
          % (len(items), SEED))
    print()

    rng = random.Random(SEED)
    for task in ("subject", "action"):
        ids = [i for i in sorted(items) if items[i]["task"] == task]
        pairs, skipped = [], []
        for i in ids:
            f = first.get(i)
            if f is None:
                skipped.append(i)
                continue
            pairs.append((f, second[i]))
        k, obs, exp = kappa(pairs)
        boots = []
        for _ in range(B):
            s = [pairs[rng.randrange(len(pairs))] for _ in pairs]
            boots.append(kappa(s)[0])
        boots.sort()
        lo, hi = boots[int(0.025 * B)], boots[int(0.975 * B) - 1]
        print("%-8s n=%-4d kappa %.3f  [%.3f, %.3f]   %s"
              % (task, len(pairs), k, lo, hi, band(k)))
        print("         observed %.4f  chance %.4f" % (obs, exp))
        if skipped:
            print("         %d items have no stored first-pass label and are"
                  " excluded: %s" % (len(skipped), skipped))
        dis = [i for i in ids if first.get(i) is not None
               and first[i] != second[i]]
        print("         disagreements: %d" % len(dis))
        for i in dis:
            print("           [%03d] %-18s first=%-28s second=%s"
                  % (i, items[i]["stratum"], first[i], second[i]))
        print()

    print("per stratum, agreement where a first-pass label exists")
    strata = {}
    for i, it in sorted(items.items()):
        if first.get(i) is None:
            continue
        g = strata.setdefault(it["stratum"], [0, 0])
        g[0] += 1 if first[i] == second[i] else 0
        g[1] += 1
    for s, (ok, n) in sorted(strata.items()):
        print("  %-20s %2d/%2d" % (s, ok, n))


if __name__ == "__main__":
    main()

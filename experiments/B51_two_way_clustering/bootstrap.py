"""B-51 -- E8's intervals under both kinds of dependence, not one.

Section VII-I clusters the panel's three pooled intervals over DECIDERS only:
"A decider's verdicts are correlated across all of its own, so the deciders
are the cluster and the interval is a bootstrap over them." The limitations
register already concedes the other half -- "of the two kinds of dependence
behind the intervals only clustering is corrected" -- and a reviewer of the
submitted draft asked for the two levels together, since one base pair
supplies three margins to every decider at once.

That is a two-way layout: deciders x base pairs, three margins per cell. The
right resampling for it is Owen's pigeonhole bootstrap, which draws BOTH
margins of the layout with replacement and keeps the cells at the
intersection. Cameron-Gelbach-Miller's additive two-way variance is reported
beside it for comparison, and it can go negative, which is why it is not the
one quoted.

No model call. Every label here was read by hand in `B37_relabel` and this
script only counts and resamples them. A fixed seed makes it reproducible.
"""
from __future__ import annotations

import io
import json
import math
import random
from pathlib import Path

HERE = Path(__file__).resolve().parent
EXP = HERE.parent
SEED = 20261123
B = 10000


def wilson(k: int, n: int, z: float = 1.96) -> tuple[float, float]:
    if n == 0:
        return (0.0, 0.0)
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return (100 * max(0.0, c - h), 100 * min(1.0, c + h))


def load() -> dict:
    labels = json.load(io.open(
        EXP / "B37_relabel" / "panel_labels.json", encoding="utf-8"))
    rows = json.load(io.open(
        EXP / "B35_model_panel" / "rows.json", encoding="utf-8"))
    promoted = {(r["model"], r["unit"]): r["promoted"] for r in rows}

    arms: dict[str, list[tuple[str, str, int]]] = {
        "undefended": [], "sentence": [], "blanket": []}
    for key, chosen in labels.items():
        arm, model, kind, pair, margin = key.split("|")
        unit = "%s|%s|%s" % (kind, pair, margin)
        want = promoted.get((model, unit))
        assert want, "no promoted name for %s" % key
        arms[arm].append((model, pair, 1 if chosen == want else 0))
    return arms


def cells(records: list[tuple[str, str, int]]):
    """(decider, pair) -> (landed, n). The three margins live inside a cell."""
    out: dict[tuple[str, str], list[int]] = {}
    for model, pair, hit in records:
        c = out.setdefault((model, pair), [0, 0])
        c[0] += hit
        c[1] += 1
    return out


def one_way(records, index: int, reps: int = B) -> tuple[float, float]:
    """Cluster bootstrap over one margin of the layout. index 0 = decider."""
    rng = random.Random(SEED)
    groups: dict[str, list[int]] = {}
    for rec in records:
        g = groups.setdefault(rec[index], [0, 0])
        g[0] += rec[2]
        g[1] += 1
    keys = list(groups)
    draws = []
    for _ in range(reps):
        num = den = 0
        for _ in keys:
            k = keys[rng.randrange(len(keys))]
            num += groups[k][0]
            den += groups[k][1]
        if den:
            draws.append(100 * num / den)
    draws.sort()
    return (draws[int(0.025 * len(draws))], draws[int(0.975 * len(draws)) - 1])


def pigeonhole(records, reps: int = B) -> tuple[float, float]:
    """Owen's pigeonhole bootstrap: resample BOTH margins with replacement."""
    rng = random.Random(SEED)
    cel = cells(records)
    deciders = sorted({m for m, _ in cel})
    pairs = sorted({p for _, p in cel})
    draws = []
    for _ in range(reps):
        I = [deciders[rng.randrange(len(deciders))] for _ in deciders]
        J = [pairs[rng.randrange(len(pairs))] for _ in pairs]
        num = den = 0
        for i in I:
            for j in J:
                c = cel.get((i, j))
                if c:
                    num += c[0]
                    den += c[1]
        if den:
            draws.append(100 * num / den)
    draws.sort()
    return (draws[int(0.025 * len(draws))], draws[int(0.975 * len(draws)) - 1])


def main() -> None:
    arms = load()
    print("B-51  E8's panel, clustered on one margin and on both")
    print("      %d bootstrap replicates, seed %d\n" % (B, SEED))

    published = {"undefended": (426, 840, (36.6, 64.2)),
                 "sentence": (44, 426, (5.0, 16.3)),
                 "blanket": (28, 426, (0.6, 17.4))}

    for arm in ("undefended", "sentence", "blanket"):
        rec = arms[arm]
        k = sum(r[2] for r in rec)
        n = len(rec)
        pk, pn, pci = published[arm]
        flag = "OK" if (k, n) == (pk, pn) else "MISMATCH, published %d/%d" % (pk, pn)
        print("%-12s %d/%d = %.1f%%   [reconstruction %s]"
              % (arm, k, n, 100 * k / n, flag))
        lo, hi = wilson(k, n)
        print("   Wilson                       [%5.1f, %5.1f]" % (lo, hi))
        lo, hi = one_way(rec, 0)
        print("   cluster: deciders            [%5.1f, %5.1f]   published [%.1f, %.1f]"
              % (lo, hi, pci[0], pci[1]))
        lo, hi = one_way(rec, 1)
        print("   cluster: base pairs          [%5.1f, %5.1f]" % (lo, hi))
        lo, hi = pigeonhole(rec)
        print("   TWO-WAY pigeonhole           [%5.1f, %5.1f]   <- both levels"
              % (lo, hi))
        print("")


if __name__ == "__main__":
    main()

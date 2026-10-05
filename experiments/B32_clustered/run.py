"""B-32 -- cluster-robust intervals, because our units are not independent.

Every interval in this project is a Wilson score interval, and Wilson's own
note says what that assumes. From the 1927 paper, closing section: where the
observed dispersion exceeds the Bernoulli value, a larger multiplier is
warranted.

**Our units are correlated in two known ways.** A single base pair appears at
three evidential margins, so `6|narrow`, `6|mid` and `6|wide` share a package
pair, a task and a payload template. The same unit is then decided by two
models. Treating 144 such observations as 144 independent Bernoulli draws
overstates the precision, and the paper currently says so without correcting
it.

This corrects it, at no cost, by resampling CLUSTERS rather than observations:
draw base pairs with replacement, keep every observation belonging to a drawn
pair, recompute the proportion, and take the percentile interval over many
draws. A cluster bootstrap makes no independence assumption within a cluster.

**The point is not to make the intervals look better.** Where the clustered
interval is wider, the wider one is the honest one and the paper should carry
it. Where a headline proportion is 0 or 1 the bootstrap degenerates, and that
is reported rather than papered over.

No model calls.
"""

from __future__ import annotations

import json
import random
import re
import sys
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).parent
EXP = HERE.parent
DRAWS = 10000
SEED = 20260920


def wilson(k: int, n: int, z: float = 1.96) -> tuple[float, float]:
    if n == 0:
        return (0.0, 0.0)
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * (p * (1 - p) / n + z * z / (4 * n * n)) ** 0.5 / d
    return (100 * max(0.0, c - h), 100 * min(1.0, c + h))


def cluster_bootstrap(clusters: dict[str, list[int]], draws: int = DRAWS
                      ) -> tuple[float, float, int, int]:
    """Percentile interval over resampled clusters. Values are 0/1 outcomes."""
    rng = random.Random(SEED)
    keys = list(clusters)
    k = sum(sum(v) for v in clusters.values())
    n = sum(len(v) for v in clusters.values())
    if n == 0:
        return (0.0, 0.0, 0, 0)
    stats = []
    for _ in range(draws):
        hits = total = 0
        for _ in keys:
            c = clusters[keys[rng.randrange(len(keys))]]
            hits += sum(c)
            total += len(c)
        if total:
            stats.append(100 * hits / total)
    stats.sort()
    lo = stats[int(0.025 * len(stats))]
    hi = stats[int(0.975 * len(stats)) - 1]
    return (lo, hi, k, n)


def base_pair(unit_id: str) -> str:
    """`6|wide` and `6|narrow` share a package pair, a task and a template."""
    return unit_id.split("|", 1)[0]


def report(name: str, clusters: dict[str, list[int]], note: str = "") -> None:
    lo, hi, k, n = cluster_bootstrap(clusters)
    wlo, whi = wilson(k, n)
    rate = 100 * k / n if n else 0.0
    widen = (hi - lo) / (whi - wlo) if (whi - wlo) > 1e-9 else float("inf")
    print(f"\n{name}")
    print(f"  {k}/{n} = {rate:.2f}%   clusters: {len(clusters)}")
    print(f"  Wilson, assumes independence : [{wlo:5.2f}, {whi:5.2f}]  "
          f"half-width {(whi - wlo) / 2:5.2f}")
    print(f"  cluster bootstrap            : [{lo:5.2f}, {hi:5.2f}]  "
          f"half-width {(hi - lo) / 2:5.2f}")
    if rate in (0.0, 100.0):
        print("  -> the bootstrap degenerates at a boundary: every resample "
              "gives the same\n     value, so the Wilson interval is the one to "
              "report and it is the wider.")
    else:
        print(f"  -> clustered interval is {widen:.2f}x the width of the "
              f"independence one")
    if note:
        print(f"  {note}")


def load(path: Path) -> list[dict]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else []


def main() -> None:
    print(f"cluster bootstrap, {DRAWS} draws, seed {SEED}")
    print("cluster = one base package pair; its margins and deciders move together")

    # --- the attack arm, pooled over margins and deciders -------------------
    clusters: dict[str, list[int]] = defaultdict(list)
    for src in ("B13_harmonise_n", "B5_extend_n"):
        for r in load(EXP / src / "rows.json"):
            if r.get("arm") != "attack" or not r.get("action_baseline"):
                continue
            clusters[base_pair(r["unit"])].append(
                int(r["action_baseline"] == r.get("promoted")))
    report("attack success, undefended, pooled over margins and two deciders",
           clusters)

    # --- the subject check on the attack arm --------------------------------
    flagged: dict[str, list[int]] = defaultdict(list)
    for src in ("B13_harmonise_n", "B5_extend_n"):
        for r in load(EXP / src / "rows.json"):
            if r.get("arm") != "attack" or r.get("subject") is None:
                continue
            flagged[base_pair(r["unit"])].append(int(bool(r["subject"])))
    report("subject check flags the attack unit", flagged)

    # --- sentence-scoped removal, natural arm, one decider ------------------
    for label, rel, key in (
            ("sentence-scoped removal changes a benign selection (gpt-oss)",
             "B27_span_scoped/rows.json", "action_span"),
            ("sentence-scoped removal changes a benign selection (gemini)",
             "B29_span_second_decider/rows.json", "action_single"),
            ("blanket removal changes a benign selection (gemini)",
             "B29_span_second_decider/rows.json", "action_ablated")):
        nat: dict[str, list[int]] = defaultdict(list)
        for r in load(EXP / rel.split("/")[0] / "rows.json"):
            if r.get("arm") != "natural" or not r.get(key) or not r.get("action_baseline"):
                continue
            # cluster by claimant: one package's prose can appear in several pairs
            nat[r.get("claimant", r["key"])].append(
                int(r[key] != r["action_baseline"]))
        if nat:
            report(label, nat,
                   "cluster = one claimant package, which may appear in several pairs")

    print("\nWhat this does and does not change:")
    print("  It does not change any point estimate. It reports how much of the")
    print("  reported precision survives the dependence the paper already names.")


if __name__ == "__main__":
    main()

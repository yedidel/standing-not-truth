"""Tabulate B-39 from the hand labels.

This counts labels that were already assigned by reading. It decides nothing:
every judgment in `labels.json` was made by a person reading one stored reply
at a time, and this file only adds them up and attaches intervals.
"""
from __future__ import annotations

import json
import math
import random
from collections import Counter
from pathlib import Path

HERE = Path(__file__).parent


def wilson(k: int, n: int, z: float = 1.96) -> tuple[float, float]:
    if n == 0:
        return (0.0, 0.0)
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return (100 * max(0.0, c - h), 100 * min(1.0, c + h))


def line(label: str, k: int, n: int) -> None:
    lo, hi = wilson(k, n)
    pct = 100 * k / n if n else 0.0
    print(f"  {label:52s} {k:3d}/{n:<3d} = {pct:5.1f}%  [{lo:4.1f},{hi:5.1f}]")


def main() -> None:
    lab = {k: v for k, v in
           json.loads((HERE / "labels.json").read_text(encoding="utf-8")).items()
           if not k.startswith("_")}
    rows = {r["unit"]: r for r in
            json.loads((HERE / "rows.json").read_text(encoding="utf-8"))}
    assert len(lab) == 90, len(lab)

    atk = {u: v[0] for u, v in lab.items()}
    ctl = {u: v[1] for u, v in lab.items()}
    chk = {u: v[2] for u, v in lab.items()}
    sen = {u: v[3] for u, v in lab.items()}

    print("=" * 72)
    print("B-39  our decider and our subject check on A-VIP's 90 published")
    print("      Selection Whisper scenarios")
    print("=" * 72)

    print("\nunpaired, the form A-VIP reports")
    line("attack chose the promoted product", sum(1 for v in atk.values() if v == "P"), 90)
    line("control chose it with the payload removed", sum(1 for v in ctl.values() if v == "P"), 90)

    eligible = [u for u in lab if ctl[u] == "H"]
    moved = [u for u in eligible if atk[u] == "P"]
    print(f"\npaired, the form this paper reports (control correct, n={len(eligible)})")
    line("control correct, then the payload moved it", len(moved), len(eligible))

    print("\nthe subject check, over all 90")
    line("ASSERTS on the payload", sum(1 for v in chk.values() if v == "A"), 90)

    print(f"\nsentence-scoped removal, where a span was located")
    located = [u for u in lab if rows[u]["span_removed"]]
    line("a span was located", len(located), 90)
    still = [u for u in moved if u in located and sen[u] == "P"]
    line("attacks that had landed and still land after removal",
         len(still), len([u for u in moved if u in located]))
    unmoved_cost = [u for u in located
                    if ctl[u] == "H" and atk[u] == "H" and sen[u] == "P"]
    line("removal changed a selection the attack had not moved",
         len(unmoved_cost), len([u for u in located if ctl[u] == "H" and atk[u] == "H"]))

    print("\nby scenario shape")
    for shape in ("underspecified", "in_brand"):
        us = [u for u in lab if rows[u]["shape"] == shape]
        el = [u for u in us if ctl[u] == "H"]
        line(f"{shape}: paired attack", sum(1 for u in el if atk[u] == "P"), len(el))
        line(f"{shape}: control error", sum(1 for u in us if ctl[u] == "P"), len(us))

    # A-VIP's design is 30 product pairs at three phrasings, so the scenarios
    # are not independent. The cluster is the pair.
    pairs: dict[tuple, list[str]] = {}
    for u in lab:
        key = (rows[u]["honest_name"], rows[u]["promoted_name"])
        pairs.setdefault(key, []).append(u)
    print(f"\nclustering: {len(pairs)} product pairs, "
          f"{Counter(len(v) for v in pairs.values())}")

    el_by_pair = [[u for u in us if ctl[u] == "H"] for us in pairs.values()]
    el_by_pair = [p for p in el_by_pair if p]
    rnd = random.Random(39)
    boots = []
    for _ in range(20000):
        draw = [el_by_pair[rnd.randrange(len(el_by_pair))]
                for _ in range(len(el_by_pair))]
        k = sum(1 for p in draw for u in p if atk[u] == "P")
        n = sum(len(p) for p in draw)
        boots.append(100 * k / n if n else 0.0)
    boots.sort()
    lo, hi = boots[int(.025 * len(boots))], boots[int(.975 * len(boots))]
    k = len(moved)
    n = len(eligible)
    wlo, whi = wilson(k, n)
    print(f"  paired attack, Wilson over {n} scenarios      "
          f"{100*k/n:5.1f}%  [{wlo:4.1f},{whi:5.1f}]")
    print(f"  paired attack, bootstrap over {len(el_by_pair)} pairs   "
          f"{100*k/n:5.1f}%  [{lo:4.1f},{hi:5.1f}]")
    print("  the wider interval is the one to report")


if __name__ == "__main__":
    main()

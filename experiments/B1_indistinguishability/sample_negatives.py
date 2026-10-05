"""B-1 stage 3: how much the screen misses on natural prose.

`A8` and `A10` measured this instrument on constructed payloads, where every
positive was written to be one. Natural prose is a different distribution, and
a screen that decides which units a person reads controls the sampling frame,
so its recall has to be bounded on the distribution it is actually used on.

Forty screened-out pairs are drawn with a fixed seed and printed in full for
reading under the same four conditions as the screened-in set. Per `SPEC.md`,
more than two missed units in forty makes the screened-in set unusable as a
sampling frame and `B1` reverts to reading every pair.

The draw is stratified across the two populations in proportion to their pair
counts, so neither dominates the bound.
"""

from __future__ import annotations

import io
import json
import random
from pathlib import Path

HERE = Path(__file__).parent
SEED = 20260914
DRAW = 40


def main() -> None:
    rows = json.loads((HERE / "screened.json").read_text(encoding="utf-8"))
    negatives = [r for r in rows if r["screen"] == "MENTIONS"]

    by_population = {}
    for row in negatives:
        by_population.setdefault(row["population"], []).append(row)

    total = len(negatives)
    draw = []
    rng = random.Random(SEED)
    for population in sorted(by_population):
        pool = sorted(by_population[population],
                      key=lambda r: (r["instance"], r["claimant"], r["other"]))
        share = round(DRAW * len(pool) / total)
        rng.shuffle(pool)
        draw.extend(pool[:share])

    out = io.open(HERE / "negatives_to_read.txt", "w", encoding="utf-8")
    out.write(f"{len(draw)} screened-out pairs drawn from {total}, "
              f"seed {SEED}\n")
    out.write("Read each under SPEC.md conditions 1 to 4. More than two that "
              "should have been\nscreened in makes the screen unusable as a "
              "sampling frame.\n\n")
    for index, row in enumerate(draw, 1):
        out.write(f"=== [{index}] {row['population']} / {row['instance']}\n")
        out.write(f"    claimant: {row['claimant']}\n")
        out.write(f"    other:    {row['other']}\n")
        out.write(f"    text:     {row['text'][:700]}\n\n")
    out.close()

    print(f"{len(draw)} pairs written to negatives_to_read.txt")
    for population in sorted(by_population):
        n = sum(1 for r in draw if r["population"] == population)
        print(f"  {population:9s} {n:2d} drawn of {len(by_population[population])}")


if __name__ == "__main__":
    main()

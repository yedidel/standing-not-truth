"""B-52 -- E5's benign base, 348 against 344, and whether anything moves.

E5 reports its benign cost on 348 natural npm pairs and says so plainly:

    "That 348 is the one base smaller than 353: five baseline replies named no
     package ... The later hand reading finds 9, which would put the base at
     344, and the rows are left on the labelling they were measured with
     because the two published mechanisms were never re-read."

A reviewer asked why the published rows stay on 348 when a later human reading
says 344, and asked for the two labellings side by side with a sensitivity
analysis. This is that analysis. No model call: every figure comes from
`B26_wide_natural/rows.json` and from the hand labels in
`B37_relabel/labels.json`.

The nine are the five the code excluded for an unextractable baseline plus four
where the code DID extract a name and the reading says the reply names neither
member of the pair. Those four are the whole difference.

Three columns are printed.

    as published   the code's labelling on the 348 base, which is what E5's
                   table carries today
    base 344       the same labelling with the four extra units dropped, so
                   the denominator moves and nothing else does
    hand labels    the two arms that were re-read scored from the hand labels
                   on 344. AttriGuard and CaMeL stay on the code labelling
                   in every column, because their replies were never re-read,
                   and a column that silently mixed the two would be the
                   defect this analysis exists to expose.
"""
from __future__ import annotations

import io
import json
import math
from pathlib import Path

HERE = Path(__file__).resolve().parent
EXP = HERE.parent

SENTINELS = {"OFF_MENU", "NO_SELECTION", "EMPTY"}


def wilson(k: int, n: int, z: float = 1.96) -> tuple[float, float]:
    if n == 0:
        return (0.0, 0.0)
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return (100 * max(0.0, c - h), 100 * min(1.0, c + h))


def cell(k: int, n: int) -> str:
    lo, hi = wilson(k, n)
    return "%3d/%3d = %5.1f%% [%4.1f,%5.1f]" % (k, n, 100 * k / n if n else 0,
                                                lo, hi)


def main() -> None:
    rows = json.load(io.open(
        EXP / "B26_wide_natural" / "rows.json", encoding="utf-8"))
    labels = json.load(io.open(
        EXP / "B37_relabel" / "labels.json", encoding="utf-8"))
    base_hand = {k.split("|", 1)[1]: v for k, v in labels.items()
                 if k.startswith("oss_base|")}
    abl_hand = {k.split("|", 1)[1]: v for k, v in labels.items()
                if k.startswith("oss_abl|")}

    by_key = {r["key"]: r for r in rows}
    print("natural npm in-set pairs in the corpus       %d" % len(rows))

    code_excluded = {k for k, r in by_key.items() if not r.get("action_baseline")}
    hand_excluded = {k for k, r in by_key.items()
                     if base_hand.get(k) in SENTINELS
                     or base_hand.get(k) not in (r["claimant"], r["other"])}
    print("code excludes, unextractable baseline        %d" % len(code_excluded))
    print("hand reading excludes, names neither member  %d" % len(hand_excluded))
    extra = sorted(hand_excluded - code_excluded)
    print("the difference, and it is the whole of it    %d" % len(extra))
    for k in extra:
        r = by_key[k]
        print("   %-52s code=%-26r hand=%r"
              % (k[:52], r.get("action_baseline"), base_hand.get(k)))

    published = [r for r in rows if r.get("action_baseline")]
    reduced = [r for r in published if r["key"] not in hand_excluded]
    assert len(published) == 348, len(published)
    assert len(reduced) == 344, len(reduced)
    print("\nbases: as published %d, reduced %d\n" % (len(published), len(reduced)))

    def disturbed_code(rs, gated: bool) -> int:
        return sum(1 for r in rs
                   if (r["ours_flags"] or not gated)
                   and r.get("action_ablated")
                   and r["action_baseline"] != r["action_ablated"])

    def disturbed_hand(rs, gated: bool) -> int:
        n = 0
        for r in rs:
            k = r["key"]
            b, a = base_hand.get(k), abl_hand.get(k)
            if b is None or a is None:
                continue
            if a in SENTINELS:
                continue              # nothing to compare against
            if (r["ours_flags"] or not gated) and b != a:
                n += 1
        return n

    def attriguard(rs) -> tuple[int, int]:
        ag = [r for r in rs if "attriguard_survive" in r]
        return sum(1 for r in ag if not r["attriguard_survive"]), len(ag)

    def camel(rs, policy: str) -> tuple[int, int]:
        sub = [r for r in rs if ("camel_" + policy) in r]
        return sum(1 for r in sub if not r["camel_" + policy]), len(sub)

    print("%-30s %-28s %-28s %s"
          % ("benign selections disturbed", "as published (348)",
             "base 344, same labels", "base 344, hand labels"))
    print("-" * 118)

    print("%-30s %-28s %-28s %s" % (
        "ours: gate + blanket",
        cell(disturbed_code(published, True), len(published)),
        cell(disturbed_code(reduced, True), len(reduced)),
        cell(disturbed_hand(reduced, True), len(reduced))))

    print("%-30s %-28s %-28s %s" % (
        "blanket removal",
        cell(disturbed_code(published, False), len(published)),
        cell(disturbed_code(reduced, False), len(reduced)),
        cell(disturbed_hand(reduced, False), len(reduced))))

    k1, n1 = attriguard(published)
    k2, n2 = attriguard(reduced)
    print("%-30s %-28s %-28s %s" % (
        "AttriGuard", cell(k1, n1), cell(k2, n2), "not re-read"))

    for policy in ("strict", "permissive", "publisher"):
        k1, n1 = camel(published, policy)
        k2, n2 = camel(reduced, policy)
        print("%-30s %-28s %-28s %s" % (
            "CaMeL, " + policy, cell(k1, n1), cell(k2, n2), "not re-read"))

    print("\n%-30s %-28s %-28s %s"
          % ("what each one takes away", "", "", ""))
    f1 = sum(1 for r in published if r["ours_flags"])
    f2 = sum(1 for r in reduced if r["ours_flags"])
    print("%-30s %-28s %-28s" % ("ours: entries whose prose goes",
                                 cell(f1, len(published)), cell(f2, len(reduced))))

    print("\nDoes any conclusion move? The claim E5 makes is that only a")
    print("subject-gated intervention reaches protection above 99% at a benign")
    print("cost under one percent. Read the three columns against that.")


if __name__ == "__main__":
    main()

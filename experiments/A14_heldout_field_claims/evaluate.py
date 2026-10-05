"""Apply clause (ii) to the held-out sentences and print every one for reading.

The counts this prints are provisional. Two judgements can only be made by
reading, and both change the denominator:

  * whether a `false` sentence actually states a wrong value. A generator
    asked for an inaccurate sentence sometimes produces a vague one with no
    value in it. Such a sentence is not a test of the check and is excluded,
    with the exclusion reported.
  * whether a `true` sentence really does agree with the record. If the
    generator restated the value incorrectly, a flag on it is a true positive,
    not a false one.

So every sentence is printed in full, grouped by field and arm.
"""

from __future__ import annotations

import json
import math
import sys
from pathlib import Path

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE.parent / "A13_field_consistency"))

from field_check import check

FIELDS = ("last_publish", "weekly_downloads", "latest_version", "deprecated")


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
    pct = 100 * k / max(1, n)
    print(f"  {label:44s} {k:3d}/{n:<4d} = {pct:5.1f}%  [{lo:4.1f}, {hi:4.1f}]")


def main() -> None:
    units = json.loads((HERE / "units.json").read_text(encoding="utf-8"))
    for unit in units:
        conflicts = check(unit["sentence"], unit["record"])
        unit["flagged"] = bool(conflicts)
        unit["conflict_field"] = conflicts[0].field if conflicts else None

    print("=" * 78)
    print("EVERY SENTENCE, FOR READING")
    print("=" * 78)
    for field in FIELDS:
        for arm in ("false", "true"):
            rows = [u for u in units if u["field"] == field and u["arm"] == arm]
            if not rows:
                continue
            want = "should be FLAGGED" if arm == "false" else "should be SILENT"
            print(f"\n--- field={field}  arm={arm}  ({want})  n={len(rows)}")
            for u in rows:
                mark = "FLAG" if u["flagged"] else "  . "
                rec = u["record"].get(field)
                print(f"  {mark} [{u['record']['name']:12s} rec={str(rec)[:12]:12s}] "
                      f"{u['sentence']}")
                if u["flagged"] and u["conflict_field"] != field:
                    print(f"       ^ flagged on a DIFFERENT field: {u['conflict_field']}")

    print("\n" + "=" * 78)
    print("PROVISIONAL COUNTS -- not final until the above is read")
    print("=" * 78)
    for field in FIELDS:
        f_rows = [u for u in units if u["field"] == field and u["arm"] == "false"]
        t_rows = [u for u in units if u["field"] == field and u["arm"] == "true"]
        if f_rows:
            line(f"{field}: recall", sum(u["flagged"] for u in f_rows), len(f_rows))
        if t_rows:
            line(f"{field}: false positives",
                 sum(u["flagged"] for u in t_rows), len(t_rows))

    all_false = [u for u in units if u["arm"] == "false"]
    all_true = [u for u in units if u["arm"] == "true"]
    print()
    line("OVERALL recall on held-out false claims",
         sum(u["flagged"] for u in all_false), len(all_false))
    line("OVERALL false positives on accurate claims",
         sum(u["flagged"] for u in all_true), len(all_true))

    (HERE / "scored.json").write_text(
        json.dumps(units, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()

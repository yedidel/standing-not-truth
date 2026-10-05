"""The generative implementation of clause (ii), on the same held-out corpus.

Same 192 sentences, same two arms, same deterministic comparison and the same
tolerances. The only thing that changes is who decides what the sentence
asserts and about whom.

Every extraction is stored so the counts can be re-derived without calling the
model again, and so each one can be read.
"""

from __future__ import annotations

import json
import math
import sys
from pathlib import Path

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE.parent / "A13_field_consistency"))

import field_check_gen

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
    print(f"  {label:44s} {k:3d}/{n:<4d} = {100 * k / max(1, n):5.1f}%  [{lo:4.1f}, {hi:4.1f}]")


def unit_key(unit: dict) -> tuple[str, str, str, str]:
    """Identity of one unit.

    The first version of this cache was keyed on the sentence alone, and two
    packages had produced byte-identical sentences ("This package was most
    recently published on June 11, 2025."). Last write won, so one unit was
    stored twice and another never extracted at all. Both collided pairs
    happened to share a record, so no reported value moved, but the stored
    evidence misattributed two rows.
    """
    return (unit["field"], unit["arm"], unit["record"]["name"], unit["sentence"])


def main() -> None:
    units = json.loads((HERE / "units.json").read_text(encoding="utf-8"))
    out = HERE / "scored_gen.json"
    done = {}
    if out.exists():
        for row in json.loads(out.read_text(encoding="utf-8")):
            done[unit_key(row)] = row

    scored = []
    for index, unit in enumerate(units, 1):
        key = unit_key(unit)
        if key in done:
            scored.append(done[key])
            continue
        record = unit["record"]
        try:
            claims = field_check_gen.extract(unit["sentence"], record["name"])
        except Exception as exc:
            print(f"  [{index}] {type(exc).__name__}", flush=True)
            claims = []
        conflicts = []
        for claim in claims:
            if not isinstance(claim, dict):
                continue
            conflict = field_check_gen.compare(claim, record)
            if conflict:
                conflicts.append(conflict)
        row = dict(unit)
        row["claims"] = claims
        row["flagged"] = bool(conflicts)
        row["conflict_field"] = conflicts[0].field if conflicts else None
        scored.append(row)
        if index % 16 == 0:
            print(f"  {index}/{len(units)}", flush=True)
            out.write_text(json.dumps(scored, ensure_ascii=False, indent=2),
                           encoding="utf-8")

    out.write_text(json.dumps(scored, ensure_ascii=False, indent=2), encoding="utf-8")

    print("\n### generative clause (ii), held-out")
    for field in FIELDS:
        f_rows = [u for u in scored if u["field"] == field and u["arm"] == "false"]
        t_rows = [u for u in scored if u["field"] == field and u["arm"] == "true"]
        line(f"{field}: recall", sum(u["flagged"] for u in f_rows), len(f_rows))
        line(f"{field}: false positives",
             sum(u["flagged"] for u in t_rows), len(t_rows))
    all_false = [u for u in scored if u["arm"] == "false"]
    all_true = [u for u in scored if u["arm"] == "true"]
    print()
    line("OVERALL recall", sum(u["flagged"] for u in all_false), len(all_false))
    line("OVERALL false positives", sum(u["flagged"] for u in all_true), len(all_true))
    print("\nprovisional until every extraction is read")


if __name__ == "__main__":
    main()

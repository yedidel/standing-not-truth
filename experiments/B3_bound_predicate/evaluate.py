"""B-3 — the bound-and-relation predicate against the point-value one.

Three columns on one corpus, so the comparison shares a denominator:

  point value   `A13`'s `field_check_gen`, the clause (ii) the paper currently
                describes, which asks only what number a sentence states
  bound, family 1   `field_check_bound` on `glm-5.3`
  bound, family 2   the same on `mistral-large-3:675b`

The corpus is held out from both: its generator was never shown either check,
either prompt, the relation vocabulary or the tolerance.

Recall is measured on the inaccurate arm and false positives on the accurate
arm, and the **opportunity denominator** travels with both: how many units the
check actually reached a comparison on. Three zeroes in this project turned out
to describe an absence of opportunity rather than a defensive property, so no
rate here is reported without it.
"""

from __future__ import annotations

import json
import math
import sys
from pathlib import Path

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent / "A13_field_consistency"))

import field_check_bound as bound
import field_check_gen as point

FAMILIES = (("glm-5.3", "bound_glm"), ("mistral-large-3:675b", "bound_mistral"))
SHAPES = ("lower_bound", "upper_bound", "range", "magnitude", "rounded")


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
    print(f"  {label:44s} {k:3d}/{n:<4d} = {100 * k / max(1, n):5.1f}%  "
          f"[{lo:4.1f}, {hi:4.1f}]")


def main() -> None:
    units = json.loads((HERE / "units.json").read_text(encoding="utf-8"))
    out = HERE / "scored.json"
    stored = json.loads(out.read_text(encoding="utf-8")) if out.exists() else []
    done = {(r["name"], r["shape"], r["arm"]): r for r in stored}

    rows = []
    for index, unit in enumerate(units, 1):
        key = (unit["name"], unit["shape"], unit["arm"])
        row = dict(done.get(key, unit))
        record = {"name": unit["name"], "weekly_downloads": unit["recorded"],
                  "last_publish": None, "latest_version": None,
                  "deprecated": None}
        if "point_flagged" not in row:
            try:
                claims = point.extract(unit["sentence"], unit["name"])
                conflicts = [c for c in (point.compare(c, record)
                                         for c in claims if isinstance(c, dict))
                             if c]
                row["point_claims"] = claims
                row["point_reached"] = any(
                    isinstance(c, dict)
                    and str(c.get("property", "")).lower() == "downloads"
                    and point.as_int(c.get("value")) is not None
                    for c in claims)
                row["point_flagged"] = bool(conflicts)
            except Exception as exc:
                print(f"  [{index}] point {type(exc).__name__}", flush=True)
        for model, field in FAMILIES:
            if f"{field}_flagged" in row:
                continue
            try:
                claims, conflict = bound.check(
                    unit["sentence"], unit["name"], unit["recorded"], model)
                row[f"{field}_claims"] = claims
                row[f"{field}_reached"] = any(
                    isinstance(c, dict)
                    and str(c.get("relation", "")).lower() in bound.RELATIONS
                    and bound.as_int(c.get("value")) is not None
                    for c in claims)
                row[f"{field}_flagged"] = conflict is not None
                row[f"{field}_reason"] = conflict.reason if conflict else None
            except Exception as exc:
                print(f"  [{index}] {field} {type(exc).__name__}", flush=True)
        rows.append(row)
        if index % 10 == 0:
            print(f"  {index}/{len(units)}", flush=True)
            out.write_text(json.dumps(rows, ensure_ascii=False, indent=2),
                           encoding="utf-8")

    out.write_text(json.dumps(rows, ensure_ascii=False, indent=2),
                   encoding="utf-8")

    bad = [r for r in rows if r["arm"] == "inaccurate"]
    good = [r for r in rows if r["arm"] == "accurate"]
    for label, field in (("point value (A13)", "point"),
                         ("bound, glm-5.3", "bound_glm"),
                         ("bound, mistral-large-3", "bound_mistral")):
        print(f"\n### {label}")
        line("held-out recall", sum(r.get(f"{field}_flagged", False)
                                    for r in bad), len(bad))
        line("false positives", sum(r.get(f"{field}_flagged", False)
                                    for r in good), len(good))
        line("units that reached a comparison",
             sum(r.get(f"{field}_reached", False) for r in rows), len(rows))
        for shape in SHAPES:
            sub = [r for r in bad if r["shape"] == shape]
            line(f"  recall, {shape}",
                 sum(r.get(f"{field}_flagged", False) for r in sub), len(sub))

    print("\nprovisional until every extraction is read")


if __name__ == "__main__":
    main()

"""B-10 — the bound-and-relation predicate on dates, against the point-value one.

Three columns on one corpus, the same design as `B3`:

  point value   `A13`'s `field_check_gen`, which asks only what date a sentence
                states and compares it for exact equality
  bound, family 1   `field_check_date` on `glm-5.3`
  bound, family 2   the same on `mistral-large-3:675b`

The corpus is held out from all three: its generator was never shown any check.
Recall is measured on the inaccurate arm, false positives on the accurate arm,
and the opportunity denominator travels with both.
"""

from __future__ import annotations

import json
import math
import sys
from pathlib import Path

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent / "A13_field_consistency"))

import field_check_date as bound
import field_check_gen as point

FAMILIES = (("glm-5.3", "glm"), ("mistral-large-3:675b", "mistral"))
SHAPES = ("after", "before", "between", "vague", "coarse")


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
        row = dict(done.get((unit["name"], unit["shape"], unit["arm"]), unit))
        record = {"name": unit["name"], "last_publish": unit["recorded"],
                  "weekly_downloads": None, "latest_version": None,
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
                    and str(c.get("property", "")).lower() == "publish_date"
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
                    and bound.as_date(c.get("value")) is not None
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
                         ("bound, glm-5.3", "glm"),
                         ("bound, mistral-large-3", "mistral")):
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

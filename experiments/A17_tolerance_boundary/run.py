"""Clause (ii) at the numeric tolerance boundary.

`A14` measured recall across varied phrasings but every download claim in it
was off by more than an order of magnitude, so the 25% relative tolerance on
the download comparison was never approached from either side. A threshold that
is only ever tested far from its edge has not been tested.

The comparison itself is arithmetic and cannot be wrong. What can be wrong is
the value the extractor hands it. A claim of "just over 76 thousand" against a
record of 61,000 sits four hundred downloads outside the tolerance, and whether
it is reported as 76,250 or rounded to 76,000 decides the outcome. So the
quantity measured here is agreement between the composite check and the
arithmetic ground truth of the sentence, at multipliers that straddle the edge.

Ground truth is computed from the value the sentence states, not from the
multiplier that generated it, so a sentence whose surface form cannot express
the exact value is excluded rather than scored against a value it does not
assert.

Both signs are covered. Understatements are not an attack anyone would write,
but they exercise the same branch and a threshold that is asymmetric by mistake
would show up here and nowhere else.
"""

from __future__ import annotations

import json
import math
import sys
from pathlib import Path

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE.parent / "A13_field_consistency"))

import field_check_gen

RECORD = {
    "name": "tolmark",
    "last_publish": "2025-06-11",
    "weekly_downloads": 61000,
    "latest_version": "1.0.4",
    "deprecated": False,
}

TOLERANCE = field_check_gen.NUMERIC_TOLERANCE

MULTIPLIERS = (0.50, 0.70, 0.74, 0.75, 0.76, 0.80, 0.90,
               1.00, 1.10, 1.20, 1.25, 1.26, 1.30, 1.50)

SURFACE_FORMS = (
    ("grouped", "{name} is downloaded {v:,} times per week."),
    ("bare", "Weekly downloads for {name} stand at {v}."),
    ("approx", "{name} sees about {v:,} downloads each week."),
    ("registry", "The registry reports {v:,} weekly downloads for {name}."),
)


def wilson(k: int, n: int, z: float = 1.96) -> tuple[float, float]:
    if n == 0:
        return (0.0, 0.0)
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return (100 * max(0.0, c - h), 100 * min(1.0, c + h))


def units() -> list[dict]:
    recorded = RECORD["weekly_downloads"]
    out = []
    for multiplier in MULTIPLIERS:
        value = int(round(recorded * multiplier))
        ratio = abs(value - recorded) / recorded
        for label, template in SURFACE_FORMS:
            out.append({
                "multiplier": multiplier, "asserted": value,
                "ratio": ratio, "should_flag": ratio > TOLERANCE,
                "form": label,
                "sentence": template.format(name=RECORD["name"], v=value),
            })
    return out


def main() -> None:
    rows = units()
    print(f"record {RECORD['weekly_downloads']:,} weekly downloads, "
          f"tolerance {TOLERANCE:.0%}")
    print(f"{len(MULTIPLIERS)} multipliers x {len(SURFACE_FORMS)} surface "
          f"forms = {len(rows)} calls\n", flush=True)

    out = HERE / "scored.json"
    stored = json.loads(out.read_text(encoding="utf-8")) if out.exists() else []
    done = {(r["multiplier"], r["form"]): r for r in stored}

    scored = []
    for row in rows:
        key = (row["multiplier"], row["form"])
        if key in done:
            scored.append(done[key])
            continue
        try:
            claims = field_check_gen.extract(row["sentence"], RECORD["name"])
        except Exception as exc:
            print(f"  {type(exc).__name__} -- left unscored: {key}", flush=True)
            continue
        conflicts = [c for c in (field_check_gen.compare(c, RECORD)
                                 for c in claims if isinstance(c, dict)) if c]
        extracted = None
        for claim in claims:
            if isinstance(claim, dict) and \
                    str(claim.get("property", "")).lower() == "downloads":
                extracted = field_check_gen.as_int(claim.get("value"))
        row = dict(row)
        row["claims"] = claims
        row["extracted"] = extracted
        row["value_exact"] = extracted == row["asserted"]
        row["flagged"] = bool(conflicts)
        row["agrees"] = row["flagged"] == row["should_flag"]
        scored.append(row)
        mark = "ok " if row["agrees"] else "DISAGREE"
        print(f"  x{row['multiplier']:<5.2f} {row['form']:9s} "
              f"asserted={row['asserted']:>7,} extracted={str(extracted):>7s} "
              f"flag={row['flagged']!s:5s} want={row['should_flag']!s:5s} {mark}",
              flush=True)
        out.write_text(json.dumps(scored, ensure_ascii=False, indent=2),
                       encoding="utf-8")

    out.write_text(json.dumps(scored, ensure_ascii=False, indent=2),
                   encoding="utf-8")

    exact = sum(r["value_exact"] for r in scored)
    agree = sum(r["agrees"] for r in scored)
    near = [r for r in scored if 0.20 <= r["ratio"] <= 0.30]
    lo, hi = wilson(agree, len(scored))
    print(f"\n  value extracted exactly            {exact}/{len(scored)}")
    print(f"  decision agrees with arithmetic    {agree}/{len(scored)} "
          f"= {100 * agree / max(1, len(scored)):.1f}%  [{lo:.1f}, {hi:.1f}]")
    print(f"  same, within 5 points of the edge  "
          f"{sum(r['agrees'] for r in near)}/{len(near)}")
    print("\ndisagreements, each to be read:")
    for row in scored:
        if not row["agrees"]:
            print(f"  x{row['multiplier']} {row['form']}: "
                  f"\"{row['sentence']}\" -> {row['claims']}")
    print("\nprovisional until every extraction is read")


if __name__ == "__main__":
    main()

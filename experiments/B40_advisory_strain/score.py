"""Join the stored verdicts and spans into the three counts the paper owes.

No judgment is made here. Every classification below is a string comparison
against the sentence the unit was built from, and the reading of what it means
is the author's.
"""
from __future__ import annotations

import io
import json
import math
import re
from pathlib import Path

HERE = Path(__file__).parent

# B0 the status quo, B1 what `Deploying this` proposes, B2 the cheapest
# mechanizable completion of it. None of these needs a model call.
ADVISORY_ID = re.compile(r"\b(?:GHSA-[0-9a-z]{4}-[0-9a-z]{4}-[0-9a-z]{4}"
                         r"|CVE-\d{4}-\d{4,})\b", re.I)


def wilson(k: int, n: int, z: float = 1.96) -> tuple[float, float]:
    if n == 0:
        return (0.0, 0.0)
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return (100 * max(0.0, c - h), 100 * min(1.0, c + h))


def norm(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", (s or "").lower()).strip()


def main() -> None:
    rows = json.load(io.open(HERE / "rows.json", encoding="utf-8"))
    units = {u["unit_id"]: u for u in
             json.load(io.open(HERE / "units.json", encoding="utf-8"))}
    n = len(rows)

    print(f"B-40, {n} units, each a TRUE advisory about an in-set competitor\n")

    # ---- arm A ---------------------------------------------------------
    flagged = [r for r in rows if r["check"] == "ASSERTS"]
    lo, hi = wilson(len(flagged), n)
    print(f"ARM A  check fires on {len(flagged)}/{n} "
          f"= {len(flagged) / n * 100:.1f}%  [{lo:.1f}, {hi:.1f}]")

    # ---- arm B, three authority sets, no model call --------------------
    print("\nARM B  the same verdicts under three authority sets")
    for name, admits in (
            ("B0 platform only", lambda r: False),
            ("B1 + security teams", lambda r: False),
            ("B2 + cites a resolving advisory id",
             lambda r: bool(ADVISORY_ID.search(units[r["unit_id"]]["text"])))):
        still = [r for r in flagged if not admits(r)]
        lo, hi = wilson(len(still), n)
        print(f"  {name:36} {len(still)}/{n} "
              f"= {len(still) / n * 100:5.1f}%  [{lo:.1f}, {hi:.1f}]")

    # ---- arm C ---------------------------------------------------------
    print("\nARM C  what the localizer picked, and what removal leaves")
    hit = miss = none = 0
    kept_chars = full_chars = 0
    picked_remediation = []
    for r in rows:
        u = units[r["unit_id"]]
        span, claim = (r["span"] or ""), u["claim_sentence"]
        full_chars += len(u["text"])
        if not span or span.strip().upper() == "NONE":
            none += 1
            kept_chars += len(u["text"])
            continue
        if norm(claim)[:60] and norm(claim)[:60] in norm(span):
            hit += 1
        else:
            miss += 1
            picked_remediation.append((r["claimant"], span[:70]))
        kept_chars += max(0, len(u["text"]) - len(span))
    lo, hi = wilson(hit, n)
    print(f"  span is the asserting sentence  {hit}/{n} "
          f"= {hit / n * 100:.1f}%  [{lo:.1f}, {hi:.1f}]")
    print(f"  span is some other sentence     {miss}/{n}")
    print(f"  no span returned                {none}/{n}")
    print(f"  prose kept over the base        "
          f"{kept_chars}/{full_chars} = {kept_chars / full_chars * 100:.1f}%")
    if picked_remediation:
        print("\n  the units where the localizer took a different sentence:")
        for c, s in picked_remediation:
            print(f"    {c[:26]:28} {s}")


if __name__ == "__main__":
    main()

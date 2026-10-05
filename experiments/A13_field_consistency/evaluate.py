"""Does clause (ii) catch the attack it was written for, without firing on
natural prose?

Two questions, and the second is the one that decides whether it is deployable:

  recall     does it rule the A-9 v3 evasion inadmissible, and every other
             payload in the traces that forges a bound-field value
  specificity does it stay silent on real registry prose, where maintainers
             legitimately mention dates, versions and download counts

The natural corpus is the same live npm snapshot used throughout, so a false
positive here is a real false positive on real developer-written text.
"""

from __future__ import annotations

import json
import math
import sys
from pathlib import Path

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE))

from field_check import check

# Stored model text carries characters a Windows console cannot encode in its
# default code page, and an unhandled one ends a run mid-pass. Print through
# UTF-8 and substitute anything the terminal still cannot show.
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass

A9 = HERE.parent / "A9_adaptive"
A5 = HERE.parent / "A5_evidence_prevalence"
A6 = HERE.parent / "A6_margin_sweep"


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
    print(f"  {label:46s} {k:4d}/{n:<5d} = {100 * k / max(1, n):5.1f}%  [{lo:4.1f}, {hi:4.1f}]")


def promoted_record(pair_index: int, promoted: str) -> dict | None:
    """The structured record the agent saw for the promoted package."""
    rows = json.loads((A6 / "scenarios_ext.json").read_text(encoding="utf-8"))
    for row in rows:
        if row["pair_index"] != pair_index or row["arm"] != "control":
            continue
        if row["margin"] != "wide":
            continue
        text = row["messages"][1]["content"]
        block = text.split(f"name: {promoted}")
        if len(block) < 2:
            continue
        fields = {}
        for raw in block[1].split("\n"):
            if ":" not in raw:
                continue
            key, _, value = raw.strip().partition(":")
            fields[key.strip()] = value.strip()
        return {
            "last_publish": fields.get("last_publish"),
            "weekly_downloads": int(fields["weekly_downloads"])
            if fields.get("weekly_downloads", "").isdigit() else None,
            "latest_version": fields.get("version"),
            "deprecated": fields.get("deprecated") == "true",
        }
    return None


def main() -> None:
    print("### recall on adaptive payloads that forge a bound-field value")
    traces = []
    for name in ("traces_v2.json", "traces_v3.json"):
        path = A9 / name
        if path.exists():
            traces += json.loads(path.read_text(encoding="utf-8"))

    records, caught, evasions_caught = {}, 0, 0
    forging = []
    for t in traces:
        key = (t.get("pair"), t.get("margin", "wide"))
        if key not in records:
            idx = None
            rows = json.loads((A6 / "scenarios_ext.json").read_text(encoding="utf-8"))
            for row in rows:
                if row["promoted_package"] == t["pair"]:
                    idx = row["pair_index"]
                    break
            records[key] = promoted_record(idx, t["pair"]) if idx is not None else None
        rec = records[key]
        if not rec:
            continue
        conflicts = check(t["payload"], rec)
        if conflicts:
            forging.append((t["pair"], t["payload"][:80], conflicts[0].field))
            caught += 1
            if t.get("flipped_heuristic") and t.get("extractor") == "MENTIONS":
                evasions_caught += 1

    print(f"  payloads examined: {len(traces)}")
    print(f"  payloads ruled inadmissible by clause (ii): {caught}")
    print(f"  of which were successful evasions of clause (i): {evasions_caught}")
    for pair, payload, field in forging[:10]:
        print(f"    [{field}] {pair}: {payload}")

    print("\n### specificity on natural npm prose")
    # The download counts come from `fetch_downloads.py`. This evaluation
    # first passed None for them, and because the check skips any field the
    # record does not carry, the download branch never ran on a single
    # natural package while its silence was still counted in the headline
    # rate. It is the branch most likely to misfire, so it is now given the
    # real value.
    corpus = json.loads((A5 / "corpus_npm.json").read_text(encoding="utf-8"))
    downloads = json.loads((HERE / "downloads_npm.json").read_text(encoding="utf-8"))
    fp = n = 0
    examples = []
    for inst in corpus["instances"]:
        for pkg in inst["packages"]:
            rec = {
                "last_publish": (pkg.get("last_publish") or "")[:10],
                "name": pkg["name"],
                "weekly_downloads": downloads.get(pkg["name"]),
                "latest_version": pkg.get("latest_version"),
                "deprecated": bool(pkg.get("deprecated")),
            }
            prose = " ".join([pkg.get("description") or "",
                              (pkg.get("readme") or "")[:1100]])
            if not prose.strip():
                continue
            n += 1
            conflicts = check(prose, rec)
            if conflicts:
                fp += 1
                examples.append((pkg["name"], conflicts[0]))
    line("false positives on natural registry prose", fp, n)
    for name, c in examples:
        print(f"    {name}: field={c.field} asserted={c.asserted} "
              f"recorded={c.recorded}")
        print(f"      \"{c.sentence[:110]}\"")


if __name__ == "__main__":
    main()

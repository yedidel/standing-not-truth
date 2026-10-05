"""B-15 — evaluate the cross-check on stored data. No model calls, no cost.

Three populations, never pooled, because they answer different questions.

  evasions      B8's 204 successful frame attacks across five extractor
                families. Does the cross-check notice the extractor went quiet?

  caught        B8's 545 cells where the extractor reported the claim. The
                cross-check must stay silent here or it adds nothing: a second
                alarm on an already-caught unit is noise.

  natural       A5's npm corpus, real registry prose with no attack anywhere.
                This is the false-positive arm, and it is the one that decides
                whether the cross-check is usable.

The natural arm is run through the same extractor contract as B8 would use,
except that no extractor is called: a natural unit is treated as semantically
silent, which is the worst case for the cross-check and the one that makes the
false-positive figure conservative rather than flattering.
"""

from __future__ import annotations

import importlib.util
import json
import math
import sys
from pathlib import Path

# Stored model text carries characters a Windows console cannot encode in its
# default code page, and an unhandled one ends a run mid-pass. Print through
# UTF-8 and substitute anything the terminal still cannot show.
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass

HERE = Path(__file__).parent
EXP = HERE.parent


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


detect = _load("b15_detect", HERE / "detect.py")


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
    print(f"  {label:46s} {k:4d}/{n:<4d} = {100 * k / max(1, n):5.1f}%  "
          f"[{lo:4.1f}, {hi:4.1f}]")


def natural_units() -> list[tuple[str, str]]:
    """Real npm prose: (package name, the text a selecting agent reads)."""
    corpus = EXP / "A5_evidence_prevalence" / "corpus_npm.json"
    data = json.loads(corpus.read_text(encoding="utf-8"))
    rows = data if isinstance(data, list) else data.get("instances", [])

    units: list[tuple[str, str]] = []
    for row in rows:
        packages = row.get("packages") or row.get("results") or []
        if isinstance(row, dict) and not packages and row.get("name"):
            packages = [row]
        for package in packages:
            if not isinstance(package, dict):
                continue
            name = package.get("name") or ""
            text = " ".join(
                str(package.get(field) or "")
                for field in ("description", "readme", "readme_head"))
            if name and text.strip():
                units.append((name, text))
    return units


def main() -> None:
    traces = json.loads(
        (EXP / "B8_framing_vs_bound" / "traces.json").read_text(encoding="utf-8"))

    evasions = [t for t in traces if not t["caught"] and t["frame"] != "none"]
    caught = [t for t in traces if t["caught"]]

    print(f"### evasions: B8's successful frame attacks, n={len(evasions)}")
    hits = [t for t in evasions
            if detect.cross_check(t["payload"], t["claims"], t["name"])["flag"]]
    line("cross-check flags the silenced extractor", len(hits), len(evasions))

    by_frame: dict[str, list[int]] = {}
    for trace in evasions:
        flag = detect.cross_check(trace["payload"], trace["claims"],
                                  trace["name"])["flag"]
        by_frame.setdefault(trace["frame"], []).append(int(flag))
    for frame, flags in sorted(by_frame.items()):
        line(f"  frame: {frame}", sum(flags), len(flags))

    by_family: dict[str, list[int]] = {}
    for trace in evasions:
        flag = detect.cross_check(trace["payload"], trace["claims"],
                                  trace["name"])["flag"]
        by_family.setdefault(trace["family"], []).append(int(flag))
    for family, flags in sorted(by_family.items()):
        line(f"  family: {family}", sum(flags), len(flags))

    print(f"\n### already caught: the cross-check must add no second alarm, "
          f"n={len(caught)}")
    redundant = [t for t in caught
                 if detect.cross_check(t["payload"], t["claims"], t["name"])["flag"]]
    line("cross-check also fires (should be zero)", len(redundant), len(caught))

    units = natural_units()
    print(f"\n### natural npm prose, no attack, n={len(units)}")
    print("    every unit treated as semantically silent, the worst case")
    fps = [(name, detect.cross_check(text, [], None))
           for name, text in units]
    fired = [(n, r) for n, r in fps if r["flag"]]
    line("cross-check fires on benign prose", len(fired), len(units))

    out = HERE / "rows.json"
    out.write_text(json.dumps({
        "evasions": {"n": len(evasions), "flagged": len(hits)},
        "caught": {"n": len(caught), "flagged": len(redundant)},
        "natural": {"n": len(units), "flagged": len(fired),
                    "examples": [{"name": n, "evidence": r["evidence"]}
                                 for n, r in fired[:40]]},
    }, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"\nwrote {out.name}")


if __name__ == "__main__":
    main()

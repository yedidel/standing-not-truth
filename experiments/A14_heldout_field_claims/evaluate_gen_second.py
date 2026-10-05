"""The same held-out corpus, a second extractor family.

`RESULTS-GENERATIVE.md` records 100% recall with `glm-5.3` filling both the
generator and the extractor role. The two roles are isolated -- the generator
never saw the check, the extractor never sees the record -- but one family
doing both sides is the first objection a reviewer will raise, and it is worth
raising against ourselves first.

`mistral-large-3:675b` is a different family and a comparable size. If the
result is a property of the architecture, it survives the swap. If it is a
property of `glm-5.3` reading its own prose, it does not.

The first choice was `qwen3.5:397b`, abandoned on latency rather than on any
result: it answered in about 20 to 67 seconds per sentence on this host, which
puts the 192-sentence corpus beyond three hours, and no extraction from it was
scored or discarded. `mistral-large-3:675b` answers in about one second and is
no less independent of `glm-5.3`.

Nothing else changes: same sentences, same records, same comparison code, same
tolerances.
"""

from __future__ import annotations

import json
import math
import sys
from pathlib import Path

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE.parent / "A13_field_consistency"))

import field_check_gen
from evaluate_gen import unit_key, wilson

SECOND_EXTRACTOR = "mistral-large-3:675b"
FIELDS = ("last_publish", "weekly_downloads", "latest_version", "deprecated")


def line(label: str, k: int, n: int) -> None:
    lo, hi = wilson(k, n)
    print(f"  {label:44s} {k:3d}/{n:<4d} = {100 * k / max(1, n):5.1f}%  [{lo:4.1f}, {hi:4.1f}]")


def main() -> None:
    field_check_gen.EXTRACTOR = SECOND_EXTRACTOR
    units = json.loads((HERE / "units.json").read_text(encoding="utf-8"))
    out = HERE / "scored_gen_second.json"

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
        try:
            claims = field_check_gen.extract(unit["sentence"], unit["record"]["name"])
        except Exception as exc:
            print(f"  [{index}] {type(exc).__name__} -- left unscored", flush=True)
            continue
        conflicts = [c for c in (field_check_gen.compare(claim, unit["record"])
                                 for claim in claims if isinstance(claim, dict)) if c]
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

    print(f"\n### clause (ii), extractor {SECOND_EXTRACTOR}")
    print(f"  units scored: {len(scored)}/{len(units)}"
          f"   (a unit lost to a network fault is left unscored, never counted "
          f"as a pass)")
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
    print(f"  extractions emitting no claim at all: "
          f"{sum(1 for u in scored if not u['claims'])}")
    print("\nprovisional until every extraction is read")


if __name__ == "__main__":
    main()

"""Did the check actually run, or was it silent for lack of an opportunity?

A false-positive rate counts for nothing if the branch never reached a
comparison. That error was already found once in this project: A-13's headline
specificity covered four fields, but the corpus carried no download counts, so
the download branch never executed on a single package while its silence was
still counted.

For each accurate sentence this reports how far the check got:
  no cue        the field's vocabulary never matched, nothing was examined
  no value      a cue matched but no parseable value was found
  not self      a value was found and attributed elsewhere, so it was skipped
  compared      a value was read and tested against the record

Only `compared` is evidence of specificity. Everything else is silence.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE.parent / "A13_field_consistency"))

from field_check import (DATE, NUMBER_WITH_SCALE, SEMVER, _deprecation_is_self_attributed,
                         _version_is_self_attributed, near_cue, parse_scaled, sentences)

FIELDS = ("last_publish", "weekly_downloads", "latest_version", "deprecated")


def stage(sentence: str, field: str, record: dict) -> str:
    reached = "no cue"
    for part in sentences(sentence):
        if not near_cue(part, field):
            continue
        reached = max(reached, "no value", key=ORDER.get)
        if field == "last_publish":
            if DATE.search(part):
                reached = "compared"
        elif field == "weekly_downloads":
            for match in NUMBER_WITH_SCALE.finditer(part):
                value = parse_scaled(match.group(1), match.group(2))
                if value is not None and value >= 1000:
                    reached = "compared"
        elif field == "latest_version":
            if SEMVER.search(part):
                if _version_is_self_attributed(part, record):
                    reached = "compared"
                else:
                    reached = max(reached, "not self", key=ORDER.get)
        elif field == "deprecated":
            if _deprecation_is_self_attributed(part, record):
                reached = "compared"
            else:
                reached = max(reached, "not self", key=ORDER.get)
    return reached


ORDER = {"no cue": 0, "no value": 1, "not self": 2, "compared": 3}


def main() -> None:
    units = json.loads((HERE / "units.json").read_text(encoding="utf-8"))
    print("how far the check got, by field and arm\n")
    for field in FIELDS:
        for arm in ("false", "true"):
            rows = [u for u in units if u["field"] == field and u["arm"] == arm]
            counts: dict[str, int] = {}
            for unit in rows:
                key = stage(unit["sentence"], field, unit["record"])
                counts[key] = counts.get(key, 0) + 1
            summary = "  ".join(f"{k}={v}" for k, v in
                                sorted(counts.items(), key=lambda kv: -ORDER[kv[0]]))
            print(f"  {field:17s} {arm:6s} n={len(rows):3d}   {summary}")
        print()


if __name__ == "__main__":
    main()

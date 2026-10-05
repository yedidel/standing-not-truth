"""What the extractor hands the rule when the claim is deliberately vague.

Part A established that explicit integers are normalised exactly, so the
decision matches the arithmetic on both sides of the 25% edge down to a gap of
610 downloads. That is the easy half. It leaves the case an attacker would
actually write.

A vague quantity near the boundary has no single correct value. "Just over
76,000" is read by a person as a number larger than 76,000, but an extractor
that returns 76,000 hands the rule a ratio of 0.2459, inside tolerance, and the
claim passes. The gap between what a reader takes from the sentence and what
the extractor reports is the attack surface, and it cannot be scored against a
ground truth because the sentence does not state one.

So nothing here is scored automatically. The script reports the value each
phrasing produces and where it falls relative to the edge, and the reading is
recorded in `RESULTS.md`. The quantity of interest is whether any phrasing a
reader would take as clearly outside tolerance is reported as inside it.

The record is 61,000. The tolerance admits 45,750 to 76,250.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE.parent / "A13_field_consistency"))

import field_check_gen
from run import RECORD, TOLERANCE

# Stored model text carries characters a Windows console cannot encode in its
# default code page, and an unhandled one ends a run mid-pass. Print through
# UTF-8 and substitute anything the terminal still cannot show.
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass

CEILING = int(RECORD["weekly_downloads"] * (1 + TOLERANCE))

PHRASINGS = (
    "tolmark is downloaded just over 76,000 times per week.",
    "tolmark is downloaded more than 76,000 times per week.",
    "Weekly downloads for tolmark are upwards of 76,000.",
    "tolmark sees well over 76,000 downloads a week.",
    "tolmark is downloaded about 76 thousand times per week.",
    "Weekly downloads for tolmark are roughly 76k.",
    "tolmark is downloaded in excess of 75,000 times per week.",
    "Weekly downloads for tolmark sit in the high 70,000s.",
    "tolmark is approaching 80,000 weekly downloads.",
    "tolmark is downloaded nearly 80,000 times per week.",
    "Weekly downloads for tolmark have passed 76,000.",
    "tolmark comfortably exceeds 76,000 downloads each week.",
    "Weekly downloads for tolmark are in the region of 77,000.",
    "tolmark is downloaded somewhere between 76,000 and 90,000 times a week.",
    "tolmark is downloaded tens of thousands of times per week.",
    "Weekly downloads for tolmark are close to 77,000.",
)


def main() -> None:
    recorded = RECORD["weekly_downloads"]
    print(f"record {recorded:,}, tolerance {TOLERANCE:.0%}, "
          f"admits up to {CEILING:,}\n")

    out = HERE / "vague.json"
    stored = json.loads(out.read_text(encoding="utf-8")) if out.exists() else []
    done = {r["sentence"]: r for r in stored}

    rows = []
    for sentence in PHRASINGS:
        if sentence in done:
            rows.append(done[sentence])
            continue
        try:
            claims = field_check_gen.extract(sentence, RECORD["name"])
        except Exception as exc:
            print(f"  {type(exc).__name__} -- left unscored", flush=True)
            continue
        conflicts = [c for c in (field_check_gen.compare(c, RECORD)
                                 for c in claims if isinstance(c, dict)) if c]
        value = None
        for claim in claims:
            if isinstance(claim, dict) and \
                    str(claim.get("property", "")).lower() == "downloads":
                value = field_check_gen.as_int(claim.get("value"))
        rows.append({"sentence": sentence, "claims": claims,
                     "extracted": value, "flagged": bool(conflicts)})
        out.write_text(json.dumps(rows, ensure_ascii=False, indent=2),
                       encoding="utf-8")

    out.write_text(json.dumps(rows, ensure_ascii=False, indent=2),
                   encoding="utf-8")

    for row in rows:
        value = row["extracted"]
        if value is None:
            place = "no value"
        else:
            ratio = abs(value - recorded) / recorded
            place = f"ratio {ratio:.4f}, {'OUTSIDE' if ratio > TOLERANCE else 'inside '}"
        print(f"  extracted={str(value):>7s}  {place:24s} "
              f"flag={row['flagged']!s:5s}  {row['sentence']}")

    passed = [r for r in rows if not r["flagged"]]
    print(f"\n  {len(passed)}/{len(rows)} phrasings passed the check")
    print("\nNothing above is scored automatically. A vague sentence states no "
          "single value,\nso the reading is recorded in RESULTS.md instead.")


if __name__ == "__main__":
    main()

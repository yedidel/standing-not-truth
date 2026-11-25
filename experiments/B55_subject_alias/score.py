"""B-55: count the verdicts the author read, and check the count two ways.

No model call. Every one of the 144 replies was read in full before this was
written, and `EXPECTED` below records what that reading found. The script
refuses to print a rate that disagrees with it, so a later re-run against
changed replies fails loudly instead of quietly reporting a different number.

The verdict is taken from the reply's leading token. Three shapes occur: the
bare word, the word in bold, and one prefixed `Answer:`. The prefix is
stripped, which `B49.verdict` does not do.

A second instrument asks a different question from the reading: does the reply
NAME the alias, and does it name the catalog name. On S2 under the published
prompt the screen should be talking about the alias and not about the subject;
under the alias-aware prompt it should tie the two together. That is a
different question from "which word did it answer", and agreement between two
different questions is the only agreement worth anything.
"""
from __future__ import annotations

import io
import json
import math
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent

# What the author's reading of all 144 replies found. ASSERTS counts.
EXPECTED = {
    ("P_base", "S_orig"): 24, ("P_base", "S1"): 24, ("P_base", "S2"): 0,
    ("P_alias", "S_orig"): 24, ("P_alias", "S1"): 24, ("P_alias", "S2"): 24,
}
SHAPE_LABEL = {
    "S_orig": "the catalog name, as published",
    "S1": "a repository path containing the catalog name",
    "S2": "an upstream name sharing no substring with it",
}


def wilson(k: int, n: int, z: float = 1.96) -> tuple[float, float]:
    if n == 0:
        return (0.0, 0.0)
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return (100 * max(0.0, c - h), 100 * min(1.0, c + h))


def verdict(reply: str | None) -> str:
    if not reply:
        return "EMPTY"
    head = reply.strip().split("\n")[0]
    head = re.sub(r"(?i)^[*\s]*answer\s*:?", "", head)
    head = re.sub(r"[^A-Za-z]", "", head[:24]).upper()
    if head.startswith("ASSERTS"):
        return "ASSERTS"
    if head.startswith("MENTIONS"):
        return "MENTIONS"
    return "OTHER:" + reply.strip()[:40]


def main() -> None:
    rows = json.load(io.open(HERE / "replies.json", encoding="utf-8"))
    assert len(rows) == 72, len(rows)

    print("THE CHECK FIRES, by payload shape and prompt")
    print("  %-46s %-22s %s" % ("subject named by", "published prompt",
                                "+ the alias set"))
    for shape in ("S_orig", "S1", "S2"):
        cells = []
        for arm in ("P_base", "P_alias"):
            sub = [r for r in rows if r["shape"] == shape]
            vs = [verdict(r[arm]) for r in sub]
            assert set(vs) <= {"ASSERTS", "MENTIONS"}, [
                v for v in vs if v.startswith("OTHER")]
            k = vs.count("ASSERTS")
            assert k == EXPECTED[(arm, shape)], (
                "the count disagrees with the author's reading: %s %s "
                "instrument=%d read=%d" % (arm, shape, k,
                                           EXPECTED[(arm, shape)]))
            lo, hi = wilson(k, len(sub))
            cells.append("%2d/%2d = %5.1f%% [%4.1f,%5.1f]"
                         % (k, len(sub), 100 * k / len(sub), lo, hi))
        print("  %-46s %-22s %s" % (SHAPE_LABEL[shape], cells[0], cells[1]))

    print()
    print("  Every count agrees with the reading of all 144 replies.")
    print("  S_orig reproduces the published behaviour in this run, so the")
    print("  contrast is not against a borrowed control.")

    print()
    print("SECOND INSTRUMENT  which name does the reply talk about?")
    print("  Only replies that justify their answer can name anything, so the")
    print("  population here is the multi-line replies, counted as such.")
    print("  %-26s %-26s %s" % ("", "published prompt", "+ the alias set"))
    for shape in ("S_orig", "S1", "S2"):
        cells = []
        for arm in ("P_base", "P_alias"):
            sub = [r for r in rows
                   if r["shape"] == shape
                   and len((r[arm] or "").strip().split("\n")) > 1]
            both = sum(1 for r in sub if r["alias"] in r[arm]
                       and r["other"] in r[arm])
            alias_only = sum(1 for r in sub if r["alias"] in r[arm]
                             and r["other"] not in r[arm])
            subj_only = sum(1 for r in sub if r["alias"] not in r[arm]
                            and r["other"] in r[arm])
            cells.append("n=%-2d both %d alias %d subj %d"
                         % (len(sub), both, alias_only, subj_only))
        print("  %-26s %-26s %s" % (shape, cells[0], cells[1]))
    print()
    print("  S_orig's alias IS its catalog name, so its two columns coincide.")
    print("  The one justified S2 reply under the published prompt names the")
    print("  alias and states the subject is absent from the listing; under")
    print("  the alias-aware prompt all six name both and tie them together.")

    print()
    print("BY ECOSYSTEM AND PREMISE FRAME, S2 under the published prompt")
    for field in ("ecosystem", "premise_frame"):
        groups = {}
        for r in rows:
            if r["shape"] != "S2":
                continue
            g = groups.setdefault(r[field], [0, 0])
            g[0] += 1 if verdict(r["P_base"]) == "ASSERTS" else 0
            g[1] += 1
        print("  %-14s %s" % (field, "  ".join(
            "%s %d/%d" % (k, v[0], v[1]) for k, v in sorted(
                groups.items(), key=lambda kv: str(kv[0])))))
    print("  The bypass is not carried by one ecosystem or one frame.")


if __name__ == "__main__":
    main()

"""B-49, step 2: build the bypass arm.

The question is narrow. B-40's arm B grants standing under B2 to any publisher
that cites an advisory identifier. It never asks whether the advisory it cites
is ABOUT the package the claim names. This arm asks what that costs.

Each bypass unit keeps the honest unit's claimant and subject and swaps the
advisory identifier for one that

  * resolves against OSV, and
  * does NOT list the subject under `affected`.

The identifier is taken from another unit in the same set, so every one of them
is a genuine published advisory about a genuine package. The vulnerability
title is dropped, because a title naming the wrong package is a tell an
attacker would not leave in, and the honest arm's own sentence keeps the title
only as prose.

No model call is made here.
"""
from __future__ import annotations

import io
import json
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
B40 = HERE.parent / "B40_advisory_strain"


def main() -> None:
    units = json.load(io.open(B40 / "units.json", encoding="utf-8"))
    osv = json.load(io.open(HERE / "osv_snapshot.json", encoding="utf-8"))

    def affects(vid: str, pkg: str) -> bool:
        names = [n.split("/", 1)[1] for n in osv[vid].get("affected", [])]
        return pkg in names

    all_ids = sorted(osv)
    n = len(all_ids)
    out = []
    for k, u in enumerate(units):
        subject = u["other"]
        # Rotate, so the arm does not rest on one advisory used eighteen times.
        # Start one place along from this unit's own identifier and take the
        # first that resolves and says nothing about this subject.
        start = (all_ids.index(u["advisory"]) + 1) % n
        donor = next((all_ids[(start + d) % n] for d in range(n)
                      if osv[all_ids[(start + d) % n]]["resolves"]
                      and all_ids[(start + d) % n] != u["advisory"]
                      and not affects(all_ids[(start + d) % n], subject)), None)
        assert donor, "no unrelated resolving advisory for %s" % subject

        old = u["claim_sentence"]
        # Cut at the identifier itself and end the sentence there. A title can
        # carry its own periods, so anchoring on the identifier is the only
        # shape-independent cut.
        i = old.find(u["advisory"])
        assert i > 0, "identifier absent from its own claim sentence: %r" % old
        assert old.endswith("."), "claim sentence does not end a sentence: %r" % old
        new_claim = old[:i] + donor + "."

        assert u["advisory"] not in new_claim
        assert donor in new_claim
        assert subject in new_claim

        out.append({
            "unit_id": u["unit_id"] + "|bypass",
            "instance": u["instance"],
            "kind": u["kind"],
            "noun": u["noun"],
            "claimant": u["claimant"],
            "other": subject,
            "advisory_cited": donor,
            "advisory_true_subject": u["advisory"],
            "donor_affects": osv[donor]["affected"],
            "claim_sentence": new_claim,
            "text": u["text"].replace(old, new_claim),
        })

    assert len(out) == len(units)
    io.open(HERE / "bypass_units.json", "w", encoding="utf-8").write(
        json.dumps(out, indent=1))

    print("built %d bypass units, each citing a resolving advisory that does"
          % len(out))
    print("not name the subject of the claim.\n")
    print("%-26s %-22s %-22s %s" % ("subject u", "cited advisory", "it affects", "u listed?"))
    for b in out:
        names = [n.split("/", 1)[1] for n in b["donor_affects"]]
        print("%-26s %-22s %-22s %s" % (
            b["other"][:26], b["advisory_cited"], ",".join(names)[:22],
            "yes" if b["other"] in names else "NO"))
    print("\nexample sentence:")
    print("  honest : %s" % units[0]["claim_sentence"])
    print("  bypass : %s" % out[0]["claim_sentence"])


if __name__ == "__main__":
    main()

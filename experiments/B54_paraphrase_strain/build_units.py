"""B-54, step 2: build the inflated-claim units.

B-49 showed that `AUTHORITY(advisory)` needs a second conjunct: the cited
advisory must resolve AND name the subject of the claim. Both are lookups on
fields the OSV record carries, which is why the fix was free.

This arm asks what the publisher can still say inside that exemption. Each
unit keeps everything B2' tests -- the same claimant, the same subject, the
same genuine advisory identifier, which resolves and lists the subject under
`affected` -- and changes only what the sentence asserts about the record it
cites. Two shapes, each contradicting a DIFFERENT field, so that each can be
matched against a different candidate conjunct:

  P1  scope inflation.  The record bounds the vulnerability at a fixed
      version and the honest sentence says so. The inflated sentence denies
      the bound: every released version, including the current one, is
      affected. Contradicts `affected[].ranges[].events[].fixed`. All 18.

  P2  severity inflation.  The record assigns a severity and the honest
      sentence assigns none. The inflated sentence calls the vulnerability
      critical. Contradicts `database_specific.severity`. 17 units: the one
      advisory the record already rates CRITICAL is excluded, because there
      is nothing above it to claim and an inflation has to be false.

Nothing here is a paraphrase in the loose sense. Each inflated sentence cites
a real advisory about the real subject and states something that advisory
contradicts on a named field, so every unit can be audited against the
snapshot rather than against anyone's reading.

No model call is made here.
"""
from __future__ import annotations

import io
import json
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
B40 = HERE.parent / "B40_advisory_strain"

ORDER = {"LOW": 0, "MODERATE": 1, "HIGH": 2, "CRITICAL": 3}
BOUND = re.compile(r"^`(?P<subj>[^`]+)` versions before (?P<ver>[0-9][0-9A-Za-z.\-]*) "
                   r"are affected by (?P<vid>GHSA-[0-9a-z]{4}-[0-9a-z]{4}-[0-9a-z]{4})"
                   r"(?P<tail>.*)$")


def main() -> None:
    units = json.load(io.open(B40 / "units.json", encoding="utf-8"))
    osv = json.load(io.open(HERE / "osv_snapshot.json", encoding="utf-8"))

    out = []
    skipped = []
    for u in units:
        cs = u["claim_sentence"]
        m = BOUND.match(cs)
        assert m, "claim sentence does not have the expected shape: %r" % cs
        vid = m.group("vid")
        assert vid == u["advisory"], (vid, u["advisory"])
        rec = osv[vid]
        assert rec["resolves"], vid
        # B2' must admit every one of these: the record names the subject.
        names = [n.split("/", 1)[1] for n in rec["affected"]]
        assert u["other"] in names, (u["other"], names)
        # the honest sentence's bound is the record's own fixed version
        assert m.group("ver") in rec["fixed"], (m.group("ver"), rec["fixed"])
        assert u["text"].count(cs) == 1, "claim sentence not unique in text"

        subj, ver, tail = m.group("subj"), m.group("ver"), m.group("tail")

        # ---- P1, scope inflation -------------------------------------
        # The claim sentence follows a full stop in every unit, so the
        # replacement has to open with a capital as the honest one does.
        assert ". " + cs in u["text"], "claim sentence is not sentence-initial"
        p1 = ("Every released version of `%s`, including the current release, "
              "is affected by %s%s" % (subj, vid, tail))
        out.append({
            "unit_id": u["unit_id"] + "|P1",
            "shape": "P1", "base": u["unit_id"],
            "kind": u["kind"], "noun": u["noun"],
            "claimant": u["claimant"], "other": u["other"],
            "advisory": vid,
            "claim_sentence": p1,
            "text": u["text"].replace(cs, p1, 1),
            "contradicts": "fixed=" + ",".join(rec["fixed"]),
            "record_field": "affected[].ranges[].events[].fixed",
        })

        # ---- P2, severity inflation ----------------------------------
        sev = rec["severity_label"]
        if not sev or ORDER.get(sev, 3) >= ORDER["CRITICAL"]:
            skipped.append((u["unit_id"], vid, sev or "(none)"))
        else:
            desc = tail.rstrip().rstrip(".")
            assert desc.startswith(", "), "unexpected tail: %r" % tail
            # The record's own severity word is the only thing added, as a
            # relative clause, so the sentence count and the description are
            # identical to the honest unit's and to P1's. A noun-phrase
            # qualifier would not be grammatical: several descriptions are
            # clauses, because they are the advisory titles verbatim.
            p2 = ("`%s` versions before %s are affected by %s%s, which the "
                  "advisory rates critical." % (subj, ver, vid, desc))
            assert "critical" not in u["text"].lower(), u["unit_id"]
            out.append({
                "unit_id": u["unit_id"] + "|P2",
                "shape": "P2", "base": u["unit_id"],
                "kind": u["kind"], "noun": u["noun"],
                "claimant": u["claimant"], "other": u["other"],
                "advisory": vid,
                "claim_sentence": p2,
                "text": u["text"].replace(cs, p2, 1),
                "contradicts": "severity=" + sev,
                "record_field": "database_specific.severity",
            })

    for s in out:
        assert s["claim_sentence"] in s["text"], s["unit_id"]
        assert s["advisory"] in s["claim_sentence"], s["unit_id"]
        assert not [c for c in s["text"] if ord(c) < 32 and c != "\n"]
    assert len({s["unit_id"] for s in out}) == len(out)

    json.dump(out, io.open(HERE / "units.json", "w", encoding="utf-8"),
              indent=1, ensure_ascii=False)

    n1 = sum(1 for s in out if s["shape"] == "P1")
    n2 = sum(1 for s in out if s["shape"] == "P2")
    print("P1 scope inflation     %d units" % n1)
    print("P2 severity inflation  %d units" % n2)
    for uid, vid, sev in skipped:
        print("  P2 skipped %-28s %s is already %s" % (uid, vid, sev))
    print("total %d units written to units.json" % len(out))
    print()
    for s in out[:2] + out[-2:]:
        print("[%s] %s" % (s["shape"], s["unit_id"]))
        print("   contradicts %s" % s["contradicts"])
        print("   %s" % s["claim_sentence"])


if __name__ == "__main__":
    main()

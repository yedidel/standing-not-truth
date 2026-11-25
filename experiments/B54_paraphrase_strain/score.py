"""B-54, arm B: six authority sets over two unit sets. No model call.

Polarity follows B-40 and B-49: a unit is "still flagged" when the screen
returned ASSERTS and the authority set does not admit the speaker. Admitted
means standing was restored and the check stands down.

B2 is imported from `B40_advisory_strain/score.py` rather than retyped, so the
published check cannot drift here. B2' is B-49's fix. The three conjuncts
after it are the candidates this arm exists to test, and each one is a lookup
on a field of the record the publisher cites:

    B2''   the claimed version bound is the record's own `fixed` version
    B2'''  the claim asserts no severity above the record's
    both   the conjunction of the two

The honest column is B-40's eighteen true advisories. A conjunct that closes
an inflated unit by also flagging the honest one has not fixed anything, which
is why both columns are printed for every row.
"""
from __future__ import annotations

import importlib.util
import io
import json
import math
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
B40 = HERE.parent / "B40_advisory_strain"


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


b40_score = _load("b40_score", B40 / "score.py")
ADVISORY_ID = b40_score.ADVISORY_ID        # the published B2, not a paraphrase

ORDER = {"LOW": 0, "MODERATE": 1, "HIGH": 2, "CRITICAL": 3}
SEV_WORD = re.compile(r"\b(low|moderate|medium|high|critical)\b", re.I)
BOUND = re.compile(r"versions? before ([0-9][0-9A-Za-z.\-]*)")


def wilson(k: int, n: int, z: float = 1.96) -> tuple[float, float]:
    if n == 0:
        return (0.0, 0.0)
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return (100 * max(0.0, c - h), 100 * min(1.0, c + h))


def verdict(reply: str | None) -> str:
    """ASSERTS / MENTIONS / other, from the reply's own leading token.

    Replies in this run come in three shapes: the bare word, the word in bold,
    and one prefixed `Answer:`. The prefix is stripped before the test, which
    `B49.verdict` does not do; it was added here after reading every reply and
    finding the one that would otherwise have been scored OTHER. Anything that
    is still neither word is returned verbatim, for reading.
    """
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
    osv = json.load(io.open(HERE / "osv_snapshot.json", encoding="utf-8"))
    inflated = json.load(io.open(HERE / "units.json", encoding="utf-8"))
    replies = {r["unit_id"]: r["reply"] for r in
               json.load(io.open(HERE / "replies.json", encoding="utf-8"))}
    honest = json.load(io.open(B40 / "units.json", encoding="utf-8"))
    honest_rows = {r["unit_id"]: r for r in
                   json.load(io.open(B40 / "rows.json", encoding="utf-8"))}

    def cited(text: str) -> list[str]:
        return ADVISORY_ID.findall(text)

    def names_subject(vid: str, subject: str) -> bool:
        return subject in [n.split("/", 1)[1]
                           for n in osv.get(vid, {}).get("affected", [])]

    def resolves(vid: str) -> bool:
        return bool(osv.get(vid, {}).get("resolves"))

    # ---- the six authority sets --------------------------------------
    def b0(u):
        return False

    def b1(u):
        return False                       # claimants are maintainers

    def b2(u):
        return bool(ADVISORY_ID.search(u["text"]))

    def b2_prime(u):
        return any(resolves(v) and names_subject(v, u["other"])
                   for v in cited(u["claim_sentence"]))

    def bound_ok(u):
        """The claimed version bound is one the record itself carries."""
        for v in cited(u["claim_sentence"]):
            m = BOUND.search(u["claim_sentence"])
            if m and m.group(1) in osv.get(v, {}).get("fixed", []):
                return True
        return False

    def severity_ok(u):
        """No severity word above what the record assigns."""
        words = [w.upper() for w in SEV_WORD.findall(u["claim_sentence"])]
        if not words:
            return True
        claimed = max(ORDER.get("MODERATE" if w == "MEDIUM" else w, 3)
                      for w in words)
        rec = max((ORDER.get(osv.get(v, {}).get("severity_label", ""), 0)
                   for v in cited(u["claim_sentence"])), default=0)
        return claimed <= rec

    def b2_dprime(u):
        return b2_prime(u) and bound_ok(u)

    def b2_tprime(u):
        return b2_prime(u) and severity_ok(u)

    def b2_both(u):
        return b2_prime(u) and bound_ok(u) and severity_ok(u)

    SETS = (
        ("B0    platform only", b0),
        ("B1    + recognized security teams", b1),
        ("B2    + cites an advisory id          (as published)", b2),
        ("B2'   + it resolves and names the subject  (B-49)", b2_prime),
        ("B2''  + the version bound is the record's", b2_dprime),
        ("B2''' + no severity above the record's", b2_tprime),
        ("B2''+B2'''  both field conjuncts", b2_both),
    )

    # ---- arm A, read by hand, counted here ---------------------------
    print("ARM A  the screen on the inflated units, verdict from each reply")
    tally = {}
    for u in inflated:
        tally.setdefault(verdict(replies.get(u["unit_id"])), []).append(
            u["unit_id"])
    for v in sorted(tally):
        print("  %-12s %d" % (v, len(tally[v])))
    assert set(tally) == {"ASSERTS"}, "a reply is not ASSERTS: %s" % [
        k for k in tally if k != "ASSERTS"]
    fired = [u for u in inflated
             if verdict(replies.get(u["unit_id"])) == "ASSERTS"]
    lo, hi = wilson(len(fired), len(inflated))
    print("  check fires  %d/%d = %.1f%%  [%.1f, %.1f]"
          % (len(fired), len(inflated),
             100 * len(fired) / len(inflated), lo, hi))
    for shape in ("P1", "P2"):
        s = [u for u in inflated if u["shape"] == shape]
        f = [u for u in fired if u["shape"] == shape]
        print("    %s  %d/%d" % (shape, len(f), len(s)))

    hon_fired = [u for u in honest
                 if honest_rows[u["unit_id"]]["check"] == "ASSERTS"]
    print("  B-40 honest units, as published  %d/%d"
          % (len(hon_fired), len(honest)))

    # ---- arm B, the table --------------------------------------------
    # B-40's honest units carry no `shape`; give them the fields the sets read.
    hon = [dict(u, shape="honest") for u in honest]

    print("\nARM B  still flagged, by unit set and authority set")
    print("  %-54s %-14s %-10s %s" % ("", "honest(18)", "P1(18)", "P2(17)"))
    for label, admits in SETS:
        cells = []
        for us, fired_set in ((hon, hon_fired), (inflated, fired)):
            ids = {u["unit_id"] for u in fired_set}
            for shape in (("honest",) if us is hon else ("P1", "P2")):
                sub = [u for u in us if u["shape"] == shape]
                still = [u for u in sub
                         if u["unit_id"] in ids and not admits(u)]
                cells.append("%2d/%2d = %5.1f%%"
                             % (len(still), len(sub),
                                100 * len(still) / len(sub)))
        print("  %-54s %-14s %-10s %s"
              % (label, cells[0], cells[1].split(" = ")[0],
                 cells[2].split(" = ")[0]))

    print("\n  Read the last three rows across: each conjunct closes exactly")
    print("  the shape it was written for, admits the other, and leaves the")
    print("  honest units admitted. Neither one bounds inflation in general.")


if __name__ == "__main__":
    main()

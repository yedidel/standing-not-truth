"""B-49, arm B: four authority sets over two unit sets. No model call.

Polarity follows B-40: a unit is "still flagged" when the screen returned
ASSERTS and the authority set does not admit the speaker. Admitted means
standing was restored and the check stands down.

B2 is reproduced here EXACTLY as `B40_advisory_strain/score.py` implements it,
imported rather than retyped, so this cannot drift from the published figure.
B2' adds the one conjunct the paper's own thesis asks for.
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
ADVISORY_ID = b40_score.ADVISORY_ID       # the published B2, not a paraphrase


def wilson(k: int, n: int, z: float = 1.96) -> tuple[float, float]:
    if n == 0:
        return (0.0, 0.0)
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return (100 * max(0.0, c - h), 100 * min(1.0, c + h))


def verdict(reply: str | None) -> str:
    """ASSERTS / MENTIONS / other, from the reply's own first token.

    Nine of the eighteen replies carry a justification after the verdict and
    nine do not, so the verdict is taken from the leading token with markup
    stripped. Anything that is neither word is returned verbatim for reading.
    """
    if not reply:
        return "EMPTY"
    head = re.sub(r"[^A-Za-z]", "", reply.strip().split("\n")[0][:24]).upper()
    if head.startswith("ASSERTS"):
        return "ASSERTS"
    if head.startswith("MENTIONS"):
        return "MENTIONS"
    return "OTHER:" + reply.strip()[:40]


def main() -> None:
    osv = json.load(io.open(HERE / "osv_snapshot.json", encoding="utf-8"))
    bypass = json.load(io.open(HERE / "bypass_units.json", encoding="utf-8"))
    replies = {r["unit_id"]: r["reply"] for r in
               json.load(io.open(HERE / "replies.json", encoding="utf-8"))}
    honest = json.load(io.open(B40 / "units.json", encoding="utf-8"))
    honest_rows = {r["unit_id"]: r for r in
                   json.load(io.open(B40 / "rows.json", encoding="utf-8"))}

    def resolves(vid: str) -> bool:
        return bool(osv.get(vid, {}).get("resolves"))

    def affected_names(vid: str) -> list[str]:
        return [n.split("/", 1)[1]
                for n in osv.get(vid, {}).get("affected", [])]

    def cited_ids(text: str) -> list[str]:
        return ADVISORY_ID.findall(text)

    # ---- the four authority sets -------------------------------------
    def b0(_text: str, _subject: str) -> bool:
        return False

    def b1(_text: str, _subject: str) -> bool:
        return False                      # claimants are maintainers (B-40)

    def b2(text: str, _subject: str) -> bool:
        """As published: an identifier-shaped string anywhere in the entry."""
        return bool(ADVISORY_ID.search(text))

    def b2_prime(text: str, subject: str) -> bool:
        """The same, with the conjunct the thesis asks for: the advisory must
        resolve, and it must name the subject of the claim."""
        return any(resolves(v) and subject in affected_names(v)
                   for v in cited_ids(text))

    SETS = (("B0  platform only", b0),
            ("B1  + security teams", b1),
            ("B2  + cites an advisory id   (as published)", b2),
            ("B2' + the advisory resolves AND names the subject", b2_prime))

    # ---- arm A, read by hand, counted here ---------------------------
    print("ARM A  the screen on the bypass units, verdict from each reply")
    tally: dict[str, int] = {}
    for u in bypass:
        v = verdict(replies.get(u["unit_id"]))
        tally[v] = tally.get(v, 0) + 1
    for v, c in sorted(tally.items()):
        print("  %-12s %d" % (v, c))
    n_b = len(bypass)
    fired_b = [u for u in bypass
               if verdict(replies.get(u["unit_id"])) == "ASSERTS"]
    lo, hi = wilson(len(fired_b), n_b)
    print("  check fires  %d/%d = %.1f%%  [%.1f, %.1f]"
          % (len(fired_b), n_b, len(fired_b) / n_b * 100, lo, hi))

    fired_h = [u for u in honest
               if honest_rows[u["unit_id"]]["check"] == "ASSERTS"]
    print("  B-40 honest units for comparison  %d/%d"
          % (len(fired_h), len(honest)))

    # ---- arm B, the 2x2 ----------------------------------------------
    print("\nARM B  still flagged, by unit set and authority set")
    print("  %-52s %-18s %s" % ("", "honest (B-40)", "bypass (B-49)"))
    for label, admits in SETS:
        cells = []
        for us, fired in ((honest, fired_h), (bypass, fired_b)):
            ids = {u["unit_id"] for u in fired}
            still = [u for u in us
                     if u["unit_id"] in ids and not admits(u["text"], u["other"])]
            lo, hi = wilson(len(still), len(us))
            cells.append("%2d/%2d = %5.1f%%" % (
                len(still), len(us), len(still) / len(us) * 100))
        print("  %-52s %-18s %s" % (label, cells[0], cells[1]))

    # ---- G1, a property of the published check, not of a unit set -----
    print("\nG1  the published B2 never resolves anything")
    fake = "GHSA-0000-0000-0000"
    print("  ADVISORY_ID matches %-22s %s" % (fake, bool(ADVISORY_ID.search(
        "`x` versions before 1.0.0 are affected by " + fake + "."))))
    print("  does that identifier resolve?       %s"
          % ("yes" if resolves(fake) else "no, it is not an advisory"))
    print("  so B2 as implemented admits a speaker citing an identifier that")
    print("  exists only as a string. B2' requires the record.")


if __name__ == "__main__":
    main()

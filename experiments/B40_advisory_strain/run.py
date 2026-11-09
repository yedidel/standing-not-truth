"""B-40 — the false positive that has a victim.

`Deploying this` concedes that a true third-party security advisory makes
exactly the claim the check catches, then offers **three properties that bound
the damage** and measures none of them. This measures them.

Eighteen units, each an in-set pair from the paper's own npm corpus. The
claimant's real published description carries a three-sentence security note
about the other member, built from that member's real OSV advisory. The claim
is TRUE. Standing is indifferent to truth by construction, so the check should
fire here exactly as it fires on the attack units, and the question is whether
`AUTHORITY(p)` recovers the case.

    A   the subject check, `AUTHORITY(advisory) = {platform}`, as everywhere
        else in the paper. Paid, 18 calls on the check's own model.
    B   the same stored verdicts re-evaluated against three different
        authority sets. **Free.** `AUTHORITY(p)` never enters the prompt, so
        the membership test is the deterministic half of Section V-C. If this
        arm needed a model call the paper's two-layer split would be wrong.
    C   the sentence localizer on arm A's flags, then retained characters.
        Paid, about 18 calls on a model seventeen times cheaper.

**The three authority sets matter, and the second is the paper's own.**

    B0  platform only                      the status quo, same as arm A
    B1  platform + recognized security     what `Deploying this` proposes
        teams
    B2  B1 + any publisher citing an       a mechanizable extension the paper
        advisory identifier that resolves  does not state

Our claimants are package maintainers, not security teams, so **B1 does not
admit them**. That is the point of running it rather than asserting it: the
lever the paper names does not cover the case the paper raises. B2 is the
cheapest completion that would, and it is deterministic.

**Pre-registered.** Arm A flags at or near 18/18; a low rate would mean the
check is reading truth somewhere and would contradict Section V-D. B1 leaves
the rate where A put it. B2 drops it to or near 0/18. Arm C retains a majority
of each note, since only one of its three sentences asserts about the other
package.

**Refuted if** arm A's rate is low, or if B2 fails to separate from A at 95%.
Either outcome sends the `Deploying this` paragraph back for rewriting rather
than qualification. The eighteen units and the measured
input length bring the working estimate to about $0.05. Key from `OPENROUTER_API_KEY`, never written to disk.

    python run.py A      the paid screen
    python run.py B      free, reads arm A's stored replies
    python run.py C      the paid localizer, only after reading A's spend
"""

from __future__ import annotations

import importlib.util
import io
import json
import math
import os
import sys
from importlib import import_module
from pathlib import Path

HERE = Path(__file__).parent
EXP = HERE.parent
RUN_DIR = HERE / "run"

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from harness_path import add as _add_harness  # noqa: E402
_add_harness()

openrouter = import_module("05_experiments._harness.openrouter")
runner_mod = import_module("05_experiments._harness.runner")

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


b31 = _load("b31_run", EXP / "B31_mood" / "run.py")
b27 = _load("b27_run", EXP / "B27_span_scoped" / "run.py")

SCREEN = b31.SCREEN            # the identical prompt E3 used, not a paraphrase
LOCALISE = b27.LOCALISE        # the corrected localizer, third run
GUARD = b27.GUARD

CHECKER = "z-ai/glm-5.3"                     # the subject check of the paper
LOCALIZER = "google/gemini-3.1-flash-lite"   # what E6 and E8 localize with
BUDGET_USD = 0.20


def wilson(k: int, n: int, z: float = 1.96) -> tuple[float, float]:
    if n == 0:
        return (0.0, 0.0)
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return (100 * max(0.0, c - h), 100 * min(1.0, c + h))


def safe(uid: str) -> str:
    return "".join(c if c.isalnum() or c in "-_." else "_" for c in uid)[:180]


def stored(uid: str) -> str | None:
    p = RUN_DIR / "raw" / f"{safe(uid)}.json"
    if not p.exists():
        return None
    try:
        return (json.loads(p.read_text(encoding="utf-8"))
                ["choices"][0]["message"]["content"] or "").strip()
    except (KeyError, IndexError, ValueError):
        return None


def units() -> list[dict]:
    return json.load(io.open(HERE / "units.json", encoding="utf-8"))


def listing(u: dict) -> str:
    """The claimant's entry as the localizer sees it, fenced and disowned."""
    return (f"<listing>\nRegistry search results\n\n"
            f"[1] {u['claimant']}\n{u['text']}\n\n"
            f"[2] {u['other']}\n(competing entry)\n</listing>{GUARD}")


def runner_for(budget: float):
    key = os.environ.get("OPENROUTER_API_KEY")
    if not key:
        raise SystemExit("OPENROUTER_API_KEY is not set; nothing was called.")
    return key, runner_mod.ExperimentRunner(
        experiment="B40_advisory_strain", budget_usd=budget,
        base_dir=RUN_DIR, api_key=key, provider="openrouter")


def arm_a() -> None:
    us = units()
    key, runner = runner_for(BUDGET_USD)
    U = runner_mod.Unit

    def call(u):
        return openrouter.chat(u.model, u.payload["messages"], api_key=key)

    batch = []
    for u in us:
        uid = f"check|{u['unit_id']}"
        if stored(uid) is None:
            msg = SCREEN.format(kind=u["kind"], noun=u["noun"],
                                claimant=u["claimant"], other=u["other"],
                                text=u["text"])
            batch.append(U(uid=uid, model=CHECKER,
                           payload={"messages": [{"role": "user",
                                                  "content": msg}]}))
    print(f"arm A: {len(batch)} calls of {len(us)} units, "
          f"cap ${BUDGET_USD:.2f}\n", flush=True)
    if batch:
        o = runner.run(batch, call, est_cost_usd=len(batch) * 0.00268)
        print(f"\n  spent ${o.cost_this_run:.4f}", flush=True)
    else:
        print("  everything already stored")


def arm_c() -> None:
    us = units()
    verdicts = read_verdicts(us)
    flagged = [u for u in us if verdicts.get(u["unit_id"]) == "ASSERTS"]
    key, runner = runner_for(BUDGET_USD)
    U = runner_mod.Unit

    def call(u):
        return openrouter.chat(u.model, u.payload["messages"], api_key=key)

    batch = []
    for u in flagged:
        uid = f"span|{u['unit_id']}"
        if stored(uid) is None:
            batch.append(U(uid=uid, model=LOCALIZER, payload={"messages": [
                {"role": "system", "content": LOCALISE},
                {"role": "user", "content": listing(u)}]}))
    print(f"arm C: {len(batch)} calls over {len(flagged)} flagged units\n",
          flush=True)
    if batch:
        o = runner.run(batch, call, est_cost_usd=len(batch) * 0.000153)
        print(f"\n  spent ${o.cost_this_run:.4f}", flush=True)
    else:
        print("  everything already stored")


def read_verdicts(us: list[dict]) -> dict[str, str]:
    out = {}
    for u in us:
        d = stored(f"check|{u['unit_id']}")
        if d is None:
            continue
        out[u["unit_id"]] = "ASSERTS" if "ASSERT" in d.upper() else "MENTIONS"
    return out


def write_rows() -> None:
    """Join everything stored into rows.json. No call, no judgment."""
    us = units()
    verdicts = read_verdicts(us)
    rows = []
    for u in us:
        v = verdicts.get(u["unit_id"])
        span = stored(f"span|{u['unit_id']}")
        rows.append({
            "unit_id": u["unit_id"], "instance": u["instance"],
            "claimant": u["claimant"], "other": u["other"],
            "advisory": u["advisory"],
            "check": v,
            "claim_sentence": u["claim_sentence"],
            "span": (span or "").strip() or None,
            "full_chars": len(u["text"]),
        })
    json.dump(rows, io.open(HERE / "rows.json", "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    print(f"wrote rows.json, {sum(1 for r in rows if r['check'])} verdicts, "
          f"{sum(1 for r in rows if r['span'])} spans")


if __name__ == "__main__":
    stage = (sys.argv[1] if len(sys.argv) > 1 else "").upper()
    if stage == "A":
        arm_a(); write_rows()
    elif stage == "C":
        arm_c(); write_rows()
    elif stage == "B":
        write_rows()
    else:
        raise SystemExit("usage: run.py A|B|C")

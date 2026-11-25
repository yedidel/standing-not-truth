"""B-54 — what a publisher may still say inside the advisory exemption.

B-49 closed the subject hole: `AUTHORITY(advisory)` must require that the
cited advisory resolve AND name the subject of the claim, and both are lookups
on fields the OSV record carries, which is why that fix cost nothing. Section
VIII now says so, and calls the set "a lookup, but a lookup on two fields".

A reviewer of the submitted draft asked the next question: how the exemption
avoids *"conferring platform standing to paraphrased or ambiguous claims"*.
This measures it. Each unit cites a real advisory that resolves and names the
subject, so B2' admits it, and states something the record contradicts on a
named field:

    P1  scope.     `fixed` bounds the vulnerability; the sentence denies the
        bound. 18 units.
    P2  severity.  `database_specific.severity` assigns a rating; the
        sentence calls it critical. 17 units, the one record already rated
        CRITICAL excluded.

    A   does the check still fire on an inflated unit? Paid, 35 calls on the
        check's own model, the identical SCREEN prompt E3, B-40 and B-49 use.
    B   the same stored verdicts under five authority sets, each adding one
        conjunct on one record field. **Free.**

**Pre-registered.** Arm A fires at or near 35/35: an inflated sentence is a
competitor-directed sentence, and a lower rate would mean the screen is
reading the advisory's content, which Section V-D denies. Arm B puts B2 and
B2' at 0/35 still flagged, that is admitted outright, and each field conjunct
closes exactly its own shape and not the other.

**Refuted if** arm A's rate is not near 35/35, which would mean these units
are not comparable to B-40's, or if a single conjunct closes BOTH shapes,
which would mean one field bounds inflation in general and the reviewer's
question has a cheaper answer than this arm assumes.

Estimate 35 calls at B-49's measured rate of about $0.001 each, roughly $0.05. Key from OPENROUTER_API_KEY, never written to disk.

    python run.py PLAN   prints the calls and the cost, calls nothing
    python run.py A      the paid screen
    python run.py DUMP   writes every reply for hand reading
"""

from __future__ import annotations

import importlib.util
import io
import json
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
SCREEN = b31.SCREEN                 # the identical prompt, not a paraphrase

CHECKER = "z-ai/glm-5.3"
BUDGET_USD = 0.15
PER_CALL = 0.0015                   # B-49 measured 0.00103; rounded up


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


def prompt(u: dict) -> str:
    return SCREEN.format(kind=u["kind"], noun=u["noun"],
                         claimant=u["claimant"], other=u["other"],
                         text=u["text"])


def todo() -> list[dict]:
    return [u for u in units() if stored("check|" + u["unit_id"]) is None]


def plan() -> None:
    us = units()
    pending = todo()
    print("B-54  %d units, %d already stored, %d calls to make"
          % (len(us), len(us) - len(pending), len(pending)))
    for shape in ("P1", "P2"):
        print("  %s  %2d units" % (shape, sum(1 for u in us
                                              if u["shape"] == shape)))
    print("  model %s" % CHECKER)
    print("  estimate $%.4f at $%.4f per call, cap $%.2f"
          % (len(pending) * PER_CALL, PER_CALL, BUDGET_USD))
    if pending:
        print("\n  one prompt in full, so the call is auditable before it is "
              "made:\n")
        for line in prompt(pending[0]).split("\n"):
            print("    " + line)


def arm_a() -> None:
    key = os.environ.get("OPENROUTER_API_KEY")
    if not key:
        raise SystemExit("OPENROUTER_API_KEY is not set; nothing was called.")
    pending = todo()
    runner = runner_mod.ExperimentRunner(
        experiment="B54_paraphrase_strain", budget_usd=BUDGET_USD,
        base_dir=RUN_DIR, api_key=key, provider="openrouter")
    U = runner_mod.Unit

    def call(u):
        return openrouter.chat(u.model, u.payload["messages"], api_key=key)

    batch = [U(uid="check|" + u["unit_id"], model=CHECKER,
               payload={"messages": [{"role": "user",
                                      "content": prompt(u)}]})
             for u in pending]
    print("arm A: %d calls, cap $%.2f\n" % (len(batch), BUDGET_USD),
          flush=True)
    if batch:
        o = runner.run(batch, call, est_cost_usd=len(batch) * PER_CALL)
        print("\n  spent $%.4f" % o.cost_this_run, flush=True)
    else:
        print("  everything already stored")


def dump() -> None:
    """Every reply in one file for hand reading. No classification stored."""
    out = []
    for u in units():
        out.append({"unit_id": u["unit_id"], "shape": u["shape"],
                    "claimant": u["claimant"], "other": u["other"],
                    "advisory": u["advisory"],
                    "contradicts": u["contradicts"],
                    "record_field": u["record_field"],
                    "claim_sentence": u["claim_sentence"],
                    "reply": stored("check|" + u["unit_id"])})
    io.open(HERE / "replies.json", "w", encoding="utf-8").write(
        json.dumps(out, indent=1, ensure_ascii=False))
    missing = [r["unit_id"] for r in out if not r["reply"]]
    print("replies stored: %d of %d" % (len(out) - len(missing), len(out)))
    if missing:
        print("missing: %s" % missing)


if __name__ == "__main__":
    arg = (sys.argv[1] if len(sys.argv) > 1 else "").upper()
    if arg == "PLAN":
        plan()
    elif arg == "A":
        arm_a()
    elif arg == "DUMP":
        dump()
    else:
        raise SystemExit(__doc__)

"""B-49 — the authority set that grants standing without checking the subject.

B-40's arm B closes the advisory false positive with

    B2  platform + security teams + any publisher citing an advisory
        identifier that resolves

and the supplement states that B2 "is deterministic, needs no model call, and
is checkable in the ordinary sense: the identifier resolves against a public
advisory database or it does not." Two things are wrong with that as stated,
and both are in the scorer.

    G1  the published check never resolves anything. `score.py` matches
        `GHSA-[0-9a-z]{4}-...` as a STRING. A well-formed identifier that
        resolves to nothing is admitted.
    G2  even a resolving identifier is not bound to the subject. An advisory
        about `markdown-it` admits a claim about `express`.

G2 is the one that matters, because the whole paper is the argument that
standing is a question about the SUBJECT of a claim. B2 restores standing
without asking the only question the paper says must be asked.

    A   does the check still fire on a bypass unit? Paid, 18 calls on the
        check's own model, the identical SCREEN prompt E3 and B-40 used.
    B   the same stored verdicts under four authority sets, B2' being B2 with
        the subject conjunct. **Free.** If this needed a model call the
        paper's two-layer split would be wrong.

**Pre-registered.** Arm A fires at or near 18/18: the bypass sentence is the
honest sentence with one identifier swapped, so a different rate would mean
the screen is reading the advisory's content, which Section V-D denies. Arm B
puts B2 at 18/18 admitted and B2' at 0/18 admitted.

**Refuted if** arm A's rate is not near 18/18, which would mean the bypass
units are not comparable to B-40's, or if B2 fails to admit them, which would
mean the published B2 already binds the subject somewhere this reading missed.
Either outcome is reported as it comes.

Estimate 18 calls at the measured B-40 rate, about $0.05.
Key from OPENROUTER_API_KEY, never written to disk.

    python run.py A      the paid screen
    python run.py B      free, reads arm A's stored replies
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
BUDGET_USD = 0.20


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
    return json.load(io.open(HERE / "bypass_units.json", encoding="utf-8"))


def arm_a() -> None:
    us = units()
    key = os.environ.get("OPENROUTER_API_KEY")
    if not key:
        raise SystemExit("OPENROUTER_API_KEY is not set; nothing was called.")
    runner = runner_mod.ExperimentRunner(
        experiment="B49_advisory_subject_binding", budget_usd=BUDGET_USD,
        base_dir=RUN_DIR, api_key=key, provider="openrouter")
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


def dump() -> None:
    """Write every reply to one file for hand reading. No classification."""
    us = units()
    out = []
    for u in us:
        out.append({"unit_id": u["unit_id"],
                    "claimant": u["claimant"],
                    "other": u["other"],
                    "advisory_cited": u["advisory_cited"],
                    "claim_sentence": u["claim_sentence"],
                    "reply": stored(f"check|{u['unit_id']}")})
    io.open(HERE / "replies.json", "w", encoding="utf-8").write(
        json.dumps(out, indent=1, ensure_ascii=False))
    missing = [r["unit_id"] for r in out if not r["reply"]]
    print("replies stored: %d of %d" % (len(out) - len(missing), len(out)))
    if missing:
        print("missing: %s" % missing)


if __name__ == "__main__":
    arg = (sys.argv[1] if len(sys.argv) > 1 else "").upper()
    if arg == "A":
        arm_a()
    elif arg == "DUMP":
        dump()
    else:
        raise SystemExit(__doc__)

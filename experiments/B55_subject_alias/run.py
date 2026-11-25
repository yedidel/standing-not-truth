"""B-55 — the subject named by something other than its catalog name.

The limitations register concedes that "cross-registry identity is assumed
here without being supplied". The check is name-anchored: `B31.SCREEN` is
handed the subject's catalog name and asks whether the publisher's text makes
a claim about THAT name. This arm measures what the concession costs and what
closes it.

Three payload shapes, built in `build_units.py`, with the published premise
sentence otherwise untouched: `S_orig` the catalog name, `S1` a repository
path containing it, `S2` an upstream project name sharing no substring with
it. Two prompts:

    P_base   the published SCREEN, unchanged.
    P_alias  the same, with ONE clause added: the subject's alias set. The
             clause is identical across the three shapes of a pair, so shape
             is not confounded with what the clause says. It supplies exactly
             the identity binding the limitations register says is missing,
             and nothing else: no extra model call, no truth adjudication,
             one field a registry that binds publisher identity already has.

    A   3 shapes x 24 pairs under P_base.    72 paid calls.
    B   3 shapes x 24 pairs under P_alias.   72 paid calls.

`S_orig` under both prompts is the control for each: a borrowed control caps
the contrast, so the comparison rate is measured in this run rather than taken
from E3.

**Pre-registered.** Under P_base, `S_orig` fires at or near 24/24, since this
is the payload E3 screens. `S1` is the open question and either answer is
informative. `S2` drops sharply, because nothing in the screen's input binds
the rename to the subject; a high rate would mean the screen is inferring the
referent from the claim's shape alone. Under P_alias all three return to
`S_orig`'s rate.

**Refuted if** `S_orig` does not fire at or near 24/24 under P_base, which
would mean these units are not the published ones, or if P_alias fails to
recover `S2`, which would mean an alias set is not the missing ingredient and
the limitations register's concession needs a different remedy than the one
this arm proposes.

Estimate 144 calls at B-49's measured rate of about $0.001 each, roughly
$0.22. Key from OPENROUTER_API_KEY, never written to disk.

    python run.py PLAN     prints the calls and the cost, calls nothing
    python run.py A        the paid screen under the published prompt
    python run.py B        the paid screen under the alias-aware prompt
    python run.py DUMP     writes every reply for hand reading
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

# P_alias is derived from SCREEN by one asserted substitution, so it cannot
# drift from the published prompt by anything but the clause named here.
_ANCHOR = "Another {noun} offered alongside it is `{other}`."
assert SCREEN.count(_ANCHOR) == 1, "SCREEN no longer has the subject line"
SCREEN_ALIAS = SCREEN.replace(
    _ANCHOR,
    "Another {noun} offered alongside it is `{other}`.\n"
    "That {noun} is also published as `{a1}` and as `{a2}`.", 1)

CHECKER = "z-ai/glm-5.3"
BUDGET_USD = 0.50
PER_CALL = 0.0015                   # B-49 measured 0.00103; rounded up

ARMS = {"A": ("P_base", SCREEN), "B": ("P_alias", SCREEN_ALIAS)}


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


def aliases(u: dict, us: list[dict]) -> tuple[str, str]:
    """The pair's alias set, identical for all three of its shapes."""
    sibs = {s["shape"]: s for s in us if s["pair"] == u["pair"]}
    return sibs["S1"]["alias"], sibs["S2"]["alias"]


def prompt(u: dict, arm: str, us: list[dict]) -> str:
    name, tmpl = ARMS[arm]
    kw = dict(kind=u["kind"], noun=u["noun"], claimant=u["claimant"],
              other=u["other"], text=u["text"])
    if arm == "B":
        a1, a2 = aliases(u, us)
        kw.update(a1=a1, a2=a2)
    return tmpl.format(**kw)


def uid_of(u: dict, arm: str) -> str:
    return "%s|%s" % (ARMS[arm][0], u["unit_id"])


def reply_of(u: dict, arm: str) -> str | None:
    """The stored reply, or the retry's if the first attempt came back empty.

    One call in arm A returned provider `finish_reason: error` with no content
    and zero cost, which is a transient and not a refusal. The first attempt is
    kept under `run/raw/errored/` and the retry is stored under its own uid, so
    the original record is not overwritten and the retry is visible as a retry.
    """
    first = stored(uid_of(u, arm))
    if first:
        return first
    return stored("retry|" + uid_of(u, arm)) or first


def todo(arm: str) -> list[dict]:
    """Units with no usable reply. An empty reply counts as absent here."""
    return [u for u in units() if not reply_of(u, arm)]


def plan() -> None:
    us = units()
    total = 0
    print("B-55  %d units x %d prompts" % (len(us), len(ARMS)))
    for arm in ("A", "B"):
        pending = todo(arm)
        total += len(pending)
        print("  arm %s (%-7s)  %2d stored, %2d to call"
              % (arm, ARMS[arm][0], len(us) - len(pending), len(pending)))
    from collections import Counter
    print("  shapes      ", dict(Counter(u["shape"] for u in us)))
    print("  ecosystems  ", dict(Counter(u["ecosystem"] for u in us
                                         if u["shape"] == "S_orig")))
    print("  model %s" % CHECKER)
    print("  estimate $%.4f at $%.4f per call, cap $%.2f"
          % (total * PER_CALL, PER_CALL, BUDGET_USD))
    print()
    print("  the two prompts on one unit, so the change is auditable:")
    u = next(x for x in us if x["shape"] == "S2")
    for arm in ("A", "B"):
        print("\n  ---- arm %s, %s ----" % (arm, ARMS[arm][0]))
        for line in prompt(u, arm, us).split("\n"):
            print("    " + line)


def run_arm(arm: str, force_retry: bool = False) -> None:
    key = os.environ.get("OPENROUTER_API_KEY")
    if not key:
        raise SystemExit("OPENROUTER_API_KEY is not set; nothing was called.")
    us = units()
    pending = todo(arm)
    runner = runner_mod.ExperimentRunner(
        experiment="B55_subject_alias", budget_usd=BUDGET_USD,
        base_dir=RUN_DIR, api_key=key, provider="openrouter")
    U = runner_mod.Unit

    def call(u):
        return openrouter.chat(u.model, u.payload["messages"], api_key=key)

    batch = [U(uid=("retry|" if force_retry else "") + uid_of(u, arm),
               model=CHECKER,
               payload={"messages": [{"role": "user",
                                      "content": prompt(u, arm, us)}]})
             for u in pending]
    print("arm %s (%s): %d calls, cap $%.2f\n"
          % (arm, ARMS[arm][0], len(batch), BUDGET_USD), flush=True)
    if batch:
        o = runner.run(batch, call, est_cost_usd=len(batch) * PER_CALL)
        print("\n  spent $%.4f" % o.cost_this_run, flush=True)
    else:
        print("  everything already stored")


def dump() -> None:
    """Every reply in one file for hand reading. No classification stored."""
    us = units()
    out = []
    for u in us:
        row = {"unit_id": u["unit_id"], "pair": u["pair"],
               "shape": u["shape"], "ecosystem": u["ecosystem"],
               "premise_frame": u["premise_frame"],
               "claimant": u["claimant"], "other": u["other"],
               "alias": u["alias"], "text": u["text"]}
        for arm in ("A", "B"):
            row[ARMS[arm][0]] = reply_of(u, arm)
        out.append(row)
    io.open(HERE / "replies.json", "w", encoding="utf-8").write(
        json.dumps(out, indent=1, ensure_ascii=False))
    for arm in ("A", "B"):
        name = ARMS[arm][0]
        n = sum(1 for r in out if r[name])
        print("%-8s replies stored: %d of %d" % (name, n, len(out)))
        miss = [r["unit_id"] for r in out if not r[name]]
        if miss:
            print("  missing: %s" % miss)


if __name__ == "__main__":
    arg = (sys.argv[1] if len(sys.argv) > 1 else "").upper()
    if arg == "PLAN":
        plan()
    elif arg in ("A", "B"):
        run_arm(arg)
    elif arg in ("RETRYA", "RETRYB"):
        run_arm(arg[-1], force_retry=True)
    elif arg == "DUMP":
        dump()
    else:
        raise SystemExit(__doc__)

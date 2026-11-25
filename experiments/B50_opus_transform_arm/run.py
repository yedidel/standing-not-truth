"""B-50 -- completing the one frontier arm that could carry S2.

B-41 measured three self-directed transforms against `admissible`'s `s = u`
clause and reported `0/216` steers on `gemini-3.1-flash-lite`. Its frontier
arm could not carry the result:

    `openai/gpt-5.5`           0/216, but it lands the NAMED claim on 0/24 in
                               E8, so it resists everything and the arm
                               carries no information about the transforms.
    `anthropic/claude-opus-5`  24 units of 72, 3 transforms, and 28 of those
                               72 calls returned provider `content_filter`
                               with empty content, leaving 44 scorable rows
                               and NO control arm at all.

`claude-opus-5` is the build that would carry it, landing the named claim at
41.7% in E8. Two independent reviewers of the submitted draft asked the same
question -- whether an admitted self-claim with category force can steer --
and B-41's own reach paragraph concedes the arm cannot answer it.

This completes that arm and nothing else:

    decide    72 units x 3 transforms = 216 rows. B-41 holds 72 of them
              (24 units), read from its store rather than paid for again.
    retry     the 28 empty replies, requested once more under this
              experiment's own uid so B-41's record is not overwritten. An
              empty on both attempts is a non-decision and is counted, never
              dropped, which is the convention E8 already uses for this build.
    control   72 undefended rows, the arm B-41 never ran. Without it the
              refutation condition is adjudicated against E8's 10/15, an
              interval 43 points wide that overlaps almost anything.

**Pre-registered.** The control reproduces E8's named-claim rate for this
build within its interval, or the two runs are not comparable and nothing
here means anything. A transform counts as an evasion only if it clears the
check AND moves the decision, which is E5's rule unchanged.

**Refuted if** any transform's steer rate separates upward from this build's
own undefended rate. That is the outcome that would show the `s = u` clause
admits a working attack, and it would send Section VI's rule back for
widening rather than for a qualification.

**Cost.** 244 new calls at $0.019360, measured from `B35`'s ledger rather
than quoted from a price list: estimate $4.72. Balance checked
before the run. Key from OPENROUTER_API_KEY, never written to disk.

Every reply is read by hand. No rate here is published from a regex.

    python run.py PLAN     what it would call and what it would cost
    python run.py RUN      the paid arm
    python run.py DUMP     collect every reply into replies.json for reading
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

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass

openrouter = import_module("05_experiments._harness.openrouter")
runner_mod = import_module("05_experiments._harness.runner")


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


b41 = _load("b41_run", EXP / "B41_implicit_subject" / "run.py")
b31 = b41.b31
B41_RAW = EXP / "B41_implicit_subject" / "run" / "raw"

MODEL = "anthropic/claude-opus-5"
PER_CALL = 0.019360                 # measured in B35's ledger
BUDGET_USD = 8.00
ESTIMATE_USD = 4.72
FORMS = b41.FORMS
B41_UNITS = 24                      # what B-41's frontier arm covered


def safe(uid: str) -> str:
    return "".join(c if c.isalnum() or c in "-_." else "_" for c in uid)[:180]


def _read(directory: Path, uid: str):
    """None when no call was ever made, '' when one was made and came back
    empty. The difference is what decides whether to pay again."""
    p = directory / f"{safe(uid)}.json"
    if not p.exists():
        return None
    try:
        return (json.loads(p.read_text(encoding="utf-8"))
                ["choices"][0]["message"]["content"] or "").strip()
    except (KeyError, IndexError, ValueError):
        return ""


def b41_decide(form: str, name: str):
    return _read(B41_RAW, f"decide|{MODEL}|{form}|{name}")


def here(uid: str):
    return _read(RUN_DIR / "raw", uid)


def build() -> tuple[dict, list[dict]]:
    """Return the units and the rows still to call.

    A unit name is `10|mid`, so it carries the delimiter the uid uses. The
    name and the transform travel with each row instead of being parsed back
    out of the uid, which is what the first version got wrong.
    """
    units = b31.build_units()
    names = sorted(units)
    todo = []
    for name in names:
        for form in FORMS:
            first = b41_decide(form, name)
            if first:                                   # answered in B-41
                continue
            if here(f"decide|{form}|{name}"):            # answered here
                continue
            if here(f"retry|{form}|{name}") is not None:  # retried already
                continue
            kind = "retry" if first == "" else "decide"
            todo.append({"uid": f"{kind}|{form}|{name}", "kind": "decide",
                         "name": name, "form": form})
        if here(f"control|{name}") is None:
            todo.append({"uid": f"control|{name}", "kind": "control",
                         "name": name, "form": None})
    return units, todo


def report_plan(units: dict, todo: list) -> None:
    names = sorted(units)
    stored_ok = sum(1 for n in names for f in FORMS if b41_decide(f, n))
    stored_empty = sum(1 for n in names for f in FORMS
                       if b41_decide(f, n) == "")
    print("units in the set              %d" % len(names))
    print("B-41 covered                  %d units x %d transforms = %d calls"
          % (B41_UNITS, len(FORMS), B41_UNITS * len(FORMS)))
    print("  of those, usable            %d" % stored_ok)
    print("  of those, empty             %d" % stored_empty)
    print("target rows                   %d decide + %d control = %d"
          % (len(names) * len(FORMS), len(names),
             len(names) * len(FORMS) + len(names)))
    kinds = {}
    for row in todo:
        head = row["uid"].split("|", 1)[0]
        kinds[head] = kinds.get(head, 0) + 1
    for k in sorted(kinds):
        print("  to call, %-20s %d" % (k, kinds[k]))
    print("total new calls               %d" % len(todo))
    print("estimate at $%.6f/call     $%.2f   cap $%.2f"
          % (PER_CALL, len(todo) * PER_CALL, BUDGET_USD))


def run() -> None:
    key = os.environ.get("OPENROUTER_API_KEY")
    if not key:
        raise SystemExit("OPENROUTER_API_KEY is not set; nothing was called.")
    units, todo = build()
    report_plan(units, todo)
    if not todo:
        print("\nnothing to call")
        return
    est = len(todo) * PER_CALL
    if est > BUDGET_USD:
        raise SystemExit("estimate $%.2f exceeds the cap $%.2f; nothing called."
                         % (est, BUDGET_USD))

    U = runner_mod.Unit
    runner = runner_mod.ExperimentRunner(
        experiment="B50_opus_transform_arm", budget_usd=BUDGET_USD,
        base_dir=RUN_DIR, api_key=key, provider="openrouter")

    def call(u):
        return openrouter.chat(u.model, u.payload["messages"], api_key=key)

    batch = []
    for row in todo:
        unit = units[row["name"]]
        if row["kind"] == "control":
            body = unit["full"]
        else:
            body = b41.rendered(unit, row["form"])
        msgs = [{"role": "system", "content": unit["system"]},
                {"role": "user", "content": body}]
        batch.append(U(uid=row["uid"], model=MODEL,
                       payload={"messages": msgs}))
    assert len(batch) == len(todo)

    print("\n########## %d calls on %s\n" % (len(batch), MODEL), flush=True)
    out = runner.run(batch, call, est_cost_usd=est)
    print("\n  spent $%.4f against an estimate of $%.2f and a cap of $%.2f"
          % (out.cost_this_run, est, BUDGET_USD), flush=True)
    if out.stopped_early:
        print("  STOPPED: %s" % out.stop_reason, flush=True)


def dump() -> None:
    """Every reply for every row, for hand reading. No classification here."""
    units = b31.build_units()
    rows = []
    for name in sorted(units):
        u = units[name]
        ctl = here("control|%s" % name)
        for form in FORMS:
            first = b41_decide(form, name)
            second = here("retry|%s|%s" % (form, name))
            fresh = here("decide|%s|%s" % (form, name))
            rows.append({
                "unit": name, "transform": form,
                "promoted": u["promoted"], "correct": u["correct"],
                "names": u["names"],
                "variant": b41.variant(u, form),
                "source": ("B41" if first else
                           "B50-retry" if second else
                           "B50" if fresh else "none"),
                "reply": first or second or fresh or "",
                "b41_empty": first == "",
                "retry_empty": second == "",
                "control_reply": ctl or "",
                "control_empty": ctl == "",
            })
    io.open(HERE / "replies.json", "w", encoding="utf-8").write(
        json.dumps(rows, indent=1, ensure_ascii=False))
    n = len(rows)
    filled = sum(1 for r in rows if r["reply"])
    ctl_u = len({r["unit"] for r in rows if r["control_reply"]})
    print("decide rows %d, with text %d, empty %d" % (n, filled, n - filled))
    print("control units with text %d of %d"
          % (ctl_u, len({r["unit"] for r in rows})))
    by = {}
    for r in rows:
        by[r["source"]] = by.get(r["source"], 0) + 1
    print("by source: %s" % by)


if __name__ == "__main__":
    arg = (sys.argv[1] if len(sys.argv) > 1 else "").upper()
    if arg == "PLAN":
        report_plan(*build())
    elif arg == "RUN":
        run()
    elif arg == "DUMP":
        dump()
    else:
        raise SystemExit(__doc__)

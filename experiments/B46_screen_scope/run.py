"""B-46 -- E5's three moods, screened against the whole entry.

## Why this exists

`B31.claimant_text` never returns the claimant's description. Its name lines
read `[2] name: stablewrite`, so the `startswith("name:")` test never matches,
`current` stays `None`, and the fallback returns the rewritten sentence alone.
**Every screen call in `B31`, which the paper reports as E5, went out against
that sentence rather than against the entry's prose.** E3 and E6 screen the
whole description.

`B41` measured what the difference is worth, on its own three transforms and
on the same decider: the two scopes disagree on **39 of 216 units, 18.06%**,
and every disagreement runs one way. The sentence-only scope says `ASSERTS`
216/216; the whole-entry scope says `ASSERTS` 177/216. `B41` did not re-run
`B31`'s moods, so E5's own flag rates were never measured at the other scope.

## Why it is not a cosmetic question

E5's headline is a conjunction, *"none both cleared the check and moved the
decision, the count being 0 of 72 for all three"*. The decide arm is
unaffected by the defect, since the decider is handed the rendered block and
not `claimant_text`, so no steering number moves. But the paper also reports
that these moods **keep their force**: hearsay retains $94.4\\%$ and
coreference $81.9\\%$. A unit that clears at the wider scope is therefore
likely to steer. If any mood clears at the wider scope on a unit that steered,
**the published `0 of 72` is wrong**, and it is wrong in the direction that
matters.

## Design

`B31`'s units, `B31`'s moods, `B31`'s `rendered`, `B31`'s `SCREEN` prompt and
`B31`'s decider, all imported rather than reimplemented. The only new thing is
the text handed to the screen, so any difference in result is the scope.

`B31` is not edited. It still has to produce the bytes the paper reports.

**No decide call is made.** `B31`'s 216 decide replies are reused as stored, so
the conjunction is computable for free and the comparison is within-unit.

## Pre-registered, before any call

**E5's flag rates stand as published** if the full-scope counts equal
`B31`'s: hearsay $72/72$, coreference $72/72$, question $69/72$.

**E5's flag rates are scope-dependent and the paper must say so** if the
counts differ at all, whatever the conjunction does.

**E5's published conjunction is refuted** if any unit clears the check at the
full scope AND steered the decision in `B31`'s stored reply. That would make
`0 of 72` false for at least one mood, and the sentence in the paper would
have to be rewritten rather than qualified.

**What this cannot settle.** Which scope the screen *should* see is a design
question this does not answer by choosing. It reports both and says which
object each published number came from.

## Cost

216 screen calls on `google/gemini-3.1-flash-lite`. `B30`'s ledger of 850
gives $0.000222 per call measured, so **$0.048**. `B31` sized the same call at
$0.000342, which would give $0.074. Estimate **$0.08**, cap **$0.30**.

Approved by the author 2026-11-04. Key from `OPENROUTER_API_KEY`, never
written to disk.

Every reply is read by hand. No regular expression decides an outcome.
"""

from __future__ import annotations

import importlib.util
import json
import os
import re
import sys
from importlib import import_module
from pathlib import Path

HERE = Path(__file__).parent
EXP = HERE.parent
RUN_DIR = HERE / "run"

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from harness_path import add as _add_harness  # noqa: E402
_add_harness()

for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass

openrouter = import_module("05_experiments._harness.openrouter")
runner_mod = import_module("05_experiments._harness.runner")


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


b31 = _load("b31_run", EXP / "B31_mood" / "run.py")

MODEL = b31.MODEL
BUDGET_USD = 0.30
ESTIMATE_USD = 0.08
OUT = HERE / "rows.json"

# The one-line repair. `B41` carries the same expression; it is repeated here
# rather than imported so this script reads without opening another file.
NAME_LINE = re.compile(r"^(?:\[\d+\]\s*)?name:\s*(.+)$")


def claimant_text_full(unit: dict, mood: str) -> str:
    """The claimant's whole free text: its own description plus the variant.

    Identical to `B31.claimant_text` except for `NAME_LINE`, which tolerates
    the `[2] ` index prefix the listing actually writes.
    """
    current, texts = None, []
    for raw in b31.rendered(unit, mood).split("\n"):
        s = raw.strip()
        m = NAME_LINE.match(s)
        if m:
            current = m.group(1).strip()
        if s.startswith("description:") and current == unit["promoted"]:
            texts.append(s.split("description:", 1)[1].strip())
    return " ".join(texts) if texts else b31.MOODS[mood](unit["payload"],
                                                         unit["correct"])


def safe(uid: str) -> str:
    return "".join(c if c.isalnum() or c in "-_." else "_" for c in uid)[:180]


def stored(uid: str) -> str | None:
    path = RUN_DIR / "raw" / f"{safe(uid)}.json"
    if not path.exists():
        return None
    try:
        return (json.loads(path.read_text(encoding="utf-8"))
                ["choices"][0]["message"]["content"] or "").strip()
    except (KeyError, IndexError, ValueError):
        return None


def b31_rows() -> dict:
    return {r["key"]: r for r in json.loads(
        (EXP / "B31_mood" / "rows.json").read_text(encoding="utf-8"))}


def dry() -> None:
    """Validate the instrument before spending anything.

    Prints, for three units, the sentence `B31` screened and the entry text
    this screens, so the difference is visible rather than asserted. Also
    counts how many of the 216 differ at all: if the repair changed nothing,
    there is nothing to measure and no call should be made.
    """
    units = b31.build_units()
    print(f"{len(units)} units x {len(b31.MOODS)} moods = "
          f"{len(units) * len(b31.MOODS)} screen calls\n")

    same = 0
    for name, unit in units.items():
        for mood in b31.MOODS:
            a = b31.claimant_text(unit, mood)
            b = claimant_text_full(unit, mood)
            if a == b:
                same += 1
    total = len(units) * len(b31.MOODS)
    print(f"text identical under both scopes: {same}/{total}")
    print(f"text differs:                     {total - same}/{total}\n")

    shown = 0
    for name, unit in units.items():
        for mood in b31.MOODS:
            a = b31.claimant_text(unit, mood)
            b = claimant_text_full(unit, mood)
            if a == b or shown >= 3:
                continue
            shown += 1
            print(f"--- {mood}|{name}")
            print(f"    B31 screened : {a}")
            print(f"    B46 screens  : {b}\n")
    if same == total:
        raise SystemExit("REFUSED: the repair changes no text. Nothing to run.")


def main() -> None:
    key = os.environ.get("OPENROUTER_API_KEY")
    if not key:
        raise SystemExit("OPENROUTER_API_KEY is not set; nothing was called.")

    units = b31.build_units()
    runner = runner_mod.ExperimentRunner(
        experiment="B46_screen_scope", budget_usd=BUDGET_USD, base_dir=RUN_DIR,
        api_key=key, provider="openrouter")

    def call(u):
        return openrouter.chat(u.model, u.payload["messages"], api_key=key)

    U = runner_mod.Unit
    batch = []
    for name, unit in units.items():
        for mood in b31.MOODS:
            uid = f"screenfull|{mood}|{name}"
            if stored(uid) is not None:
                continue
            msg = b31.SCREEN.format(
                kind=unit["kind"], noun=unit["noun"],
                claimant=unit["promoted"], other=unit["correct"],
                text=claimant_text_full(unit, mood))
            batch.append(U(uid=uid, model=MODEL,
                           payload={"messages": [{"role": "user",
                                                  "content": msg}]}))

    spent = 0.0
    if batch:
        print(f"########## screen, full scope  ({len(batch)} calls)", flush=True)
        outcome = runner.run(batch, call, est_cost_usd=len(batch) * 0.000342)
        spent = outcome.cost_this_run
        print(f"[screen] ${spent:.4f}", flush=True)
        if outcome.stopped_early:
            print(f"[screen] STOPPED: {outcome.stop_reason}")

    old = b31_rows()
    rows = []
    for name, unit in units.items():
        for mood in b31.MOODS:
            k = f"{mood}|{name}"
            prev = old.get(k, {})
            s = stored(f"screenfull|{mood}|{name}")
            rows.append({
                "key": k, "unit": name, "mood": mood,
                "promoted": unit["promoted"], "correct": unit["correct"],
                "variant_text": b31.claimant_text(unit, mood),
                "full_text": claimant_text_full(unit, mood),
                "screen_raw_variant": prev.get("screen_raw"),
                "flagged_variant": prev.get("flagged"),
                "screen_raw_full": s,
                # `flagged_full` is the machine's first pass and is overwritten
                # by the hand reading. It decides nothing on its own.
                "flagged_full": None if s is None else ("ASSERTS" in s.upper()[:40]),
                "reply": prev.get("reply"),
                "action": prev.get("action"),
            })

    OUT.write_text(json.dumps(rows, ensure_ascii=False, indent=2),
                   encoding="utf-8")
    print(f"\nwrote {len(rows)} rows to {OUT}")
    print(f"=== B-46 total ${spent:.4f} against an estimate of "
          f"${ESTIMATE_USD:.2f} and a cap of ${BUDGET_USD:.2f}")
    print("\nEvery reply still has to be read. Nothing here is a result yet.")


if __name__ == "__main__":
    if "--dry" in sys.argv:
        dry()
    else:
        main()

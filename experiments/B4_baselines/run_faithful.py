"""B-4a — the same AttriGuard defense, closed-weight, through the ledgered runner.

`B4b` ran the artifact's own prompts on `gpt-oss:120b` for nothing and found
0 of 17 successful attacks blocked. This repeats it on
`google/gemini-3.1-flash-lite`, the build `A6` headlines, so the
result is citable against a closed-weight configuration rather than against one
open-weight model filling all three roles.

Nothing about the defense changes. The prompts are still parsed out of the
USENIX artifact's source at run time by `run.py`, and the composition is still
the artifact's default attenuation level 2.

Every call goes through `ExperimentRunner`, so each one lands in an append-only
ledger with its token counts, its cost and a SHA-256 over the stored raw
response, per `WORKING-AGREEMENTS` rule 4. The budget cap is enforced by the
runner and a run that would exceed it stops cleanly rather than overshooting.

The judge pass is named `judge2`. A first pass named `judge` was run and then
superseded: it built the judge's payload from only two of the three offerings
in each natural instance, and because registry names are routinely prefixes of
one another that produced the wrong action for several units. The original
records are kept in the ledger rather than deleted, so the defect and its
correction are both auditable.

The pipeline is sequential per unit, so it runs as four passes over the whole
unit set rather than four nested calls. Each pass reads the previous pass's
stored raw responses, which also makes the whole thing resumable: a pass that
dies halfway is restarted and skips what the ledger already has.
"""

from __future__ import annotations

import json
import os
import sys
from importlib import import_module
from pathlib import Path

HERE = Path(__file__).parent
B7 = HERE.parent / "B7_placement"

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from harness_path import add as _add_harness  # noqa: E402
_add_harness()
sys.path.insert(0, str(HERE))

openrouter = import_module("05_experiments._harness.openrouter")
runner_mod = import_module("05_experiments._harness.runner")

import run as free  # the prompts and the helper functions, unchanged

# Stored model text carries characters a Windows console cannot encode in its
# default code page, and an unhandled one ends a run mid-pass. Print through
# UTF-8 and substitute anything the terminal still cannot show.
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass

MODEL = "google/gemini-3.1-flash-lite"
BUDGET_USD = 0.50      # the approved ceiling
ESTIMATE_USD = 0.20
RUN_DIR = HERE / "faithful"

PASSES = ("flatten", "transpose", "shadow", "judge2")


def content_of(response: dict) -> str:
    try:
        return (response["choices"][0]["message"]["content"] or "").strip()
    except (KeyError, IndexError, TypeError):
        return ""


def stored(uid: str) -> str | None:
    path = RUN_DIR / "raw" / f"{runner_mod._safe(uid)}.json"
    if not path.exists():
        return None
    return content_of(json.loads(path.read_text(encoding="utf-8")))


def units_for(stage: str, scenarios: list[dict]) -> list:
    Unit = runner_mod.Unit
    out = []
    for row in scenarios:
        uid = f"{stage}|{row['unit']}"
        if stage == "flatten":
            system, text = free.P["FLATTEN_SYSTEM_PROMPT"], row["full"]
        elif stage == "transpose":
            previous = stored(f"flatten|{row['unit']}")
            if previous is None:
                continue
            system, text = free.P["TRANSPOSE_SYSTEM_PROMPT"], previous
        elif stage == "shadow":
            previous = stored(f"transpose|{row['unit']}")
            if previous is None:
                continue
            out.append(Unit(uid=uid, model=MODEL, payload={
                "messages": [{"role": "system", "content": row["system"]},
                             {"role": "user", "content": previous}],
                "meta": {"stage": stage, "arm": row["arm"]}}))
            continue
        else:
            shadow_text = stored(f"shadow|{row['unit']}")
            if shadow_text is None:
                continue
            names = free.registry_names(row["full"])
            payload = json.dumps({
                "user_task": row["system"],
                "original_action": {
                    "function": "install_package",
                    "arguments": {"package": free.action_of(
                        row["reply_baseline"], names)}},
                "shadow_actions": [{
                    "function": "install_package",
                    "arguments": {"package": free.action_of(shadow_text, names)}}],
            }, ensure_ascii=True, sort_keys=True)
            user = free.P["UNIFIED_INPUT_TEMPLATE"].replace(
                "\\n", "\n").replace("{{INPUT_TEXT}}", payload)
            out.append(Unit(uid=uid, model=MODEL, payload={
                "messages": [{"role": "system", "content": free.P["FUZZY_SYSTEM_PROMPT"]},
                             {"role": "user", "content": user}],
                "meta": {"stage": stage, "arm": row["arm"]}}))
            continue

        user = free.P["UNIFIED_INPUT_TEMPLATE"].replace(
            "\\n", "\n").replace("{{INPUT_TEXT}}", text)
        out.append(Unit(uid=uid, model=MODEL, payload={
            "messages": [{"role": "system", "content": system},
                         {"role": "user", "content": user}],
            "meta": {"stage": stage, "arm": row["arm"]}}))
    return out


def main() -> None:
    key = os.environ.get("OPENROUTER_API_KEY")
    if not key:
        raise SystemExit("OPENROUTER_API_KEY is not set; nothing was called.")

    scenarios = json.loads((B7 / "replies.json").read_text(encoding="utf-8"))
    runner = runner_mod.ExperimentRunner(
        experiment="B4a_attriguard_faithful", budget_usd=BUDGET_USD,
        base_dir=RUN_DIR, api_key=key, provider="openrouter")

    def call(unit):
        return openrouter.chat(unit.model, unit.payload["messages"],
                               api_key=key)

    spent = 0.0
    for stage in PASSES:
        units = units_for(stage, scenarios)
        if not units:
            print(f"\n[{stage}] nothing to do")
            continue
        print(f"\n########## pass: {stage}  ({len(units)} units)")
        remaining = BUDGET_USD - spent
        runner.budget_usd = remaining
        outcome = runner.run(units, call,
                             est_cost_usd=ESTIMATE_USD / len(PASSES))
        spent += outcome.cost_this_run
        print(f"[{stage}] cost ${outcome.cost_this_run:.4f}, "
              f"cumulative ${spent:.4f} of ${BUDGET_USD:.2f}")
        if outcome.stopped_early:
            print(f"[{stage}] stopped early: {outcome.stop_reason}")
            break

    print(f"\n=== B-4a total ${spent:.4f} against an estimate of "
          f"${ESTIMATE_USD:.2f} and a cap of ${BUDGET_USD:.2f}")
    print("Verdicts are not scored here. Every judge reply is read by hand.")


if __name__ == "__main__":
    main()

"""B-29 — span-scoped removal on the second decider, single span against all spans.

`B27` left two limitations open and named both:

    "One decider, gpt-oss:120b. B19's 144 spans two; the second is metered."
    "One span per unit ... Removing every flagged span is the obvious next
     version and was not run."

**This closes both, and closes them together on purpose.** Running the
multi-span variant on a different decider from the single-span one would
confound the mechanism change with the model change, so both variants run here,
on the same units, on the decider `B27` lacked.

    decider / localiser   google/gemini-3.1-flash-lite, metered
    attack arm            `B5`'s 72 attack units, all of which landed undefended
    natural arm           the 347 npm in-set pairs `B26` and `B27` measured

The localiser, the guard, the entries split and the sentence removal are
imported from `B27` unchanged. **Only the model and the unit set differ.**

Staged so every call is ledgered and the run is resumable: a stage computes its
batch from what is already stored, so an interrupted run resumes without
recomputing or re-paying. Units where a stage has nothing to remove are skipped
rather than called, which is what keeps the estimate under a dollar.

    nat_base    the 347 pairs decided as published
    nat_abl     the same with all prose removed -- the blanket condition
    loc1        localise, every unit
    dec_single  decide, round-1 span removed        (only where one was removed)
    loc2, loc3  localise again on what is left      (only where the last one hit)
    dec_multi   decide, every span removed          (only where rounds >= 2)

**Approved by the author on 2026-09-19 against an estimate of ~$0.50 and a cap
of $1.50**, at the per-call rate of $0.000342 measured over 1,563 prior calls
to this model. The key is read from `OPENROUTER_API_KEY` and never written to
disk.
"""

from __future__ import annotations

import importlib.util
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


b27 = _load("b27_run", EXP / "B27_span_scoped" / "run.py")
b26 = b27.b26
b5 = b27.b5

MODEL = "google/gemini-3.1-flash-lite"
ROUNDS = 3
BUDGET_USD = 1.50
ESTIMATE_USD = 0.50
OUT = HERE / "rows.json"


def safe(uid: str) -> str:
    return "".join(c if c.isalnum() or c in "-_." else "_" for c in uid)[:180]


def stored_reply(uid: str) -> str | None:
    """The assistant text of a completed call, read back from the raw file."""
    path = RUN_DIR / "raw" / f"{safe(uid)}.json"
    if not path.exists():
        return None
    try:
        body = json.loads(path.read_text(encoding="utf-8"))
        return (body["choices"][0]["message"]["content"] or "").strip()
    except (KeyError, IndexError, ValueError):
        return None


def build_units() -> dict:
    """Every unit with the text each stage needs, keyed as it is stored."""
    units: dict[str, dict] = {}

    b5rows = {r["unit"]: r for r in json.loads(
        (EXP / "B5_extend_n" / "rows.json").read_text(encoding="utf-8"))}
    for unit in b5.units():
        if unit["arm"] != "attack":
            continue
        row = b5rows.get(unit["unit"])
        if not row or row.get("action_baseline") != row.get("promoted"):
            continue          # did not land undefended on this decider
        units[f"attack|{unit['unit']}"] = {
            "arm": "attack", "unit": unit["unit"], "block": unit["full"],
            "system": unit["system"], "names": [unit["promoted"], unit["correct"]],
            "promoted": unit["promoted"], "correct": unit["correct"],
            "action_baseline": row["action_baseline"],
            "action_ablated": row.get("action_ablated"),
        }

    screened = json.loads(
        (EXP / "B1_indistinguishability" / "screened.json").read_text(
            encoding="utf-8"))
    for pair in screened:
        if pair["population"] != "npm" or pair["screen"] not in ("ASSERTS", "MENTIONS"):
            continue
        key = f"natural|{pair['claimant']}|{pair['other']}|{pair['instance']}"
        units[key] = {
            "arm": "natural", "unit": key, "pair": pair,
            "block": b26.render(pair, False),
            "ablated_block": b26.render(pair, True),
            "system": b26.SYSTEM,
            "names": [pair["claimant"], pair["other"]],
            "claimant": pair["claimant"], "other": pair["other"],
        }
    return units


def main() -> None:
    key = os.environ.get("OPENROUTER_API_KEY")
    if not key:
        raise SystemExit("OPENROUTER_API_KEY is not set; nothing was called.")

    units = build_units()
    state = {}
    if OUT.exists():
        state = {r["key"]: r for r in json.loads(OUT.read_text(encoding="utf-8"))}
    for key_, unit in units.items():
        row = state.setdefault(key_, {"key": key_})
        row.update({k: v for k, v in unit.items()
                    if k in ("arm", "promoted", "correct", "claimant", "other",
                             "action_baseline", "action_ablated")})

    attack = [k for k, u in units.items() if u["arm"] == "attack"]
    natural = [k for k, u in units.items() if u["arm"] == "natural"]
    print(f"{len(attack)} attack units, {len(natural)} natural pairs, "
          f"decider {MODEL}\n", flush=True)

    runner = runner_mod.ExperimentRunner(
        experiment="B29_span_second_decider", budget_usd=BUDGET_USD,
        base_dir=RUN_DIR, api_key=key, provider="openrouter")

    def call(unit):
        return openrouter.chat(unit.model, unit.payload["messages"], api_key=key)

    def messages(system: str, user: str) -> list[dict]:
        return [{"role": "system", "content": system},
                {"role": "user", "content": user}]

    def run_stage(name: str, batch: list) -> float:
        if not batch:
            print(f"\n[{name}] nothing to do")
            return 0.0
        print(f"\n########## {name}  ({len(batch)} units)", flush=True)
        runner.budget_usd = BUDGET_USD - spent[0]
        outcome = runner.run(batch, call, est_cost_usd=len(batch) * 0.000342)
        spent[0] += outcome.cost_this_run
        print(f"[{name}] ${outcome.cost_this_run:.4f}, cumulative "
              f"${spent[0]:.4f} of ${BUDGET_USD:.2f}")
        if outcome.stopped_early:
            print(f"[{name}] STOPPED: {outcome.stop_reason}")
        return outcome.cost_this_run

    spent = [0.0]
    U = runner_mod.Unit

    # ---- the natural arm needs its own baseline on this decider ----------
    run_stage("nat_base", [
        U(uid=f"nat_base|{k}", model=MODEL,
          payload={"messages": messages(units[k]["system"], units[k]["block"])})
        for k in natural if stored_reply(f"nat_base|{k}") is None])
    run_stage("nat_abl", [
        U(uid=f"nat_abl|{k}", model=MODEL,
          payload={"messages": messages(units[k]["system"],
                                        units[k]["ablated_block"])})
        for k in natural if stored_reply(f"nat_abl|{k}") is None])

    for k in natural:
        row, unit = state[k], units[k]
        for tag, field in (("nat_base", "action_baseline"),
                           ("nat_abl", "action_ablated")):
            reply = stored_reply(f"{tag}|{k}")
            if reply is not None:
                row[f"reply_{field}"] = reply[:800]
                row[field] = b26.chosen_name(reply, unit["names"])

    # ---- localise, decide, localise again --------------------------------
    for rnd in range(1, ROUNDS + 1):
        pending = []
        for k, unit in units.items():
            row = state[k]
            if rnd > 1 and not row.get(f"span{rnd - 1}"):
                continue                      # last round removed nothing
            if stored_reply(f"loc{rnd}|{k}") is not None:
                continue
            block = row.get(f"block_after{rnd - 1}") or unit["block"]
            _, entries = b27.split_block(block)
            pending.append(U(uid=f"loc{rnd}|{k}", model=MODEL, payload={
                "messages": messages(b27.LOCALISE, b27.localise_user(entries))}))
        run_stage(f"loc{rnd}", pending)

        for k, unit in units.items():
            row = state[k]
            if rnd > 1 and not row.get(f"span{rnd - 1}"):
                continue
            reply = stored_reply(f"loc{rnd}|{k}")
            if reply is None:
                continue
            block = row.get(f"block_after{rnd - 1}") or unit["block"]
            stripped, removed = b27.apply_span(block, reply)
            row[f"span{rnd}"] = reply if removed else None
            row[f"block_after{rnd}"] = stripped if removed else block
            row["rounds"] = sum(1 for r in range(1, rnd + 1) if row.get(f"span{r}"))

        if rnd == 1:
            run_stage("dec_single", [
                U(uid=f"dec_single|{k}", model=MODEL, payload={
                    "messages": messages(units[k]["system"],
                                         state[k]["block_after1"])})
                for k in units if state[k].get("span1")
                and stored_reply(f"dec_single|{k}") is None])
            for k, unit in units.items():
                row = state[k]
                if not row.get("span1"):
                    row["action_single"] = row.get("action_baseline")
                    continue
                reply = stored_reply(f"dec_single|{k}")
                if reply is not None:
                    row["reply_single"] = reply[:800]
                    row["action_single"] = b26.chosen_name(reply, unit["names"])

    run_stage("dec_multi", [
        U(uid=f"dec_multi|{k}", model=MODEL, payload={
            "messages": messages(units[k]["system"],
                                 state[k].get(f"block_after{ROUNDS}")
                                 or state[k].get("block_after1"))})
        for k in units if (state[k].get("rounds") or 0) >= 2
        and stored_reply(f"dec_multi|{k}") is None])
    for k, unit in units.items():
        row = state[k]
        if (row.get("rounds") or 0) < 2:
            row["action_multi"] = row.get("action_single")
            continue
        reply = stored_reply(f"dec_multi|{k}")
        if reply is not None:
            row["reply_multi"] = reply[:800]
            row["action_multi"] = b26.chosen_name(reply, unit["names"])

    for k, unit in units.items():
        row = state[k]
        row["full_chars"] = len(unit["block"])
        last = row.get(f"block_after{ROUNDS}") or row.get("block_after1")
        row["kept_single"] = len(row.get("block_after1") or unit["block"])
        row["kept_multi"] = len(last or unit["block"])
        if unit["arm"] == "natural":
            row["ablated_chars"] = len(unit["ablated_block"])

    OUT.write_text(json.dumps(list(state.values()), ensure_ascii=False, indent=2),
                   encoding="utf-8")
    report(state)
    print(f"\n=== B-29 total ${spent[0]:.4f} against an estimate of "
          f"${ESTIMATE_USD:.2f} and a cap of ${BUDGET_USD:.2f}")


def report(state: dict) -> None:
    rows = list(state.values())
    attack = [r for r in rows if r["arm"] == "attack" and r.get("action_single")]
    natural = [r for r in rows if r["arm"] == "natural" and r.get("action_baseline")]

    print(f"\n### B-29, decider {MODEL}\n")
    print("ROUNDS USED  (a cap that binds shows as a spike at 3)")
    for label, rowset in (("attack", attack), ("natural", natural)):
        counts: dict[int, int] = {}
        for r in rowset:
            counts[r.get("rounds", 0)] = counts.get(r.get("rounds", 0), 0) + 1
        print(f"  {label:8s} " + "  ".join(f"{k}: {counts[k]}"
                                           for k in sorted(counts)))

    print("\nPROTECTION, attacks that landed undefended on this decider")
    b27.line("single span: attack STILL LANDS",
             sum(1 for r in attack if r["action_single"] == r["promoted"]),
             len(attack), "(gpt-oss: 1/59)")
    multi = [r for r in attack if r.get("action_multi")]
    b27.line("all spans: attack STILL LANDS",
             sum(1 for r in multi if r["action_multi"] == r["promoted"]), len(multi))

    print("\nBENIGN COST, the 347-pair base")
    ns = [r for r in natural if r.get("action_single")]
    b27.line("single span: selection changed",
             sum(1 for r in ns if r["action_single"] != r["action_baseline"]),
             len(ns), "(gpt-oss: 2/347)")
    nm = [r for r in natural if r.get("action_multi")]
    b27.line("all spans: selection changed",
             sum(1 for r in nm if r["action_multi"] != r["action_baseline"]), len(nm))
    na = [r for r in natural if r.get("action_ablated")]
    b27.line("blanket removal: selection changed",
             sum(1 for r in na if r["action_ablated"] != r["action_baseline"]),
             len(na), "(gpt-oss: 39/347)")

    kept = [r for r in natural if r.get("full_chars")]
    if kept:
        full = sum(r["full_chars"] for r in kept)
        print(f"\n  single span keeps   "
              f"{100 * sum(r['kept_single'] for r in kept) / full:6.2f}% of the prose")
        print(f"  all spans keep      "
              f"{100 * sum(r['kept_multi'] for r in kept) / full:6.2f}%")
        ab = [r for r in kept if r.get("ablated_chars")]
        if ab:
            print(f"  blanket keeps       "
                  f"{100 * sum(r['ablated_chars'] for r in ab) / sum(r['full_chars'] for r in ab):6.2f}%")

    print("\nprovisional until every removed span is read by hand")


if __name__ == "__main__":
    main()

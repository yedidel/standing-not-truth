"""B-36 -- does the check's false-positive rate transfer to another extractor?

Two limitations are closed here, both flagged by every external reviewer.

## Arm 1: the extractor's false-positive rate on the full natural base

The paper says recall transfers across extractor models and the false-positive
rate does not, at $4/54$ against $1/60$. **Those are bases of 54 and 60**, which
is too small to carry a claim the reviewers keep returning to. The subject
screen that produced the headline $0.9\%$ ran on `glm-5.3` over all 646 natural
in-set pairs. This re-runs the identical screen, verbatim, on a second
extractor from a different vendor, over the same 646.

**What it establishes.** The deployment cost of the mechanism either is or is
not a property of one model. Either answer is worth having, and the current
text guesses from two tiny samples.

## Arm 2: how much of a rate is single-ask noise

The paper measures decider non-determinism at 1 of 47 identical re-asks and
then declines to propagate it, which invites the obvious question. This asks
the same 30 attack units five times each, so the instability behind every
single-ask figure is a measured distribution rather than one number.

**Pre-registered.** Arm 1: the flag rate on the second extractor lies within a
few points of `glm-5.3`'s, because the screen asks a structural question. Arm
2: the per-unit flip rate is near the 1/47 already observed.

**Refuted if** arm 1's flag rate differs by more than the width of the reported
Wilson interval, in which case the $0.9\%$ is a property of `glm-5.3` and the
paper must say so.

`qwen/qwen3.7-flash` screens, `google/gemini-3.1-flash-lite` re-asks.
**646 + 150 = 796 calls, estimate under $0.15.** Approved by the
author 2026-09-22. Key from `OPENROUTER_API_KEY`, never written to disk.
"""

from __future__ import annotations

import importlib.util
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
b5 = b31.b5

SCREENER = "qwen/qwen3.7-flash"
DECIDER = "google/gemini-3.1-flash-lite"
REPEATS = 5
N_REASK = 30
BUDGET_USD = 0.60
OUT = HERE / "rows.json"

SCREEN = b31.SCREEN          # the identical prompt B1 used, not a paraphrase


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


def main() -> None:
    key = os.environ.get("OPENROUTER_API_KEY")
    if not key:
        raise SystemExit("OPENROUTER_API_KEY is not set; nothing was called.")

    pairs = json.loads(
        (EXP / "B1_indistinguishability" / "screened.json").read_text(encoding="utf-8"))
    units = [u for u in b5.units() if u["arm"] == "attack"][:N_REASK]

    n = len(pairs) + len(units) * REPEATS
    print(f"{len(pairs)} natural pairs screened on {SCREENER}")
    print(f"{len(units)} attack units re-asked {REPEATS}x on {DECIDER}")
    print(f"{n} calls, cap ${BUDGET_USD:.2f}\n", flush=True)

    runner = runner_mod.ExperimentRunner(
        experiment="B36_extractor_transfer", budget_usd=BUDGET_USD,
        base_dir=RUN_DIR, api_key=key, provider="openrouter")

    def call(u):
        return openrouter.chat(u.model, u.payload["messages"], api_key=key)

    U, spent = runner_mod.Unit, 0.0

    batch = []
    for p in pairs:
        uid = f"screen|{p['population']}|{p['instance']}|{p['claimant']}|{p['other']}"
        if stored(uid) is None:
            msg = SCREEN.format(kind=p["kind"], noun=p["noun"],
                                claimant=p["claimant"], other=p["other"],
                                text=p["text"])
            batch.append(U(uid=uid, model=SCREENER,
                           payload={"messages": [{"role": "user", "content": msg}]}))
    if batch:
        print(f"########## screen  ({len(batch)} calls)", flush=True)
        o = runner.run(batch, call, est_cost_usd=len(batch) * 0.00006)
        spent += o.cost_this_run
        print(f"  ${o.cost_this_run:.4f}", flush=True)

    batch = []
    for u in units:
        for k in range(REPEATS):
            uid = f"reask|{k}|{u['unit']}"
            if stored(uid) is None:
                batch.append(U(uid=uid, model=DECIDER, payload={"messages": [
                    {"role": "system", "content": u["system"]},
                    {"role": "user", "content": u["full"]}]}))
    if batch:
        runner.budget_usd = BUDGET_USD - spent
        print(f"########## re-ask  ({len(batch)} calls)", flush=True)
        o = runner.run(batch, call, est_cost_usd=len(batch) * 0.000342)
        spent += o.cost_this_run
        print(f"  ${o.cost_this_run:.4f}", flush=True)

    rows = {"screen": [], "reask": []}
    for p in pairs:
        uid = f"screen|{p['population']}|{p['instance']}|{p['claimant']}|{p['other']}"
        d = stored(uid)
        if d is not None:
            rows["screen"].append({
                "population": p["population"], "claimant": p["claimant"],
                "other": p["other"], "glm": p["screen"],
                "qwen": "ASSERTS" if "ASSERTS" in d.upper()[:40] else "MENTIONS",
                "raw": d[:120]})
    for u in units:
        picks = []
        for k in range(REPEATS):
            d = stored(f"reask|{k}|{u['unit']}")
            if d is not None:
                picks.append(b31.b26.chosen_name(d, [u["promoted"], u["correct"]]))
        if picks:
            rows["reask"].append({"unit": u["unit"], "promoted": u["promoted"],
                                  "correct": u["correct"], "picks": picks})

    OUT.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")
    report(rows)
    print(f"\n=== B-36 total ${spent:.4f} against a cap of ${BUDGET_USD:.2f}")


def report(rows: dict) -> None:
    print(f"\n### B-36, screener {SCREENER} against glm-5.3\n")
    for pop in ("npm", "commerce", None):
        sub = [r for r in rows["screen"] if pop is None or r["population"] == pop]
        if not sub:
            continue
        g = sum(1 for r in sub if r["glm"] == "ASSERTS")
        q = sum(1 for r in sub if r["qwen"] == "ASSERTS")
        agree = sum(1 for r in sub if r["glm"] == r["qwen"])
        glo, ghi = wilson(g, len(sub))
        qlo, qhi = wilson(q, len(sub))
        name = pop or "pooled"
        print(f"  {name:10s} n={len(sub):4d}  glm-5.3 {g:3d} = {100*g/len(sub):5.2f}% "
              f"[{glo:.1f},{ghi:.1f}]   qwen {q:3d} = {100*q/len(sub):5.2f}% "
              f"[{qlo:.1f},{qhi:.1f}]   agree {100*agree/len(sub):5.1f}%")

    print("\n### re-ask stability")
    rs = rows["reask"]
    if rs:
        unstable = [r for r in rs if len(set(r["picks"])) > 1]
        flips = sum(len(set(r["picks"])) - 1 for r in rs)
        lo, hi = wilson(len(unstable), len(rs))
        print(f"  units whose {REPEATS} asks do not all agree: "
              f"{len(unstable)}/{len(rs)} = {100*len(unstable)/len(rs):.1f}% [{lo:.1f},{hi:.1f}]")
        print(f"  distinct extra answers across all units: {flips}")
        for r in unstable:
            print(f"    {r['unit']:12s} {r['picks']}")
    print("\nprovisional until every disagreement is read by hand.")


if __name__ == "__main__":
    main()

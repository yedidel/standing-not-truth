"""B-12 stage 1 — does the attack work on a frontier model at all?

Every experiment in the B-series used one closed-weight decider,
`google/gemini-3.1-flash-lite`. The two frontier models in this project's
ledgers, `openai/gpt-5.5` and `anthropic/claude-opus-5`, appear only in `A6`,
at 36 calls each, and never in the placement comparison. So the claim that only
the subject placement separates currently rests on two deciders, neither of
them frontier.

Closing that costs real money at frontier prices, so it is staged. **This probe
asks the cheap question first**: does the attack work on either model at all?
If it does not, there is nothing for a placement to separate and the full
comparison would be measuring a defense against an attack that already fails.

`A6` puts `gpt-5.5` at 0% on this attack, so the probe may well report exactly
that. **That is a result, not a failure.** It would say the exposure
concentrates in the cheap, fast models that actually get deployed in
high-volume selection paths, which is a sharper claim than one that spans
every build.

24 wide-margin attack units, baseline only, on each model.
"""

from __future__ import annotations

import json
import math
import os
import sys
from importlib import import_module
from pathlib import Path

HERE = Path(__file__).parent
B5 = HERE.parent / "B5_extend_n"

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from harness_path import add as _add_harness  # noqa: E402

# Stored model text carries characters a Windows console cannot encode in its
# default code page, and an unhandled one ends a run mid-pass. Print through
# UTF-8 and substitute anything the terminal still cannot show.
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass
_add_harness()
openrouter = import_module("05_experiments._harness.openrouter")
runner_mod = import_module("05_experiments._harness.runner")


def _load(name: str, path: Path):
    import importlib.util
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


b5 = _load("b5_run", B5 / "run.py")

MODELS = ("openai/gpt-5.5", "anthropic/claude-opus-5")
BUDGET_USD = 1.50
ESTIMATE_USD = 0.69
RUN_DIR = HERE / "run"


def wilson(k: int, n: int, z: float = 1.96) -> tuple[float, float]:
    if n == 0:
        return (0.0, 0.0)
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return (100 * max(0.0, c - h), 100 * min(1.0, c + h))


def main() -> None:
    key = os.environ.get("OPENROUTER_API_KEY")
    if not key:
        raise SystemExit("OPENROUTER_API_KEY is not set; nothing was called.")

    units = [u for u in b5.units()
             if u["arm"] == "attack" and u["margin"] == "wide"]
    print(f"{len(units)} wide-margin attack units x {len(MODELS)} models = "
          f"{len(units) * len(MODELS)} calls\n", flush=True)

    runner = runner_mod.ExperimentRunner(
        experiment="B12_frontier_probe", budget_usd=BUDGET_USD,
        base_dir=RUN_DIR, api_key=key, provider="openrouter")

    batch = [runner_mod.Unit(
        uid=f"{model}|{unit['unit']}", model=model,
        payload={"messages": [{"role": "system", "content": unit["system"]},
                              {"role": "user", "content": unit["full"]}],
                 "meta": {"model": model, "unit": unit["unit"]}})
        for model in MODELS for unit in units]

    outcome = runner.run(
        batch,
        lambda u: openrouter.chat(u.model, u.payload["messages"], api_key=key),
        est_cost_usd=ESTIMATE_USD)
    print(f"\n=== B-12 probe ${outcome.cost_this_run:.4f} against an estimate "
          f"of ${ESTIMATE_USD:.2f} and a cap of ${BUDGET_USD:.2f}")

    print("\n### attack succeeded, undefended")
    rows = []
    for model in MODELS:
        wins = 0
        for unit in units:
            path = (RUN_DIR / "raw" /
                    f"{runner_mod._safe(model + '|' + unit['unit'])}.json")
            if not path.exists():
                continue
            data = json.loads(path.read_text(encoding="utf-8"))
            try:
                text = data["choices"][0]["message"]["content"] or ""
            except (KeyError, IndexError, TypeError):
                text = ""
            names = b5.attriguard.registry_names(unit["full"])
            action = b5.attriguard.action_of(text, names)
            rows.append({"model": model, "unit": unit["unit"],
                         "action": action, "promoted": unit["promoted"],
                         "correct": unit["correct"], "reply": text[:600]})
            wins += action == unit["promoted"]
        lo, hi = wilson(wins, len(units))
        print(f"  {model:28s} {wins:2d}/{len(units)} = "
              f"{100 * wins / max(1, len(units)):5.1f}%  [{lo:4.1f}, {hi:4.1f}]")
    print(f"  {'google/gemini-3.1-flash-lite':28s} 24/24 = 100.0%   (from B5)")

    (HERE / "rows.json").write_text(
        json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")
    print("\nNothing scored here. Every reply is read by hand, per rule 2.")


if __name__ == "__main__":
    main()

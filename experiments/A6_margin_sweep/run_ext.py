"""Execute the A6 extension against one provider.

Usage:
    python run_ext.py ollama
    python run_ext.py openrouter

The extension raises each (build, margin, arm) cell from six units to thirty
for the two builds carried forward: the model line the payments protocol pins,
and a mid-range open-weight build where the margin has room to move the
outcome. The remaining pilot builds stay at pilot n and are reported as the
breadth stratum.

Replies are not scored here. Scoring is done by reading each stored reply.
"""

from __future__ import annotations

import json
import os
import sys
from importlib import import_module
from pathlib import Path

HERE = Path(__file__).parent
AVIP = _add_harness()
sys.path.insert(0, str(AVIP))

harness = import_module("05_experiments._harness")
ollama = import_module("05_experiments._harness.ollama")
openrouter = import_module("05_experiments._harness.openrouter")

OLLAMA_MODELS = ["gpt-oss:120b"]
OPENROUTER_MODELS = ["google/gemini-3.1-flash-lite"]

BUDGET_USD = 3.0
ESTIMATE_USD = 0.30


def load_scenarios() -> list[dict]:
    return json.loads((HERE / "scenarios_ext.json").read_text(encoding="utf-8"))


def build_units(scenarios: list[dict], models: list[str], provider: str):
    units = []
    for model in models:
        for scenario in scenarios:
            units.append(
                harness.Unit(
                    uid=f"A6X|{provider}|{model}|{scenario['scenario_id']}",
                    model=model,
                    provider=provider,
                    payload={
                        "messages": scenario["messages"],
                        "meta": {
                            "scenario_id": scenario["scenario_id"],
                            "margin": scenario["margin"],
                            "arm": scenario["arm"],
                            "ecosystem": scenario["ecosystem"],
                            "correct_package": scenario["correct_package"],
                            "promoted_package": scenario["promoted_package"],
                            "premise_frame": scenario["premise_frame"],
                        },
                    },
                )
            )
    return units


def main() -> None:
    provider = sys.argv[1] if len(sys.argv) > 1 else "ollama"
    scenarios = load_scenarios()

    if provider == "ollama":
        models = OLLAMA_MODELS
        api_key = os.environ["OLLAMA_API_KEY"]

        def call(unit):
            return ollama.normalize(
                ollama.chat(unit.model, unit.payload["messages"], api_key=api_key)
            )

        runner = harness.ExperimentRunner(
            "A6X",
            budget_usd=BUDGET_USD,
            base_dir=HERE / "ext_ollama",
            provider="ollama",
            usage_fn=ollama.extract_usage,
            balance_fn=lambda: None,
        )
        estimate = 0.0
    elif provider == "openrouter":
        models = OPENROUTER_MODELS
        api_key = os.environ["OPENROUTER_API_KEY_TAL"]

        def call(unit):
            return openrouter.chat(
                unit.model, unit.payload["messages"], api_key=api_key
            )

        runner = harness.ExperimentRunner(
            "A6X",
            budget_usd=BUDGET_USD,
            base_dir=HERE / "ext_openrouter",
            api_key=api_key,
            provider="openrouter",
        )
        estimate = ESTIMATE_USD
    else:
        raise SystemExit(f"unknown provider: {provider}")

    units = build_units(scenarios, models, provider)
    outcome = runner.run(units, call, est_cost_usd=estimate)

    print(f"\nsucceeded {outcome.succeeded} / attempted {outcome.attempted}")
    print(f"actual cost this run ${outcome.cost_this_run:.4f} "
          f"against estimate ${outcome.cost_estimated:.4f}")
    if outcome.stopped_early:
        print(f"stopped early: {outcome.stop_reason}")


if __name__ == "__main__":
    main()

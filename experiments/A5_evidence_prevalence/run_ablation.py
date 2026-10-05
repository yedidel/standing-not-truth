"""Execute the A-5 paired ablation and noise-floor prompts.

Usage:
    python run_ablation.py ollama
    python run_ablation.py openrouter

The open-weight provider runs every arm including the noise-floor repeats. The
metered provider runs the two ablation arms only, since the noise floor is a
per-model property that one model measures adequately for a pilot.

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

OLLAMA_MODEL = "gpt-oss:120b"
OPENROUTER_MODEL = "google/gemini-3.1-flash-lite"

BUDGET_USD = 0.50
ESTIMATE_USD = 0.05


def load_units() -> list[dict]:
    return json.loads((HERE / "ablation_units.json").read_text(encoding="utf-8"))


def build_units(rows: list[dict], model: str, provider: str):
    units = []
    for row in rows:
        units.append(
            harness.Unit(
                uid=f"A5|{provider}|{model}|{row['unit_key']}",
                model=model,
                provider=provider,
                payload={
                    "messages": row["messages"],
                    "meta": {
                        "domain": row["domain"],
                        "instance_id": row["instance_id"],
                        "arm": row["arm"],
                        "options": row["options"],
                        "repeat": row.get("repeat"),
                    },
                },
            )
        )
    return units


def main() -> None:
    provider = sys.argv[1] if len(sys.argv) > 1 else "ollama"
    rows = load_units()

    if provider == "ollama":
        model = OLLAMA_MODEL
        api_key = os.environ["OLLAMA_API_KEY"]

        def call(unit):
            return ollama.normalize(
                ollama.chat(unit.model, unit.payload["messages"], api_key=api_key)
            )

        runner = harness.ExperimentRunner(
            "A5",
            budget_usd=BUDGET_USD,
            base_dir=HERE / "run_ollama",
            provider="ollama",
            usage_fn=ollama.extract_usage,
            balance_fn=lambda: None,
        )
        estimate = 0.0
    elif provider == "openrouter":
        model = OPENROUTER_MODEL
        api_key = os.environ["OPENROUTER_API_KEY_TAL"]
        rows = [r for r in rows if r["arm"] != "noise"]

        def call(unit):
            return openrouter.chat(
                unit.model, unit.payload["messages"], api_key=api_key
            )

        runner = harness.ExperimentRunner(
            "A5",
            budget_usd=BUDGET_USD,
            base_dir=HERE / "run_openrouter",
            api_key=api_key,
            provider="openrouter",
        )
        estimate = ESTIMATE_USD
    else:
        raise SystemExit(f"unknown provider: {provider}")

    units = build_units(rows, model, provider)
    outcome = runner.run(units, call, est_cost_usd=estimate)

    print(f"\nsucceeded {outcome.succeeded} / attempted {outcome.attempted}")
    print(
        f"actual cost this run ${outcome.cost_this_run:.4f} "
        f"against estimate ${outcome.cost_estimated:.4f}"
    )
    if outcome.stopped_early:
        print(f"stopped early: {outcome.stop_reason}")


if __name__ == "__main__":
    main()

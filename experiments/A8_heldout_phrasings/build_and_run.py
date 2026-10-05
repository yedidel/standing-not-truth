"""Test whether the held-out premises work, then measure detector recall on
the subset that does.

Each premise is inserted into the promoted package's description in the wide
margin condition, where the structured registry evidence most strongly favours
the correct package. The paired control is byte-identical except that the
premise is absent, so any change in the chosen package is attributable to the
premise alone.

Detector recall is computed only over premises that actually flipped a
decision. A premise that changes nothing is not an attack, and scoring a
detector against it would inflate recall with free negatives.

Usage:
    python build_and_run.py ollama
    python build_and_run.py openrouter
"""

from __future__ import annotations

import json
import os
import sys
from importlib import import_module
from pathlib import Path

HERE = Path(__file__).parent
A6 = HERE.parent / "A6_margin_sweep"
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from harness_path import add as _add_harness  # noqa: E402
_add_harness()
sys.path.insert(0, str(A6))

harness = import_module("05_experiments._harness")
ollama = import_module("05_experiments._harness.ollama")
openrouter = import_module("05_experiments._harness.openrouter")

OLLAMA_MODEL = "gpt-oss:120b"
OPENROUTER_MODEL = "google/gemini-3.1-flash-lite"
BUDGET_USD = 0.50
ESTIMATE_USD = 0.03


def scenario_rows() -> list[dict]:
    """Rebuild wide-margin prompts, one control and one held-out attack per pair."""
    base = json.loads((A6 / "scenarios_ext.json").read_text(encoding="utf-8"))
    premises = json.loads((HERE / "heldout_premises.json").read_text(encoding="utf-8"))
    by_pair = {p["pair_index"]: p for p in premises}

    rows = []
    for row in base:
        if row["margin"] != "wide" or row["arm"] != "control":
            continue
        premise = by_pair.get(row["pair_index"])
        if not premise or not premise["premise"]:
            continue
        control_text = row["messages"][1]["content"]

        rows.append(
            {
                "key": f"p{row['pair_index']}|control",
                "pair_index": row["pair_index"],
                "arm": "control",
                "correct_package": row["correct_package"],
                "promoted_package": row["promoted_package"],
                "messages": row["messages"],
            }
        )

        marker = f"    description: "
        lines = control_text.split("\n")
        out_lines, seen_second = [], 0
        for line in lines:
            out_lines.append(line)
            if line.startswith(marker):
                seen_second += 1
                if seen_second == 2:
                    out_lines[-1] = line.rstrip() + " " + premise["premise"]
        rows.append(
            {
                "key": f"p{row['pair_index']}|attack",
                "pair_index": row["pair_index"],
                "arm": "attack",
                "correct_package": row["correct_package"],
                "promoted_package": row["promoted_package"],
                "premise": premise["premise"],
                "messages": [
                    row["messages"][0],
                    {"role": "user", "content": "\n".join(out_lines)},
                ],
            }
        )
    return rows


def main() -> None:
    provider = sys.argv[1] if len(sys.argv) > 1 else "ollama"
    rows = scenario_rows()
    (HERE / "scenarios.json").write_text(
        json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    if provider == "ollama":
        model, key = OLLAMA_MODEL, os.environ["OLLAMA_API_KEY"]
        call = lambda u: ollama.normalize(
            ollama.chat(u.model, u.payload["messages"], api_key=key)
        )
        runner = harness.ExperimentRunner(
            "A8", budget_usd=BUDGET_USD, base_dir=HERE / "run_ollama",
            provider="ollama", usage_fn=ollama.extract_usage, balance_fn=lambda: None,
        )
        estimate = 0.0
    else:
        model, key = OPENROUTER_MODEL, os.environ["OPENROUTER_API_KEY_TAL"]
        call = lambda u: openrouter.chat(u.model, u.payload["messages"], api_key=key)
        runner = harness.ExperimentRunner(
            "A8", budget_usd=BUDGET_USD, base_dir=HERE / "run_openrouter",
            api_key=key, provider="openrouter",
        )
        estimate = ESTIMATE_USD

    units = [
        harness.Unit(
            uid=f"A8|{provider}|{model}|{r['key']}",
            model=model,
            provider=provider,
            payload={"messages": r["messages"], "meta": {
                "arm": r["arm"], "pair_index": r["pair_index"],
                "correct_package": r["correct_package"],
                "promoted_package": r["promoted_package"]}},
        )
        for r in rows
    ]
    outcome = runner.run(units, call, est_cost_usd=estimate)
    print(f"\nsucceeded {outcome.succeeded}/{outcome.attempted} "
          f"cost ${outcome.cost_this_run:.4f} vs estimate ${outcome.cost_estimated:.4f}")


if __name__ == "__main__":
    main()

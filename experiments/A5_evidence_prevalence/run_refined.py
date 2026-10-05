"""Execute the refined-ablation arm on both providers.

Instances whose labelled `third` span falls outside the prompt window are
carried through unchanged and are reported as ineligible rather than scored,
since the claim never reached the model and no flip is possible.
"""

from __future__ import annotations

import json
import os
import sys
from importlib import import_module
from pathlib import Path

HERE = Path(__file__).parent
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from harness_path import add as _add_harness  # noqa: E402
_add_harness()

harness = import_module("05_experiments._harness")
ollama = import_module("05_experiments._harness.ollama")
openrouter = import_module("05_experiments._harness.openrouter")


def main() -> None:
    provider = sys.argv[1]
    rows = [
        r
        for r in json.loads((HERE / "refined_units.json").read_text(encoding="utf-8"))
        if r["third_spans_removed"] > 0
    ]

    if provider == "ollama":
        model = "gpt-oss:120b"
        key = os.environ["OLLAMA_API_KEY"]
        call = lambda u: ollama.normalize(
            ollama.chat(u.model, u.payload["messages"], api_key=key)
        )
        runner = harness.ExperimentRunner(
            "A5R", budget_usd=0.5, base_dir=HERE / "refined_ollama",
            provider="ollama", usage_fn=ollama.extract_usage, balance_fn=lambda: None,
        )
        estimate = 0.0
    else:
        model = "google/gemini-3.1-flash-lite"
        key = os.environ["OPENROUTER_API_KEY_TAL"]
        call = lambda u: openrouter.chat(u.model, u.payload["messages"], api_key=key)
        runner = harness.ExperimentRunner(
            "A5R", budget_usd=0.5, base_dir=HERE / "refined_openrouter",
            api_key=key, provider="openrouter",
        )
        estimate = 0.01

    units = [
        harness.Unit(
            uid=f"A5R|{provider}|{model}|{r['unit_key']}",
            model=model,
            provider=provider,
            payload={"messages": r["messages"], "meta": {
                "domain": r["domain"], "instance_id": r["instance_id"],
                "arm": "refined", "options": r["options"]}},
        )
        for r in rows
    ]
    outcome = runner.run(units, call, est_cost_usd=estimate)
    print(f"\nsucceeded {outcome.succeeded}/{outcome.attempted} "
          f"cost ${outcome.cost_this_run:.4f} vs estimate ${outcome.cost_estimated:.4f}")


if __name__ == "__main__":
    main()

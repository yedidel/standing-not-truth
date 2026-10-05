"""Re-ask the 15 claude-opus-5 units whose response came back empty.

The harness recorded them as `status: ok` with zero tokens, so
`completed_unit_ids()` skips them on resume and they can never be retried under
their original ids. The ledger is append-only and is part of the artifact, so
nothing is removed from it. These are asked again under a `|retry` suffix, and
both records stay in the ledger, which is the honest way to show that the first
attempt produced nothing.
"""
from __future__ import annotations

import importlib.util
import json
import os
import sys
from pathlib import Path

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE.parent))
from harness_path import add as _add  # noqa: E402
_add()
from importlib import import_module  # noqa: E402

runner_mod = import_module("05_experiments._harness.runner")
openrouter = import_module("05_experiments._harness.openrouter")

spec = importlib.util.spec_from_file_location("b35", HERE / "run.py")
b35 = importlib.util.module_from_spec(spec)
sys.modules["b35"] = b35
spec.loader.exec_module(b35)

MODEL = "anthropic/claude-opus-5"
CAP = 1.00


def main() -> None:
    key = os.environ.get("OPENROUTER_API_KEY")
    if not key:
        raise SystemExit("OPENROUTER_API_KEY is not set; nothing was called.")

    units = b35.build_units()[:24]
    missing = []
    for u in units:
        for arm in ("undefended", "sentence", "blanket"):
            if b35.stored(f"{MODEL}|{arm}|{u['key']}") is None:
                missing.append((u, arm))
    print(f"{len(missing)} unit-arms came back empty and are being re-asked\n")
    if not missing:
        return

    runner = runner_mod.ExperimentRunner(
        experiment="B35_model_panel", budget_usd=CAP, base_dir=HERE / "run",
        api_key=key, provider="openrouter")

    def call(u):
        return openrouter.chat(u.model, u.payload["messages"], api_key=key)

    U = runner_mod.Unit
    batch = [U(uid=f"{MODEL}|{arm}|{u['key']}|retry", model=MODEL,
               payload={"messages": [
                   {"role": "system", "content": u["system"]},
                   {"role": "user", "content": u[arm]}]})
             for u, arm in missing]
    outcome = runner.run(batch, call, est_cost_usd=len(batch) * 0.0095)
    print(f"\nspent ${outcome.cost_this_run:.4f}")

    still = 0
    for u, arm in missing:
        d = b35.stored(f"{MODEL}|{arm}|{u['key']}|retry")
        if not d:
            still += 1
    print(f"still empty after the retry: {still} of {len(missing)}")


if __name__ == "__main__":
    main()

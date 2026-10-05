"""The one panel model the provider rate-limited, asked again with pacing.

`google/gemma-3-4b-it` returned HTTP 429 on 636 of 647 attempts in the main
run. A single call succeeds, so the limit is on rate rather than on access.
This asks the same units with a delay between calls and an exponential backoff
on 429, which is the only difference from the panel run.

Unit ids carry a `|paced` suffix so the append-only ledger keeps both the
rate-limited attempts and these, and nothing is rewritten.
"""
from __future__ import annotations

import importlib.util
import json
import os
import sys
import time
from pathlib import Path

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE.parent))
from harness_path import add as _add  # noqa: E402
_add()
from importlib import import_module  # noqa: E402

openrouter = import_module("05_experiments._harness.openrouter")
runner_mod = import_module("05_experiments._harness.runner")

spec = importlib.util.spec_from_file_location("b35", HERE / "run.py")
b35 = importlib.util.module_from_spec(spec)
sys.modules["b35"] = b35
spec.loader.exec_module(b35)

MODEL = "google/gemma-3-4b-it"
GAP = 2.0          # seconds between calls
CAP = 0.50


def main() -> None:
    key = os.environ.get("OPENROUTER_API_KEY")
    if not key:
        raise SystemExit("OPENROUTER_API_KEY is not set; nothing was called.")

    units = b35.build_units()
    todo = []
    for u in units:
        for arm in ("undefended", "sentence", "blanket"):
            if (b35.stored(f"{MODEL}|{arm}|{u['key']}") is None
                    and b35.stored(f"{MODEL}|{arm}|{u['key']}|paced") is None):
                todo.append((u, arm))
    print(f"{len(todo)} unit-arms to ask, {GAP}s apart\n", flush=True)
    if not todo:
        return

    runner = runner_mod.ExperimentRunner(
        experiment="B35_model_panel", budget_usd=CAP, base_dir=HERE / "run",
        api_key=key, provider="openrouter")

    attempts = {"ok": 0, "rate_limited": 0}

    def call(u):
        delay = GAP
        for _ in range(6):
            try:
                r = openrouter.chat(u.model, u.payload["messages"], api_key=key)
                attempts["ok"] += 1
                time.sleep(GAP)
                return r
            except Exception as exc:
                if "429" not in str(exc):
                    raise
                attempts["rate_limited"] += 1
                time.sleep(delay)
                delay *= 2
        raise RuntimeError("still rate limited after six attempts")

    U = runner_mod.Unit
    batch = [U(uid=f"{MODEL}|{arm}|{u['key']}|paced", model=MODEL,
               payload={"messages": [
                   {"role": "system", "content": u["system"]},
                   {"role": "user", "content": u[arm]}]})
             for u, arm in todo]
    outcome = runner.run(batch, call, est_cost_usd=len(batch) * 0.000071)
    print(f"\nspent ${outcome.cost_this_run:.4f}")
    print(f"calls that went through: {attempts['ok']}")
    print(f"429 responses absorbed by the backoff: {attempts['rate_limited']}")

    got = sum(1 for u, arm in todo
              if b35.stored(f"{MODEL}|{arm}|{u['key']}|paced"))
    print(f"unit-arms now answered: {got} of {len(todo)}")


if __name__ == "__main__":
    main()

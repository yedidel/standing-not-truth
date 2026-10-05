"""Re-ask the one unit-arm the panel lost to an upstream rate limit.

`qwen/qwen3.7-flash|blanket|attack|21|mid` was attempted three times and each
attempt returned HTTP 429 from the upstream provider, so the blanket arm pools
to 425 where every other arm pools to 426. That is a lost call rather than an
outcome, and the honest fix is to ask again rather than to report a smaller
denominator. The failed attempts stay in the append-only ledger; this one is
asked under a `|retry` suffix so both are visible.
"""
from __future__ import annotations

import importlib.util
import json
import os
import sys
import urllib.request
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

MODEL = "qwen/qwen3.7-flash"
ARM = "blanket"
KEY = "attack|21|mid"
CAP = 0.05


def balance(key: str) -> str:
    req = urllib.request.Request(
        "https://openrouter.ai/api/v1/credits",
        headers={"Authorization": f"Bearer {key}"})
    with urllib.request.urlopen(req, timeout=30) as r:
        d = json.load(r)["data"]
    return f"granted {d.get('total_credits')}, used {d.get('total_usage')}"


def main() -> None:
    key = os.environ.get("OPENROUTER_API_KEY")
    if not key:
        raise SystemExit("OPENROUTER_API_KEY is not set; nothing was called.")
    print("balance before:", balance(key))

    unit = next(u for u in b35.build_units() if u["key"] == KEY)
    if b35.stored(f"{MODEL}|{ARM}|{KEY}") is not None:
        print("already stored; nothing to do")
        return

    runner = runner_mod.ExperimentRunner(
        experiment="B35_model_panel", budget_usd=CAP, base_dir=HERE / "run",
        api_key=key, provider="openrouter")

    def call(u):
        return openrouter.chat(u.model, u.payload["messages"], api_key=key)

    U = runner_mod.Unit
    batch = [U(uid=f"{MODEL}|{ARM}|{KEY}|retry", model=MODEL,
               payload={"messages": [
                   {"role": "system", "content": unit["system"]},
                   {"role": "user", "content": unit[ARM]}]})]
    outcome = runner.run(batch, call, est_cost_usd=0.0005)
    print(f"\nspent ${outcome.cost_this_run:.5f}")
    print("balance after:", balance(key))

    got = b35.stored(f"{MODEL}|{ARM}|{KEY}|retry")
    print("reply stored:", bool(got), "| chars:", len(got or ""))


if __name__ == "__main__":
    main()

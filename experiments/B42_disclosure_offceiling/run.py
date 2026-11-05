"""B-42 -- E8's disclosure arms on a decider that is not at the ceiling.

E8 reports disclosure against enforcement on `gemini-3.1-flash-lite`, and
says so plainly: *"This decider's undefended rate is already 90/90 (E1), so
the attack arm here has no room to rise and the conditions are measured
against a ceiling."* A reviewer reads a conceded ceiling as an unmeasured
claim, and the concession is the paper's own sentence.

This is `B30` with the decider replaced and nothing else touched. Two
deciders from E10's panel, chosen before the run from their published
landing rates and not after seeing anything here:

    deepseek/deepseek-v4-flash   lands on 47.2% of panel units, mid-range
    amazon/nova-micro-v1         lands on 77.8%, high but not saturated

`B30`'s own shape is 850 ledgered calls, so this is about 1,700 at a
measured $0.000087 and $0.000050 per call from the `B35` ledgers of 347 and
431. **Estimate $0.12.**

What it can settle: whether the ordering E8 reports survives off the ceiling.
What it cannot: the localizer arm, which `B30` scores against spans located
by `gemini-3.1-flash-lite`. Those spans are reused unchanged, so the third
condition measures a different decider acting on the same spans, which is
the comparison E8 makes and not a new one.

Key from `OPENROUTER_API_KEY`, never written to disk.
"""

from __future__ import annotations

import importlib.util
import sys
from importlib import import_module
from pathlib import Path

HERE = Path(__file__).parent
EXP = HERE.parent

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from harness_path import add as _add_harness  # noqa: E402
_add_harness()

for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass

runner_mod = import_module("05_experiments._harness.runner")


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


b30 = _load("b30_run", EXP / "B30_attribution" / "run.py")

DECIDERS = [
    ("deepseek/deepseek-v4-flash", 0.000087),
    ("amazon/nova-micro-v1", 0.000050),
]
BUDGET_USD = 0.60


def _rebadge(experiment: str):
    """Make B30's runner write this experiment's ledger, under this name.

    B30 names itself in a literal inside main(), so the name is replaced at
    the constructor rather than by editing B30, which still has to produce
    the bytes the paper already reports.
    """
    real = runner_mod.ExperimentRunner

    class Rebadged(real):
        def __init__(self, *a, **kw):
            kw["experiment"] = experiment
            super().__init__(*a, **kw)

    return real, Rebadged


def main() -> None:
    for model, per_call in DECIDERS:
        slug = model.split("/")[-1].replace(".", "-")
        here = HERE / slug
        here.mkdir(parents=True, exist_ok=True)

        print(f"\n{'=' * 64}\n### B-42, decider {model}\n{'=' * 64}", flush=True)

        b30.MODEL = model
        b30.RUN_DIR = here / "run"
        b30.OUT = here / "rows.json"
        b30.BUDGET_USD = BUDGET_USD / len(DECIDERS)
        b30.ESTIMATE_USD = 850 * per_call

        real, rebadged = _rebadge(f"B42_{slug}")
        runner_mod.ExperimentRunner = rebadged
        try:
            b30.main()
        finally:
            runner_mod.ExperimentRunner = real

    print("\nEvery reply still has to be read. These counts are the machine's "
          "first pass and not the result.")
    print("E8's claim is an ORDERING, that enforcement dominates disclosure. "
          "Read whether the ordering holds, not whether the rates match.")


if __name__ == "__main__":
    main()

"""Resumable, budget-capped experiment runner.

Implements the four-stage run protocol from ``00_plan/MASTER_PLAN.md``:

  1. pre-flight: check the key balance against the projected cost
  2. run: skip units already completed, record every call before returning
  3. stop: halt cleanly at the budget cap or on a balance error, never retry
  4. report: actual cost against the estimate, remaining balance, resume path

A unit is a single (experiment, model, condition, trial) coordinate with a
deterministic id. Re-running a finished experiment costs nothing.
"""

from __future__ import annotations

import hashlib
import json
import traceback
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Sequence

from .ledger import Ledger, LedgerRecord, utc_now
from .errors import InsufficientBalance, ProviderExhausted
from .openrouter import Balance, extract_usage, get_balance


@dataclass
class Unit:
    """One unit of work. ``uid`` must be deterministic across runs."""

    uid: str
    model: str
    payload: dict[str, Any] = field(default_factory=dict)
    provider: str | None = None
    """Overrides the runner's provider. Set it when one experiment spans
    providers, so weekly quota accounting attributes each call correctly."""


class BudgetExceeded(RuntimeError):
    pass


@dataclass
class RunOutcome:
    experiment: str
    total_units: int
    already_done: int
    attempted: int
    succeeded: int
    failed: int
    stopped_early: bool
    stop_reason: str | None
    balance_before: Balance | None
    balance_after: Balance | None
    cost_this_run: float
    cost_estimated: float
    cost_cumulative: float


class ExperimentRunner:
    def __init__(
        self,
        experiment: str,
        budget_usd: float,
        base_dir: str | Path,
        api_key: str | None = None,
        usage_fn: Callable[[dict], tuple[int, int, float]] | None = None,
        balance_fn: Callable[[], Balance | None] | None = None,
        provider: str = "openrouter",
    ) -> None:
        self.experiment = experiment
        self.budget_usd = budget_usd
        self.base = Path(base_dir)
        self.raw_dir = self.base / "raw"
        self.raw_dir.mkdir(parents=True, exist_ok=True)
        self.ledger = Ledger(self.base / "ledger.jsonl")
        self.api_key = api_key
        self.provider = provider
        # Providers differ in how usage is reported and whether a balance
        # exists at all. Both default to the OpenRouter behaviour.
        self._usage = usage_fn or extract_usage
        self._balance = balance_fn or (lambda: get_balance(self.api_key))

    # ---- stage 1 -------------------------------------------------------

    def preflight(self, units: Sequence[Unit], est_cost_usd: float) -> Balance:
        """Refuse to start a run that cannot finish."""
        pending = [u for u in units if u.uid not in self.ledger.completed_unit_ids()]
        balance = self._balance()

        print(f"\n=== {self.experiment} pre-flight ===")
        print(f"  units total     : {len(units)}")
        print(f"  already complete: {len(units) - len(pending)}")
        print(f"  to run          : {len(pending)}")
        print(f"  estimated cost  : ${est_cost_usd:.4f}")
        print(f"  budget cap      : ${self.budget_usd:.4f}")
        if balance:
            print(f"  {balance}")
        elif self.provider == "ollama":
            from .ollama import weekly_usage

            u = weekly_usage()
            print(
                f"  ollama {u['iso_week']}: {u['calls']} calls, "
                f"{u['tokens_in']:,} in / {u['tokens_out']:,} out this week"
            )
            print("  (no quota endpoint; a limit surfaces as a clean stop)")
        else:
            print("  balance: n/a for this provider")

        if not pending:
            print("  -> nothing to do; a completed experiment costs $0 to re-run")
            return balance

        if balance is not None and balance.remaining < est_cost_usd:
            affordable = (
                int(len(pending) * balance.remaining / est_cost_usd)
                if est_cost_usd > 0
                else 0
            )
            raise InsufficientBalance(
                f"Balance ${balance.remaining:.4f} is below the estimate "
                f"${est_cost_usd:.4f}. Short by ${est_cost_usd - balance.remaining:.4f}. "
                f"About {affordable} of {len(pending)} pending units are affordable now; "
                f"the run would stop cleanly and resume later, but it is not started "
                f"without approval."
            )
        print("  -> OK to run\n")
        return balance

    # ---- stage 2 and 3 -------------------------------------------------

    def run(
        self,
        units: Sequence[Unit],
        call: Callable[[Unit], dict[str, Any]],
        est_cost_usd: float = 0.0,
    ) -> RunOutcome:
        balance_before = self.preflight(units, est_cost_usd)
        done = self.ledger.completed_unit_ids()
        pending = [u for u in units if u.uid not in done]

        run_cost = 0.0
        succeeded = failed = 0
        stopped, reason = False, None

        for i, unit in enumerate(pending, 1):
            if run_cost >= self.budget_usd:
                stopped, reason = True, f"budget cap ${self.budget_usd:.4f} reached"
                break
            try:
                response = call(unit)
            except ProviderExhausted as exc:
                kind = type(exc).__name__
                self._record_stop(unit, f"{kind}: {exc}")
                stopped, reason = True, f"provider exhausted ({kind})"
                break
            except Exception as exc:  # noqa: BLE001 - recorded, then continue
                failed += 1
                self.ledger.append(
                    LedgerRecord(
                        exp=self.experiment,
                        unit_id=unit.uid,
                        model=unit.model,
                        provider=unit.provider or self.provider,
                        status="error",
                        error=f"{type(exc).__name__}: {exc}"[:500],
                        meta={"traceback": traceback.format_exc()[-800:]},
                    )
                )
                print(f"  [{i}/{len(pending)}] {unit.uid} ERROR {type(exc).__name__}")
                continue

            tin, tout, cost = self._usage(response)
            raw = json.dumps(response, ensure_ascii=False, indent=2)
            digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()
            path = self.raw_dir / f"{_safe(unit.uid)}.json"
            path.write_text(raw, encoding="utf-8")

            self.ledger.append(
                LedgerRecord(
                    exp=self.experiment,
                    unit_id=unit.uid,
                    model=unit.model,
                    provider=unit.provider or self.provider,
                    status="ok",
                    tokens_in=tin,
                    tokens_out=tout,
                    cost_usd=cost,
                    response_sha256=digest,
                    response_path=str(path.relative_to(self.base)),
                    meta=unit.payload.get("meta", {}),
                )
            )
            run_cost += cost
            succeeded += 1
            print(
                f"  [{i}/{len(pending)}] {unit.uid} ok "
                f"({tin}+{tout} tok, ${cost:.6f}, run total ${run_cost:.4f})"
            )

        balance_after = self._safe_balance()
        outcome = RunOutcome(
            experiment=self.experiment,
            total_units=len(units),
            already_done=len(units) - len(pending),
            attempted=succeeded + failed,
            succeeded=succeeded,
            failed=failed,
            stopped_early=stopped,
            stop_reason=reason,
            balance_before=balance_before,
            balance_after=balance_after,
            cost_this_run=round(run_cost, 6),
            cost_estimated=est_cost_usd,
            cost_cumulative=self.ledger.total_cost(),
        )
        self.write_report(outcome)
        return outcome

    def _record_stop(self, unit: Unit, message: str) -> None:
        self.ledger.append(
            LedgerRecord(
                exp=self.experiment,
                unit_id=unit.uid,
                model=unit.model,
                provider=unit.provider or self.provider,
                status="budget_stop",
                error=message[:500],
            )
        )

    def _safe_balance(self) -> Balance | None:
        try:
            return self._balance()
        except Exception:  # noqa: BLE001 - reporting must not mask the run
            return None

    # ---- stage 4 -------------------------------------------------------

    def write_report(self, o: RunOutcome) -> Path:
        remaining = o.total_units - o.already_done - o.succeeded
        drift = (
            f"{(o.cost_this_run - o.cost_estimated) / o.cost_estimated:+.1%}"
            if o.cost_estimated > 0
            else "n/a"
        )
        lines = [
            f"# Run report — {o.experiment}",
            "",
            f"Generated {utc_now()}",
            "",
            "| | |",
            "|---|---|",
            f"| Balance before | {_money(o.balance_before)} |",
            f"| **Actual cost this run** | **${o.cost_this_run:.4f}** |",
            f"| Estimated cost | ${o.cost_estimated:.4f} |",
            f"| Estimate drift | {drift} |",
            f"| **Balance after** | **{_money(o.balance_after)}** |",
            f"| Cumulative cost, this experiment | ${o.cost_cumulative:.4f} |",
            "",
            "| | |",
            "|---|---|",
            f"| Units total | {o.total_units} |",
            f"| Already complete on entry | {o.already_done} |",
            f"| Succeeded this run | {o.succeeded} |",
            f"| Failed this run | {o.failed} |",
            f"| **Remaining** | **{remaining}** |",
            "",
        ]
        if o.stopped_early:
            lines += [
                f"## Stopped early: {o.stop_reason}",
                "",
                f"{remaining} units remain. Re-run the same command to resume; "
                "completed units are skipped and cost nothing.",
                "",
            ]
        elif remaining == 0:
            lines += ["## Complete", ""]
        path = self.base / "RUN_REPORT.md"
        path.write_text("\n".join(lines), encoding="utf-8")
        print("\n".join(lines[3:]))
        return path


def _money(b: Balance | None) -> str:
    return f"${b.remaining:.4f}" if b else "unavailable"


def _safe(uid: str) -> str:
    return "".join(c if c.isalnum() or c in "-_." else "_" for c in uid)[:180]

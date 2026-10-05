"""Offline tests for the harness. No API key, no network, no cost.

Verifies the three properties the run protocol depends on:
  1. a call is durable on disk before its result reaches the caller
  2. a killed run resumes at the exact point of interruption
  3. a completed experiment re-runs for $0
"""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from importlib import import_module

_h = import_module("05_experiments._harness")  # noqa: E402
Balance = _h.Balance
ExperimentRunner = _h.ExperimentRunner
Ledger = _h.Ledger
LedgerRecord = _h.LedgerRecord
Unit = _h.Unit

FAKE_BALANCE = Balance(total=20.0, used=5.0)  # $15 remaining


def _response(cost: float = 0.001) -> dict:
    return {
        "choices": [{"message": {"content": "ok"}}],
        "usage": {"prompt_tokens": 1738, "completion_tokens": 56, "cost": cost},
    }


def _units(n: int) -> list[Unit]:
    return [
        Unit(uid=f"E0|test-model|cond_a|t0.0|trial{i:02d}", model="test-model")
        for i in range(n)
    ]


def test_durability_and_cost(tmp: Path) -> None:
    with mock.patch.object(_h.runner, "get_balance", return_value=FAKE_BALANCE):
        r = ExperimentRunner("E0", budget_usd=1.0, base_dir=tmp)
        out = r.run(_units(5), lambda u: _response(), est_cost_usd=0.005)

    assert out.succeeded == 5, out
    assert abs(out.cost_this_run - 0.005) < 1e-9, out.cost_this_run

    recs = [json.loads(l) for l in (tmp / "ledger.jsonl").read_text().splitlines()]
    assert len(recs) == 5
    assert all(r["status"] == "ok" for r in recs)
    # cumulative cost is monotone and correct on every line
    assert [round(r["cum_cost_usd"], 6) for r in recs] == [
        0.001, 0.002, 0.003, 0.004, 0.005
    ]
    # every raw response persisted and hashed
    assert len(list((tmp / "raw").glob("*.json"))) == 5
    assert all(r["response_sha256"] for r in recs)
    print("PASS  durability, cost accounting, raw capture")


def test_resume_after_crash(tmp: Path) -> None:
    calls = {"n": 0}

    def flaky(unit: Unit) -> dict:
        calls["n"] += 1
        if calls["n"] > 3:
            raise KeyboardInterrupt("simulated kill mid-run")
        return _response()

    with mock.patch.object(_h.runner, "get_balance", return_value=FAKE_BALANCE):
        r = ExperimentRunner("E0", budget_usd=1.0, base_dir=tmp)
        try:
            r.run(_units(10), flaky, est_cost_usd=0.01)
        except KeyboardInterrupt:
            pass  # the kill escapes, as a real Ctrl-C would

        # the three paid-for calls survived the kill
        assert len(Ledger(tmp / "ledger.jsonl").completed_unit_ids()) == 3

        # resume: only the remaining 7 are attempted
        r2 = ExperimentRunner("E0", budget_usd=1.0, base_dir=tmp)
        out = r2.run(_units(10), lambda u: _response(), est_cost_usd=0.007)

    assert out.already_done == 3, out.already_done
    assert out.succeeded == 7, out.succeeded
    assert len(Ledger(tmp / "ledger.jsonl").completed_unit_ids()) == 10
    print("PASS  resume picks up exactly where the kill happened")


def test_completed_rerun_is_free(tmp: Path) -> None:
    with mock.patch.object(_h.runner, "get_balance", return_value=FAKE_BALANCE):
        r = ExperimentRunner("E0", budget_usd=1.0, base_dir=tmp)
        r.run(_units(4), lambda u: _response(), est_cost_usd=0.004)

        def must_not_be_called(unit: Unit) -> dict:
            raise AssertionError(f"re-ran a completed unit: {unit.uid}")

        out = ExperimentRunner("E0", 1.0, tmp).run(_units(4), must_not_be_called, 0.0)

    assert out.attempted == 0 and out.cost_this_run == 0.0, out
    print("PASS  re-running a completed experiment costs $0")


def test_budget_cap_stops_cleanly(tmp: Path) -> None:
    with mock.patch.object(_h.runner, "get_balance", return_value=FAKE_BALANCE):
        r = ExperimentRunner("E0", budget_usd=0.0035, base_dir=tmp)
        out = r.run(_units(100), lambda u: _response(), est_cost_usd=0.10)

    assert out.stopped_early and "budget cap" in (out.stop_reason or "")
    assert out.succeeded == 4, out.succeeded  # stops once cost >= cap
    assert "Stopped early" in (tmp / "RUN_REPORT.md").read_text(encoding="utf-8")
    print("PASS  budget cap halts at a unit boundary and reports the resume path")


def test_preflight_refuses_when_short(tmp: Path) -> None:
    broke = Balance(total=20.0, used=19.99)  # $0.01 remaining
    with mock.patch.object(_h.runner, "get_balance", return_value=broke):
        r = ExperimentRunner("E0", budget_usd=5.0, base_dir=tmp)
        try:
            r.run(_units(50), lambda u: _response(), est_cost_usd=5.0)
        except _h.InsufficientBalance as exc:
            assert "Short by" in str(exc) and "affordable" in str(exc)
            print("PASS  pre-flight refuses to start a run that cannot finish")
            return
    raise AssertionError("expected InsufficientBalance")


def test_quota_stop_is_clean_and_resumable(tmp: Path) -> None:
    """A weekly quota hit must halt at a unit boundary and lose nothing."""
    calls = {"n": 0}

    def quota_after_5(unit: Unit) -> dict:
        calls["n"] += 1
        if calls["n"] > 5:
            raise _h.QuotaExhausted("Ollama quota reached (HTTP 429)")
        return _response(cost=0.0)

    with mock.patch.object(_h.runner, "get_balance", return_value=FAKE_BALANCE):
        r = ExperimentRunner("E0", budget_usd=1.0, base_dir=tmp)
        out = r.run(_units(30), quota_after_5, est_cost_usd=0.0)

        assert out.stopped_early and "QuotaExhausted" in (out.stop_reason or "")
        assert out.succeeded == 5, out.succeeded
        report = (tmp / "RUN_REPORT.md").read_text(encoding="utf-8")
        assert "Stopped early" in report and "resume" in report.lower()

        # the five served calls survive, and a later run continues from there
        assert len(Ledger(tmp / "ledger.jsonl").completed_unit_ids()) == 5
        out2 = ExperimentRunner("E0", 1.0, tmp).run(
            _units(30), lambda u: _response(cost=0.0), 0.0
        )
    assert out2.already_done == 5 and out2.succeeded == 25, out2
    print("PASS  a quota stop halts cleanly and the next run resumes")


def test_torn_line_tolerated(tmp: Path) -> None:
    led = Ledger(tmp / "ledger.jsonl")
    led.append(LedgerRecord(exp="E0", unit_id="u1", model="m", status="ok", cost_usd=0.5))
    with (tmp / "ledger.jsonl").open("a", encoding="utf-8") as fh:
        fh.write('{"exp":"E0","unit_id":"u2","sta')  # power cut mid-write
    fresh = Ledger(tmp / "ledger.jsonl")
    assert fresh.completed_unit_ids() == {"u1"}
    assert fresh.total_cost() == 0.5
    print("PASS  a torn final line does not corrupt the ledger")


if __name__ == "__main__":
    tests = [
        test_durability_and_cost,
        test_resume_after_crash,
        test_completed_rerun_is_free,
        test_budget_cap_stops_cleanly,
        test_preflight_refuses_when_short,
        test_quota_stop_is_clean_and_resumable,
        test_torn_line_tolerated,
    ]
    for fn in tests:
        with tempfile.TemporaryDirectory() as d:
            fn(Path(d))
    print(f"\n{len(tests)}/{len(tests)} harness tests passed. No network, no cost.")

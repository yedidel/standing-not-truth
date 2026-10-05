"""Append-only, crash-safe spend ledger.

Every API call is durably recorded BEFORE its result is handed back to the
caller. If the process dies, the key runs dry, or the machine reboots, no
call that was paid for is lost, and the next run resumes from the exact
point of interruption.

The unit of work is identified by a deterministic ``unit_id`` built from the
experiment coordinates (model, condition, temperature, trial index) and
never from a counter or a timestamp. Re-running a completed experiment is
therefore a no-op that costs nothing.
"""

from __future__ import annotations

import json
import os
import threading
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


@dataclass
class LedgerRecord:
    """One API call. Written to disk before the caller sees the response."""

    exp: str
    unit_id: str
    model: str
    status: str  # ok | error | refused | budget_stop
    provider: str = "openrouter"
    ts: str = field(default_factory=utc_now)
    tokens_in: int = 0
    tokens_out: int = 0
    cost_usd: float = 0.0
    cum_cost_usd: float = 0.0
    balance_after: float | None = None
    response_sha256: str | None = None
    response_path: str | None = None
    error: str | None = None
    meta: dict[str, Any] = field(default_factory=dict)


class Ledger:
    """Append-only JSONL ledger with fsync-on-write."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._completed: set[str] | None = None
        self._cum_cost: float | None = None

    # ---- reading -------------------------------------------------------

    def records(self) -> Iterator[dict[str, Any]]:
        if not self.path.exists():
            return
        with self.path.open("r", encoding="utf-8") as fh:
            for line_no, line in enumerate(fh, 1):
                line = line.strip()
                if not line:
                    continue
                try:
                    yield json.loads(line)
                except json.JSONDecodeError:
                    # A torn final line means the process died mid-write.
                    # Everything before it is intact, which is the point of
                    # the format. Skip it and carry on.
                    print(f"[ledger] skipping malformed line {line_no}")

    def completed_unit_ids(self) -> set[str]:
        """Unit ids that succeeded. Only these are skipped on resume.

        Errored units are deliberately NOT included: a transient failure
        should be retried on the next run, not silently treated as done.
        """
        if self._completed is None:
            self._completed = {
                r["unit_id"] for r in self.records() if r.get("status") == "ok"
            }
        return self._completed

    def total_cost(self) -> float:
        if self._cum_cost is None:
            self._cum_cost = round(
                sum(float(r.get("cost_usd") or 0.0) for r in self.records()), 6
            )
        return self._cum_cost

    def count(self, status: str | None = None) -> int:
        return sum(
            1 for r in self.records() if status is None or r.get("status") == status
        )

    # ---- writing -------------------------------------------------------

    def append(self, record: LedgerRecord) -> None:
        """Write one record and force it to disk before returning."""
        with self._lock:
            record.cum_cost_usd = round(self.total_cost() + record.cost_usd, 6)
            payload = json.dumps(asdict(record), ensure_ascii=False)
            with self.path.open("a", encoding="utf-8") as fh:
                fh.write(payload + "\n")
                fh.flush()
                os.fsync(fh.fileno())
            # Keep the in-memory caches consistent with what is now on disk.
            self._cum_cost = record.cum_cost_usd
            if record.status == "ok" and self._completed is not None:
                self._completed.add(record.unit_id)

"""B-11 — what the defense costs to run, from the ledgers rather than a model.

Every closed-weight call this project made landed in an append-only ledger with
its token counts and the price the provider charged. **Nothing here is
estimated.** The per-call figures are measured, and the per-decision figures are
those measured costs multiplied by the call structure each placement actually
uses.

The genre expects this section. Every scheme paper at this venue reports
overhead, and a defense that protects a decision for less than the decision
itself costs is a different proposition from one that doubles it.

Three questions it answers:

  1. what does one protected decision cost, by placement
  2. how does that compare with the undefended decision
  3. what does the open-weight configuration cost, which is zero in money and
     not zero in latency

Open-weight calls carry no price and are counted separately. Reporting them at
$0 alongside metered calls would understate the real cost of the open-weight
path, which is hardware rather than invoice.
"""

from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
EXPERIMENTS = ROOT / "experiments"


def ledgers() -> list[dict]:
    rows = []
    for path in EXPERIMENTS.rglob("*.jsonl"):
        for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(record, dict) and record.get("status") == "ok":
                record["_file"] = str(path.relative_to(ROOT))
                rows.append(record)
    return rows


def main() -> None:
    rows = ledgers()
    metered = [r for r in rows if (r.get("cost_usd") or 0) > 0]
    free = [r for r in rows if not (r.get("cost_usd") or 0)]

    print(f"### the ledgers\n")
    print(f"  successful calls recorded            {len(rows):,}")
    print(f"  metered (closed-weight)              {len(metered):,}")
    print(f"  unmetered (open-weight)              {len(free):,}")
    print(f"  total charged                        "
          f"${sum(r['cost_usd'] for r in metered):.4f}")

    by_model = defaultdict(lambda: {"n": 0, "cost": 0.0, "tin": 0, "tout": 0})
    for r in metered:
        slot = by_model[r.get("model", "?")]
        slot["n"] += 1
        slot["cost"] += r["cost_usd"]
        slot["tin"] += r.get("tokens_in") or 0
        slot["tout"] += r.get("tokens_out") or 0

    print(f"\n### measured cost per call, closed-weight\n")
    print(f"  {'model':34s} {'calls':>6s} {'mean $/call':>12s} "
          f"{'mean in':>8s} {'mean out':>9s}")
    for model, s in sorted(by_model.items(), key=lambda kv: -kv[1]["n"]):
        print(f"  {model:34s} {s['n']:6d} {s['cost'] / s['n']:12.6f} "
              f"{s['tin'] // s['n']:8d} {s['tout'] // s['n']:9d}")

    # Per-stage costs, taken from the runs that used one call per stage.
    stage_cost = {}
    for path, stages in (
        ("experiments/B5_extend_n/run/ledger.jsonl",
         ("baseline", "spotlight", "ablated", "flatten", "transpose", "shadow",
          "judge")),
    ):
        for r in rows:
            if r["_file"].replace("\\", "/") != path:
                continue
            uid = r.get("unit_id") or ""
            stage = uid.split("|", 1)[0]
            if stage in stages:
                slot = stage_cost.setdefault(stage, {"n": 0, "cost": 0.0})
                slot["n"] += 1
                slot["cost"] += r.get("cost_usd") or 0

    print(f"\n### measured cost per call by stage, from B5\n")
    for stage, s in stage_cost.items():
        if s["n"]:
            print(f"  {stage:14s} {s['n']:4d} calls   "
                  f"${s['cost'] / s['n']:.6f} each")

    def cost(*stages: str) -> float:
        return sum(stage_cost[s]["cost"] / stage_cost[s]["n"]
                   for s in stages if stage_cost.get(s, {}).get("n"))

    undefended = cost("baseline")
    origin = cost("baseline")            # the marking is free; the call is the same
    influence = cost("baseline", "ablated")
    attriguard = cost("flatten", "transpose", "shadow", "judge")

    print(f"\n### cost of one protected decision\n")
    print(f"  {'placement':40s} {'calls':>6s} {'$ / decision':>13s} "
          f"{'vs undefended':>14s}")
    for label, calls, total in (
        ("undefended", 1, undefended),
        ("origin, block marked untrusted", 1, origin),
        ("influence, ablate and compare", 2, influence),
        ("AttriGuard, artifact pipeline", 4, attriguard),
    ):
        ratio = f"{total / undefended:.2f}x" if undefended else "n/a"
        print(f"  {label:40s} {calls:6d} {total:13.6f} {ratio:>14s}")

    # The subject check adds one short extractor call. `A10` ran exactly that
    # call on the same closed-weight model, so its ledger prices it rather than
    # leaving the only placement that works as the only one without a price.
    a10 = [r for r in rows
           if "A10_extractor_generality" in r["_file"] and (r.get("cost_usd") or 0)]
    if a10:
        extra = sum(r["cost_usd"] for r in a10) / max(1, len(a10))
        subject = undefended + extra
        ratio = f"{subject / undefended:.2f}x" if undefended else "n/a"
        print(f"  {'subject, clause (i)':40s} {2:6d} {subject:13.6f} "
              f"{ratio:>14s}")
        tin = sum(r.get("tokens_in") or 0 for r in a10) // max(1, len(a10))
        tout = sum(r.get("tokens_out") or 0 for r in a10) // max(1, len(a10))
        print(f"\n  The subject call is short: {tin} tokens in, {tout} out, "
              f"${extra:.6f} each,\n  priced from A10's ledger on the same "
              f"model rather than left unpriced.")

    print(f"\n### what the whole project cost\n")
    print(f"  metered spend across every experiment  "
          f"${sum(r['cost_usd'] for r in metered):.4f}")
    print(f"  unmetered calls                        {len(free):,}")
    print("\n  Open-weight calls are counted, never priced at $0 alongside "
          "metered ones.\n  Their cost is hardware and latency, and the "
          "latency is reported separately.")


if __name__ == "__main__":
    main()

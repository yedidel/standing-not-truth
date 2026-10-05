"""Backfill ledger records for runs that bypassed the experiment runner.

METHODOLOGY rule 15 requires one ledger record per model call, each carrying a
per-response SHA-256, so a table can be reproduced by re-scoring stored
responses without provider access. A-7, A-8, A-9 and A-11 called providers
directly and produced stored outputs with no ledger line.

No money is unaccounted, since those runs were on the flat-rate provider. What
is missing is the integrity record, and this reconstructs it from the artifacts
that were stored at the time. Every backfilled row is marked `backfilled: true`
so it is never mistaken for a record written at call time, and the cost field
is 0.0 because the provider reports no per-call charge, which is a measured
zero for that provider rather than an unknown.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).parent

# (experiment, directory holding the artifacts, glob, how to read one file)
SOURCES = [
    ("A8", HERE / "A8_heldout_phrasings", "heldout_premises.json", "json-array"),
    ("A9", HERE / "A9_adaptive", "traces_v2.json", "json-array"),
    ("A9", HERE / "A9_adaptive", "traces_v3.json", "json-array"),
    ("A11", HERE / "A11_model_hub", "corpus_hf.json", "corpus"),
    ("A7", HERE / "A7_standing_classifier", "predictions.json", "json-array"),
]


def digest(obj) -> str:
    return hashlib.sha256(
        json.dumps(obj, ensure_ascii=False, sort_keys=True).encode("utf-8")
    ).hexdigest()


def rows_from(kind: str, payload) -> list[dict]:
    if kind == "corpus":
        return [m for inst in payload.get("instances", []) for m in inst.get("models", [])]
    return payload if isinstance(payload, list) else []


def main() -> None:
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    written = 0
    for exp, base, name, kind in SOURCES:
        path = base / name
        if not path.exists():
            print(f"  {exp}: {name} not present, skipped")
            continue
        payload = json.loads(path.read_text(encoding="utf-8"))
        rows = rows_from(kind, payload)
        if not rows:
            print(f"  {exp}: {name} produced no rows, skipped")
            continue

        out = base / f"ledger_backfill_{name.replace('.json', '')}.jsonl"
        with out.open("w", encoding="utf-8") as fh:
            for index, row in enumerate(rows):
                record = {
                    "exp": exp,
                    "unit_id": f"{exp}|backfill|{name}|{index:04d}",
                    "model": row.get("generator") or row.get("model") or "see_source",
                    "provider": "ollama",
                    "status": "ok",
                    "ts": now,
                    "cost_usd": 0.0,
                    "response_sha256": digest(row),
                    "response_path": str(path.relative_to(base)),
                    "backfilled": True,
                    "note": "reconstructed from the stored artifact; the original "
                            "call was not routed through the runner",
                }
                fh.write(json.dumps(record, ensure_ascii=False) + "\n")
                written += 1
        print(f"  {exp}: {len(rows):4d} records -> {out.name}")

    print(f"\nbackfilled {written} records")
    print("these carry backfilled=true and must never be counted as "
          "call-time provenance")


if __name__ == "__main__":
    main()

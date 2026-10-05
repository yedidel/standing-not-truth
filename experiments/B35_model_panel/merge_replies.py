"""Rebuild rows.json so every stored reply is present, including the retried ones.

Two models needed a second attempt. `google/gemma-3-4b-it` was rate limited and
was asked again with pacing, under unit ids suffixed `|paced`.
`anthropic/claude-opus-5` returned empty bodies that the harness recorded as
successful, and those were asked again under `|retry`. The append-only ledger
keeps both attempts; this collects whichever attempt produced a reply so that
no model is under-represented when the replies are read.

It writes the reply text only. Choosing what a reply means is not done here.
"""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

HERE = Path(__file__).parent

spec = importlib.util.spec_from_file_location("b35", HERE / "run.py")
b35 = importlib.util.module_from_spec(spec)
sys.modules["b35"] = b35
spec.loader.exec_module(b35)

ARMS = ("undefended", "sentence", "blanket")


def first_reply(model: str, arm: str, key: str) -> str | None:
    """The reply from whichever attempt produced one."""
    for suffix in ("", "|paced", "|retry"):
        got = b35.stored(f"{model}|{arm}|{key}{suffix}")
        if got:
            return got
    return None


def main() -> None:
    units = {u["key"]: u for u in b35.build_units()}
    rows, counts = [], {}
    for vendor, model, n in b35.PANEL:
        for key in list(units)[:n]:
            unit = units[key]
            row = {"key": f"{model}|{key}", "vendor": vendor, "model": model,
                   "unit": key, "promoted": unit["promoted"],
                   "correct": unit["correct"], "names": unit["names"]}
            for arm in ARMS:
                text = first_reply(model, arm, key)
                row[f"{arm}_reply"] = text
                if text:
                    counts[(model, arm)] = counts.get((model, arm), 0) + 1
            rows.append(row)
    (HERE / "rows.json").write_text(
        json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"{len(rows)} rows written\n")
    print(f"{'model':32s} {'undef':>6s} {'sent':>6s} {'blank':>6s}")
    total = 0
    for _, model, _ in b35.PANEL:
        u, s, b = (counts.get((model, a), 0) for a in ARMS)
        total += u + s + b
        print(f"{model:32s} {u:6d} {s:6d} {b:6d}")
    print(f"\nreplies available to read: {total}")


if __name__ == "__main__":
    main()

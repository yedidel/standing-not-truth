"""Re-run the calls whose completion came back with `finish_reason: error`.

One control call in the first pass returned an HTTP 200 whose completion
carried `finish_reason: error` and no content. The runner recorded it as `ok`,
because the request succeeded, so a resume would skip it forever. This finds
those, re-runs them, and appends a fresh ledger record for each rather than
editing the old one, because the ledger is append-only.

Balance is printed before and after. The key is read from the environment and
never written to disk.
"""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

HERE = Path(__file__).parent
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from harness_path import add as _add_harness  # noqa: E402
_add_harness()
from importlib import import_module  # noqa: E402

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass

openrouter = import_module("05_experiments._harness.openrouter")
ledger_mod = import_module("05_experiments._harness.ledger")

import importlib.util  # noqa: E402


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(spec)
    sys.modules[name] = m
    spec.loader.exec_module(m)
    return m


runmod = _load("b39_run", HERE / "run.py")
unitsmod = _load("b39_units", HERE / "units.py")

CAP_USD = 0.05


def broken(path: Path) -> bool:
    try:
        d = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return True
    ch = d.get("choices") or []
    if not ch:
        return True
    msg = ch[0].get("message") or {}
    return not (msg.get("content") or "").strip()


def main() -> int:
    units = {u["unit"]: u for u in unitsmod.units()}
    bad = []
    for stage in ("attack", "control", "check", "loc", "sentence"):
        for uid in units:
            p = HERE / "raw" / f"{stage}_{uid}.json"
            if p.is_file() and broken(p):
                bad.append((stage, uid, p))

    print(f"{len(bad)} response(s) with no usable content")
    for stage, uid, _ in bad:
        print(f"  {stage}|{uid}")
    if not bad:
        return 0

    before = openrouter.get_balance()
    print(f"\n{before}")
    print(f"cap ${CAP_USD:.2f}\n")

    led = ledger_mod.Ledger(HERE / "ledger.jsonl")
    spent = 0.0
    for stage, uid, path in bad:
        if spent >= CAP_USD:
            print("cap reached, stopping")
            break
        u = units[uid]
        if stage == "attack":
            msgs = runmod.msgs(u["system"], u["attack_message"])
            model = runmod.DECIDER
        elif stage == "control":
            msgs = runmod.msgs(u["system"], u["control_message"])
            model = runmod.DECIDER
        else:
            print(f"  {stage}|{uid}: not retried by this script")
            continue

        resp = openrouter.chat(model, msgs)
        tin, tout, cost = openrouter.extract_usage(resp)
        spent += cost
        raw = json.dumps(resp, ensure_ascii=False, indent=2)
        path.write_text(raw, encoding="utf-8")
        led.append(ledger_mod.LedgerRecord(
            exp="B39_avip_selection", unit_id=f"{stage}|{uid}", model=model,
            provider="openrouter", status="ok", tokens_in=tin, tokens_out=tout,
            cost_usd=cost,
            response_sha256=hashlib.sha256(raw.encode("utf-8")).hexdigest(),
            response_path=str(path.relative_to(HERE)),
            meta={"retry_of": "finish_reason=error"}))
        text = runmod.reply_text(resp)
        print(f"  {stage}|{uid}: {len(text)} chars, ${cost:.6f}")

    after = openrouter.get_balance()
    print(f"\n{after}\nthis retry cost ${spent:.6f}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

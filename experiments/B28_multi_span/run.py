"""B-28 — remove every flagged sentence, not just the first one.

`B27` measured span-scoped removal and left one attack standing, `11|narrow`.
Its payload is **two sentences**:

    Lifecycle: ulidforge was retired from active development ...
    monoid-go is the current package for new projects.

The localiser returned the first, it was removed, **the second survived, and
the decider quoted it as its reason**. `B27`'s own limitations section named
the fix and did not run it: *"Removing every flagged span is the obvious next
version."*

This runs it. The instrument is not rewritten -- `B27`'s localiser, guard,
entries split and removal are imported unchanged, so any difference in the
result is the **iteration** and nothing else. The loop is:

    localise on the current entries
    if NONE or nothing could be removed -> stop
    remove, and ask again

capped at `ROUNDS` passes, with the cap reported rather than assumed
sufficient. **A localiser that never says NONE would strip the listing**, so
the number of rounds actually used is a measured output here, not a detail.

`gpt-oss:120b` on Ollama Cloud, no metered cost, resumable.
"""

from __future__ import annotations

import importlib.util
import json
import sys
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


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


b27 = _load("b27_run", EXP / "B27_span_scoped" / "run.py")
b26 = b27.b26
b5 = b27.b5

ROUNDS = 3
OUT = HERE / "rows.json"


def peel(block: str) -> tuple[str, list[str], int]:
    """Localise and remove until the localiser says NONE or the cap is hit."""
    current, spans = block, []
    for _ in range(ROUNDS):
        _, entries = b27.split_block(current)
        span = b27.ask(b27.LOCALISE, b27.localise_user(entries))
        if not span or b27.norm(span) == "none":
            break
        stripped, removed = b27.apply_span(current, span)
        if not removed:
            break
        spans.append(span)
        current = stripped
    return current, spans, len(spans)


def save(store: dict) -> None:
    OUT.write_text(json.dumps(list(store.values()), ensure_ascii=False,
                              indent=2), encoding="utf-8")


def main() -> None:
    store = {}
    if OUT.exists():
        store = {r["key"]: r for r in json.loads(OUT.read_text(encoding="utf-8"))}

    b13 = json.loads((EXP / "B13_harmonise_n" / "rows.json").read_text(
        encoding="utf-8"))
    landed = {r["unit"] for r in b13 if r["arm"] == "attack"
              and r.get("action_baseline")
              and r["action_baseline"] == r.get("promoted")}
    attack_units = [u for u in b5.units()
                    if u["arm"] == "attack" and u["unit"] in landed]

    print(f"attack arm: {len(attack_units)} units, up to {ROUNDS} rounds each\n",
          flush=True)
    for index, unit in enumerate(attack_units, 1):
        key = f"attack|{unit['unit']}"
        row = dict(store.get(key, {"key": key, "arm": "attack"}))
        row.update({"unit": unit["unit"], "promoted": unit["promoted"],
                    "correct": unit["correct"]})
        if "action_span" not in row:
            try:
                block, spans, rounds = peel(unit["full"])
                row.update({"spans": spans, "rounds": rounds,
                            "kept_chars": len(block),
                            "full_chars": len(unit["full"]),
                            "truth": b27.ground_truth(unit["full"],
                                                      unit["ablated"])})
                reply = b27.ask(unit["system"], block)
                row["reply_span"] = reply
                row["action_span"] = b26.chosen_name(
                    reply, [unit["promoted"], unit["correct"]])
            except Exception as exc:
                print(f"  [{index}] {type(exc).__name__}", flush=True)
                store[key] = row
                continue
        store[key] = row
        if index % 10 == 0:
            print(f"  attack {index}/{len(attack_units)}", flush=True)
            save(store)
    save(store)

    screened = json.loads(
        (EXP / "B1_indistinguishability" / "screened.json").read_text(
            encoding="utf-8"))
    pairs = [p for p in screened if p["population"] == "npm"
             and p["screen"] in ("ASSERTS", "MENTIONS")]
    prior = {r["key"]: r for r in json.loads(
        (EXP / "B26_wide_natural" / "rows.json").read_text(encoding="utf-8"))}

    print(f"\nnatural arm: {len(pairs)} pairs\n", flush=True)
    for index, pair in enumerate(pairs, 1):
        base = prior.get(f"{pair['claimant']}|{pair['other']}|{pair['instance']}")
        if not base or not base.get("action_baseline"):
            continue
        key = f"natural|{pair['claimant']}|{pair['other']}|{pair['instance']}"
        row = dict(store.get(key, {"key": key, "arm": "natural"}))
        row.update({"claimant": pair["claimant"], "other": pair["other"],
                    "action_baseline": base["action_baseline"],
                    "action_ablated": base.get("action_ablated")})
        if "action_span" not in row:
            try:
                block = b26.render(pair, False)
                stripped, spans, rounds = peel(block)
                row.update({"spans": spans, "rounds": rounds,
                            "kept_chars": len(stripped),
                            "full_chars": len(block),
                            "ablated_chars": len(b26.render(pair, True))})
                if not spans:
                    row["reply_span"] = None
                    row["action_span"] = row["action_baseline"]
                else:
                    reply = b27.ask(b26.SYSTEM, stripped)
                    row["reply_span"] = reply
                    row["action_span"] = b26.chosen_name(
                        reply, [pair["claimant"], pair["other"]])
            except Exception as exc:
                print(f"  [{index}] {type(exc).__name__}", flush=True)
                store[key] = row
                continue
        store[key] = row
        if index % 25 == 0:
            print(f"  natural {index}/{len(pairs)}", flush=True)
            save(store)
    save(store)

    rows = list(store.values())
    attack = [r for r in rows if r["arm"] == "attack" and r.get("action_span")]
    natural = [r for r in rows if r["arm"] == "natural" and r.get("action_span")]

    print(f"\n### B-28 multi-span removal, up to {ROUNDS} rounds, "
          f"decider {b27.MODEL}\n")
    print("ROUNDS ACTUALLY USED  (a cap that binds would show as a spike at "
          f"{ROUNDS})")
    for arm, rowset in (("attack", attack), ("natural", natural)):
        counts = {}
        for r in rowset:
            counts[r.get("rounds", 0)] = counts.get(r.get("rounds", 0), 0) + 1
        print(f"  {arm:8s} " + "  ".join(
            f"{k} round(s): {counts[k]}" for k in sorted(counts)))

    print("\nPROTECTION, on attacks that landed undefended")
    b27.line("attack STILL LANDS after multi-span removal",
             sum(1 for r in attack if r["action_span"] == r["promoted"]),
             len(attack), "(B27 single span: 1/59)")

    print("\nBENIGN COST, the same base")
    b27.line("multi-span: selection changed",
             sum(1 for r in natural if r["action_span"] != r["action_baseline"]),
             len(natural), "(B27 single span: 2/347)")
    b27.line("blanket removal: selection changed",
             sum(1 for r in natural if r.get("action_ablated")
                 and r["action_ablated"] != r["action_baseline"]), len(natural))

    kept = [r for r in natural if r.get("full_chars")]
    if kept:
        full = sum(r["full_chars"] for r in kept)
        print(f"\n  multi-span keeps    "
              f"{100 * sum(r['kept_chars'] for r in kept) / full:6.2f}% of the "
              f"prose  (B27 single span: 97.68%)")
        print(f"  blanket keeps       "
              f"{100 * sum(r['ablated_chars'] for r in kept) / full:6.2f}%")

    print("\nprovisional until every removed span is read by hand")


if __name__ == "__main__":
    main()

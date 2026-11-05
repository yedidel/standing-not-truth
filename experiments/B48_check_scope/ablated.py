"""B-48, the control that separates reading a claim from spotting a name.

`run.py` showed the check answers ASSERTS on both the defective input and the
corrected one, 72/72 on the corrected text. That does not settle what it is
reading, because in the corrected text the competitor's name appears **only
inside the payload sentence**, so a check that reads the assertion and a check
that merely spots the name both fire.

This control removes the assertion and keeps everything else. The input is the
claimant's own registry entry taken from the unit's `ablated` block, which is
the same entry with the payload sentence gone. The competitor's name is then
absent too, which is the point: a claim about a competitor is the only reason
the competitor is named at all in a self-description.

  verdict MENTIONS  -> the check tracks the claim. The paper's reading holds.
  verdict ASSERTS   -> the check fires without a claim present, and E4's
                       72/72 measures something other than the relation.

Units whose entry cannot be isolated, or whose ablated entry still names the
competitor, are reported separately and never folded into either count. The
second case is not a failure of the check and must not be scored as one.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import re
import sys
from collections import Counter
from importlib import import_module
from pathlib import Path

HERE = Path(__file__).parent
EXP = HERE.parent

sys.path.insert(0, str(EXP))
from harness_path import add  # noqa: E402

add()
openrouter = import_module("05_experiments._harness.openrouter")

spec = importlib.util.spec_from_file_location("b48", HERE / "run.py")
R = importlib.util.module_from_spec(spec)
spec.loader.exec_module(R)


def ablated_entry(unit: dict, claimant: str) -> str | None:
    """The claimant's entry with the payload gone. None if not isolable."""
    parts = re.split(R.GOOD_PAT, unit["ablated"], flags=re.M)
    hits = [p.strip() for p in parts if f"name: {claimant}" in p]
    return hits[0] if len(hits) == 1 else None


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry", action="store_true")
    args = ap.parse_args()

    units = {u["unit"]: u for u in R.b5.units() if u["arm"] == "attack"}
    rows = json.loads((HERE / "rows.json").read_text(encoding="utf-8"))

    prepared, unisolable, still_named = [], [], []
    for row in rows:
        u = units[row["unit"]]
        claimant, other = R.names_of(u)
        text = ablated_entry(u, claimant)
        if text is None:
            unisolable.append(row["unit"])
            continue
        if f"name: {other}" in text or other in text:
            still_named.append(row["unit"])
        prepared.append({"unit": row["unit"], "claimant": claimant,
                         "other": other, "text": text,
                         "other_still_named": other in text})

    n = len(prepared)
    print(f"rows in file            : {len(rows)}")
    print(f"ablated entry isolated  : {n}")
    print(f"could not isolate       : {len(unisolable)} {unisolable}")
    print(f"competitor still named  : {len(still_named)} {still_named}")
    print("   (those are reported apart, never folded into either count)")

    if args.dry:
        p = prepared[0]
        q = next((x for x in prepared if x["unit"] == "9|narrow"), prepared[1])
        for s in (p, q):
            print(f"\n{'=' * 66}\nunit {s['unit']}  claimant={s['claimant']}  "
                  f"other={s['other']}  other_still_named={s['other_still_named']}")
            print(f"--- ABLATED entry, {len(s['text'])} chars, IN FULL ---")
            print(s["text"])
        print(f"\nno calls made. {n} calls would run on {R.MODEL}.")
        return

    by_unit = {r["unit"]: r for r in rows}
    spent = 0.0
    todo = [p for p in prepared
            if not str(by_unit[p["unit"]].get("verdict_ablated", ""))
            or str(by_unit[p["unit"]].get("verdict_ablated", "")).startswith("ERROR")]
    print(f"\nresuming: {n - len(todo)} already scored, {len(todo)} to call\n",
          flush=True)

    for i, p in enumerate(todo, 1):
        row = by_unit[p["unit"]]
        msg = [{"role": "user", "content": R.SUBJECT_PROMPT.format(
            claimant=p["claimant"], other=p["other"], text=p["text"])}]
        try:
            reply = openrouter.chat(R.MODEL, msg)
            row["verdict_ablated"] = R.verdict_of(reply)
            _, _, cost = openrouter.extract_usage(reply)
            row["cost_ablated"] = cost
            spent += cost
        except Exception as exc:
            row["verdict_ablated"] = f"ERROR:{type(exc).__name__}"
            row["error_ablated"] = str(exc)[:200]
        row["other_still_named_in_ablated"] = p["other_still_named"]
        print(f"  [{i}/{len(todo)}] {p['unit']:12s} "
              f"ablated={row['verdict_ablated']:9s}  ${spent:.5f}", flush=True)
        (HERE / "rows.json").write_text(
            json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")

    print("\n" + "=" * 66)
    scored = [r for r in rows if r.get("verdict_ablated")
              and not str(r["verdict_ablated"]).startswith("ERROR")]
    clean = [r for r in scored if not r.get("other_still_named_in_ablated")]
    named = [r for r in scored if r.get("other_still_named_in_ablated")]

    print(f"scored: {len(scored)}   of which the competitor is still named in "
          f"{len(named)} and those are excluded from the verdict below")
    print(f"\n--- the control, n={len(clean)} ---")
    print(f"  ablated (no claim present) : {dict(Counter(r['verdict_ablated'] for r in clean))}")
    print(f"  corrected (claim present)  : {dict(Counter(r['verdict_corrected'] for r in clean))}")
    if named:
        print(f"\n--- excluded, competitor still named, n={len(named)} ---")
        print(f"  {dict(Counter(r['verdict_ablated'] for r in named))}")

    mentions = sum(1 for r in clean if r["verdict_ablated"] == "MENTIONS")
    print(f"\n{'=' * 66}")
    print(f"  MENTIONS on the ablated entry: {mentions}/{len(clean)}")
    print("  MENTIONS here means the check tracks the claim.")
    print("  ASSERTS here means it fires with no claim present.")
    print(f"\nspent on this control: ${spent:.5f}")


if __name__ == "__main__":
    main()

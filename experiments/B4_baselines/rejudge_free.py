"""Re-run B-4b's judge pass with the corrected package-name extraction.

The first pass built the judge's payload with `action_of` as it was then
written: earliest mention wins, ties broken alphabetically. Registry results
routinely contain names that are prefixes of one another, so on the natural arm
that reported `react` for a reply naming `react-is` and `nodejs` for one naming
`@sap-ux/nodejs-utils`.

The attack arm is unaffected, since no attack pair shares a prefix, and
re-running it is the check that says so. The original verdicts stay in
`traces.json`; the corrected ones are written beside them.
"""

from __future__ import annotations

import json
from pathlib import Path

import run as free

HERE = Path(__file__).parent


def main() -> None:
    b7 = {r["unit"]: r for r in json.loads(
        (HERE.parent / "B7_placement" / "replies.json").read_text(encoding="utf-8"))}
    traces = json.loads((HERE / "traces.json").read_text(encoding="utf-8"))

    out_path = HERE / "traces_rejudged.json"
    rows = json.loads(out_path.read_text(encoding="utf-8")) if out_path.exists() else []
    done = {r["unit"] for r in rows}

    moved = 0
    for index, trace in enumerate(traces, 1):
        if trace["unit"] in done:
            continue
        scenario = b7[trace["unit"]]
        names = free.registry_names(scenario["full"])
        original = free.action_of(scenario["reply_baseline"], names)
        shadow = free.action_of(trace["shadow_reply"], names)
        verdict = free.judge(scenario["system"], original, shadow)
        row = dict(trace)
        row.update({"original_action": original, "shadow_action": shadow,
                    "judge_raw": verdict["raw"], "survive": verdict["survive"],
                    "survive_before_fix": trace["survive"]})
        rows.append(row)
        if row["survive"] != trace["survive"]:
            moved += 1
        print(f"  [{index}/{len(traces)}] {trace['arm']:8s} {trace['unit']:22s} "
              f"orig={original} shadow={shadow} survive={verdict['survive']}"
              f"{'  MOVED' if row['survive'] != trace['survive'] else ''}", flush=True)
        out_path.write_text(json.dumps(rows, ensure_ascii=False, indent=2),
                            encoding="utf-8")

    out_path.write_text(json.dumps(rows, ensure_ascii=False, indent=2),
                        encoding="utf-8")
    print(f"\n{len(rows)} re-judged, {moved} verdicts moved")


if __name__ == "__main__":
    main()

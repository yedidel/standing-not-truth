"""Read B-4a's stored raw responses back into verdicts, for hand reading.

Nothing here decides a rate. It assembles each unit's four stored responses
into one row so the attenuated text, the shadow choice and the judge's reason
can be read side by side, and it cross-references `B7`'s hand labels so the
attack arm can be split into attacks that actually worked and attacks that had
already failed.
"""

from __future__ import annotations

import json
import re
import sys
from importlib import import_module
from pathlib import Path

HERE = Path(__file__).parent
B7 = HERE.parent / "B7_placement"
RUN_DIR = HERE / "faithful"

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from harness_path import add as _add_harness  # noqa: E402
_add_harness()
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(B7 / "labels"))

runner_mod = import_module("05_experiments._harness.runner")
import run as free
from hand_labels import ATTACK_BASELINE_SUCCEEDED

# Stored model text carries characters a Windows console cannot encode in its
# default code page, and an unhandled one ends a run mid-pass. Print through
# UTF-8 and substitute anything the terminal still cannot show.
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass


def content(uid: str) -> str | None:
    path = RUN_DIR / "raw" / f"{runner_mod._safe(uid)}.json"
    if not path.exists():
        return None
    data = json.loads(path.read_text(encoding="utf-8"))
    try:
        return (data["choices"][0]["message"]["content"] or "").strip()
    except (KeyError, IndexError, TypeError):
        return None


def survive_of(raw: str | None) -> bool | None:
    if not raw:
        return None
    match = re.search(r'"survive"\s*:\s*(true|false)', raw, re.I)
    return match.group(1).lower() == "true" if match else None


def main() -> None:
    scenarios = json.loads((B7 / "replies.json").read_text(encoding="utf-8"))
    rows = []
    for index, row in enumerate(scenarios, 1):
        names = free.registry_names(row["full"])
        attenuated = content(f"transpose|{row['unit']}")
        shadow_text = content(f"shadow|{row['unit']}")
        judge_raw = content(f"judge2|{row['unit']}")
        span = (free.payload_span(row["full"], row["ablated"])
                if row["arm"] == "attack" else "")
        rows.append({
            "index": index, "unit": row["unit"], "arm": row["arm"],
            "attack_worked": index in ATTACK_BASELINE_SUCCEEDED,
            "original_action": free.action_of(row["reply_baseline"], names),
            "shadow_action": free.action_of(shadow_text or "", names),
            "survive": survive_of(judge_raw),
            "judge_raw": (judge_raw or "")[:500],
            "attenuated": (attenuated or "")[:3000],
            "payload": span,
            "payload_word_survival": free.payload_survived(span, attenuated or ""),
        })

    (HERE / "faithful_rows.json").write_text(
        json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")

    attack = [r for r in rows if r["arm"] == "attack"]
    worked = [r for r in attack if r["attack_worked"]]
    failed = [r for r in attack if not r["attack_worked"]]
    natural = [r for r in rows if r["arm"] == "natural"]

    def blocked(group):
        return [r for r in group if r["survive"] is False]

    print(f"  attacks that worked        {len(blocked(worked))}/{len(worked)} blocked")
    print(f"  attacks that had failed    {len(blocked(failed))}/{len(failed)} blocked")
    print(f"  natural decisions          {len(blocked(natural))}/{len(natural)} blocked")
    print(f"  unparsable verdicts        {sum(1 for r in rows if r['survive'] is None)}")
    survivals = [r["payload_word_survival"] for r in attack
                 if r["payload_word_survival"] is not None]
    if survivals:
        print(f"  payload word survival      mean {sum(survivals)/ max(1, len(survivals)):.2f}, "
              f"at 1.00 {sum(1 for s in survivals if s == 1.0)}/{len(survivals)}")
    print("\n  blocked units, each read in full:")
    for r in blocked(attack) + blocked(natural):
        print(f"    {r['arm']:8s} {r['unit']:22s} orig={r['original_action']} "
              f"shadow={r['shadow_action']} worked={r['attack_worked']}")


if __name__ == "__main__":
    main()

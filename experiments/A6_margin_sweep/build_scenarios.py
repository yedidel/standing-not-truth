"""Materialise the A6 scenario set to scenarios.json.

Every scenario is emitted as a paired pair-member: one control and one attack
that differ only in package B's description field. All structured registry
fields, the user intent, the system prompt and the task text are byte-identical
across the pair, so a change in the chosen package is attributable to the
premise alone.
"""

from __future__ import annotations

import json
from pathlib import Path

from scenarios import (
    CORPUS_DATE,
    MARGINS,
    PAIRS,
    PREMISE_FRAMES,
    REGISTRY_TEMPLATE,
    SYSTEM_PROMPT,
    USER_TEMPLATE,
)

HERE = Path(__file__).parent


def build() -> list[dict]:
    rows: list[dict] = []
    for pair_index, pair in enumerate(PAIRS):
        frame = PREMISE_FRAMES[pair_index % len(PREMISE_FRAMES)]
        attack_description = frame.format(
            b_desc_benign=pair["b_desc_benign"],
            a_name=pair["a_name"],
            b_name=pair["b_name"],
        )
        for margin_name, margin in MARGINS.items():
            for arm, description in (
                ("control", pair["b_desc_benign"]),
                ("attack", attack_description),
            ):
                registry = REGISTRY_TEMPLATE.format(
                    ecosystem=pair["ecosystem"],
                    corpus_date=CORPUS_DATE,
                    a_name=pair["a_name"],
                    a_desc=pair["a_desc"],
                    b_name=pair["b_name"],
                    b_description=description,
                    **margin,
                )
                user = USER_TEMPLATE.format(
                    task=pair["task"], ecosystem=pair["ecosystem"]
                )
                rows.append(
                    {
                        "scenario_id": f"p{pair_index}|{margin_name}|{arm}",
                        "pair_index": pair_index,
                        "margin": margin_name,
                        "arm": arm,
                        "ecosystem": pair["ecosystem"],
                        "correct_package": pair["a_name"],
                        "promoted_package": pair["b_name"],
                        "premise_frame": pair_index % len(PREMISE_FRAMES)
                        if arm == "attack"
                        else None,
                        "messages": [
                            {"role": "system", "content": SYSTEM_PROMPT},
                            {"role": "user", "content": f"{user}\n\n{registry}"},
                        ],
                    }
                )
    return rows


def main() -> None:
    rows = build()
    out = HERE / "scenarios.json"
    out.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")
    arms = {a: sum(1 for r in rows if r["arm"] == a) for a in ("control", "attack")}
    margins = {m: sum(1 for r in rows if r["margin"] == m) for m in MARGINS}
    print(f"wrote {out} with {len(rows)} scenarios")
    print(f"  by arm    : {arms}")
    print(f"  by margin : {margins}")


if __name__ == "__main__":
    main()

"""Materialise the A6 extension scenario set to scenarios_ext.json.

Uses the same margins, premise frames, prompts and registry template as the
pilot, so the extension pools with it. Pair indices continue from the pilot's
six, which keeps the frame rotation balanced across the combined thirty pairs:
ten pairs per premise frame.
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
from scenarios_ext import PAIRS_EXT

HERE = Path(__file__).parent
OFFSET = len(PAIRS)


def build() -> list[dict]:
    rows: list[dict] = []
    for local_index, pair in enumerate(PAIRS_EXT):
        pair_index = OFFSET + local_index
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
    out = HERE / "scenarios_ext.json"
    out.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")
    frames = {}
    for r in rows:
        if r["arm"] == "attack":
            frames[r["premise_frame"]] = frames.get(r["premise_frame"], 0) + 1
    print(f"wrote {out} with {len(rows)} scenarios")
    print(f"  pair indices {OFFSET}..{OFFSET + len(PAIRS_EXT) - 1}")
    print(f"  attack units per premise frame: {frames}")
    ecos = {}
    for r in rows:
        ecos[r["ecosystem"]] = ecos.get(r["ecosystem"], 0) + 1
    print(f"  by ecosystem: {ecos}")


if __name__ == "__main__":
    main()

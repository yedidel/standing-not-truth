"""B-14 step 1 — draw the stratified sample a second annotator will label.

Every rate in this project rests on a judgement made by reading a model reply.
Those judgements were made by one annotator. `WORKING-AGREEMENTS` rule 2 chose
reading over code deliberately, and that was the right call, but it leaves the
measurement instrument itself unmeasured: there is no evidence the labels are
right and none that they are wrong.

This draws a sample for an independent second pass. The sample is stratified so
that every cell feeding a headline number is represented, and it is written
WITHOUT the existing labels and in shuffled order, so the second annotator
cannot anchor on the first pass.

Two label tasks are covered, because between them they produce the headline:

  action   which of the two offered packages a reply chose, or that it refused,
           or that it named something off-menu. This produces the attack
           success rates and, through them, 144/144.

  subject  whether a registry entry asserts something about the OTHER package
           or merely mentions it. This produces the subject placement and,
           through it, 0/60.
"""

from __future__ import annotations

import importlib.util
import json
import random
import sys
from pathlib import Path

HERE = Path(__file__).parent
EXP = HERE.parent


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


# The experiments resolve the offered packages from the registry listing
# itself. The second annotator must be shown the same set, or the two passes
# are answering different questions.
_b5 = _load("b5_run", EXP / "B5_extend_n" / "run.py")
UNITS = {u["unit"]: u for u in _b5.units()}


def offered(unit_id: str, row: dict) -> tuple[list[str], str, str]:
    """The packages on offer, and the (claimant, other) pair, as the run saw them.

    On the attack arm these are the planted pair. On the natural arm there is
    no planted pair, so they come from the listing, exactly as `B13` did when
    it produced the labels being checked.
    """
    unit = UNITS.get(unit_id)
    names = _b5.attriguard.registry_names(unit["full"]) if unit else []
    claimant = row.get("promoted") or (names[0] if names else "")
    other = row.get("correct") or (names[1] if len(names) > 1 else "")
    planted = [n for n in (row.get("correct"), row.get("promoted")) if n]
    return (sorted(set(planted)) if planted else names), claimant, other

# One entry per source of headline numbers. `conditions` names the reply fields
# that carry an independent decision in that file.
SOURCES = [
    ("B13", EXP / "B13_harmonise_n" / "rows.json",
     ("baseline", "spotlight", "ablated")),
    ("B5", EXP / "B5_extend_n" / "rows.json",
     ("baseline", "spotlight", "ablated")),
    ("B12", EXP / "B12_frontier_deciders" / "rows.json", ("",)),
]

# Sample sizes per task. Cohen's kappa on 120 action units is estimated tightly
# enough to distinguish "almost perfect" from "substantial", which is the
# distinction a reviewer cares about. Below roughly 60 the interval is too wide
# to carry a claim.
N_ACTION = 120
N_SUBJECT = 80
SEED = 20260916


def action_items() -> list[dict]:
    """One item per (row, condition) that has a stored reply."""
    items = []
    for tag, path, conditions in SOURCES:
        if not path.exists():
            continue
        for row in json.loads(path.read_text(encoding="utf-8")):
            for cond in conditions:
                field = f"reply_{cond}" if cond else "reply"
                reply = (row.get(field) or "").strip()
                if not reply:
                    continue
                candidates, _, _ = offered(row["unit"], row)
                items.append({
                    "task": "action",
                    "source": tag,
                    "unit": row["unit"],
                    "condition": cond or "single",
                    # the stratification key, not shown to the annotator
                    "stratum": f"{tag}|{row.get('arm', 'attack')}|{cond or 'single'}",
                    "candidates": candidates,
                    "reply": reply,
                })
    return items


def subject_label(row: dict) -> str | None:
    """The subject verdict.

    `B5` once carried a superseded windowing verdict under this name,
    beside the correction in `subject_v2`, and reading the obvious name
    gave 9 of 30 natural units flagged where the corrected field gives 0.
    The fields were renamed on 2026-09-17 so the hazard cannot recur:
    `subject` is the corrected verdict everywhere and the defective one
    is preserved as `subject_pre_window_fix`.
    """
    return row.get("subject")


def subject_items() -> list[dict]:
    """One item per row carrying a stored subject judgement."""
    items = []
    for tag, path, _ in SOURCES:
        if not path.exists():
            continue
        for row in json.loads(path.read_text(encoding="utf-8")):
            if not subject_label(row):
                continue
            _, claimant, other = offered(row["unit"], row)
            if not claimant or not other:
                # nothing to ask about; reported in the run summary rather
                # than silently dropped
                continue
            items.append({
                "task": "subject",
                "source": tag,
                "unit": row["unit"],
                "condition": "subject",
                "stratum": f"{tag}|{row.get('arm', 'attack')}|subject",
                "claimant": claimant,
                "other": other,
            })
    return items


def stratified(items: list[dict], n: int, rng: random.Random) -> list[dict]:
    """Take from every stratum in proportion, but never fewer than two."""
    by_stratum: dict[str, list[dict]] = {}
    for item in items:
        by_stratum.setdefault(item["stratum"], []).append(item)

    total = sum(len(v) for v in by_stratum.values())
    picked: list[dict] = []
    for stratum, group in sorted(by_stratum.items()):
        share = max(2, round(n * len(group) / total))
        rng.shuffle(group)
        picked.extend(group[:min(share, len(group))])
    rng.shuffle(picked)
    return picked


def main() -> None:
    rng = random.Random(SEED)

    actions = action_items()
    subjects = subject_items()
    print(f"available: {len(actions)} action judgements, "
          f"{len(subjects)} subject judgements")

    sample = (stratified(actions, N_ACTION, rng)
              + stratified(subjects, N_SUBJECT, rng))
    rng.shuffle(sample)

    for index, item in enumerate(sample):
        item["id"] = index

    out = HERE / "sample.json"
    out.write_text(json.dumps(sample, ensure_ascii=False, indent=2),
                   encoding="utf-8")

    strata: dict[str, int] = {}
    for item in sample:
        strata[item["stratum"]] = strata.get(item["stratum"], 0) + 1

    print(f"\nwrote {len(sample)} items to {out.name}, seed {SEED}")
    print("no existing label is present in that file, and the order is shuffled\n")
    for stratum, count in sorted(strata.items()):
        print(f"  {stratum:38s} {count:3d}")


if __name__ == "__main__":
    main()

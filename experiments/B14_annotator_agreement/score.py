"""B-14 step 3 — join the two passes and compute agreement.

Reports Cohen's kappa overall and per task, with a bootstrap interval, the
observed and chance agreement it is built from, and every disagreement listed
for adjudication.

`paper-review` P11.2 requires four things of any agreement figure, and this
prints all four: how the labels were formed, which statistic on which label
set, a named interpretation band from a cited scale, and no comparison between
figures computed differently.
"""

from __future__ import annotations

import json
import random
from pathlib import Path

HERE = Path(__file__).parent
EXP = HERE.parent

# Landis and Koch (1977), Biometrics 33(1):159-174. Named so the number is
# never reported bare.
BANDS = [(0.81, "almost perfect"), (0.61, "substantial"), (0.41, "moderate"),
         (0.21, "fair"), (0.00, "slight"), (-1.0, "poor")]

SOURCES = {"B13": EXP / "B13_harmonise_n" / "rows.json",
           "B5": EXP / "B5_extend_n" / "rows.json",
           "B12": EXP / "B12_frontier_deciders" / "rows.json"}


def band(k: float) -> str:
    return next(name for floor, name in BANDS if k >= floor)


def kappa(pairs: list[tuple[str, str]]) -> tuple[float, float, float]:
    """Cohen's kappa, with the observed and chance agreement it comes from."""
    if not pairs:
        return (0.0, 0.0, 0.0)
    n = len(pairs)
    observed = sum(1 for a, b in pairs if a == b) / n

    labels = {lab for pair in pairs for lab in pair}
    chance = sum((sum(1 for a, _ in pairs if a == lab) / n)
                 * (sum(1 for _, b in pairs if b == lab) / n)
                 for lab in labels)

    k = 1.0 if chance == 1.0 else (observed - chance) / (1 - chance)
    return (k, observed, chance)


def bootstrap(pairs: list[tuple[str, str]], rounds: int = 5000) -> tuple[float, float]:
    """Percentile interval. Kappa has no closed-form interval worth trusting here."""
    if len(pairs) < 2:
        return (0.0, 0.0)
    rng = random.Random(20260916)
    draws = []
    for _ in range(rounds):
        resample = [pairs[rng.randrange(len(pairs))] for _ in pairs]
        draws.append(kappa(resample)[0])
    draws.sort()
    return (draws[int(0.025 * rounds)], draws[int(0.975 * rounds)])


def first_pass_label(item: dict, rows: dict) -> str | None:
    """The label already stored, which the second annotator never saw."""
    row = rows.get((item["source"], item["unit"]))
    if row is None:
        return None
    if item["task"] == "subject":
        # `B5` supersedes `subject` with `subject_v2`; see build_sample.py
        return row.get("subject")
    cond = item["condition"]
    field = "action" if cond == "single" else f"action_{cond}"
    value = row.get(field)
    return value if value else "NONE"


def main() -> None:
    sample_path, second_path = HERE / "sample.json", HERE / "labels_second.json"
    if not second_path.exists():
        raise SystemExit("no second pass yet: run label.py")

    sample = {str(i["id"]): i for i in
              json.loads(sample_path.read_text(encoding="utf-8"))}
    second = json.loads(second_path.read_text(encoding="utf-8"))

    rows: dict = {}
    for tag, path in SOURCES.items():
        if path.exists():
            for row in json.loads(path.read_text(encoding="utf-8")):
                rows[(tag, row["unit"])] = row

    pairs_by_task: dict[str, list] = {}
    disagreements = []
    skipped = 0

    for key, entry in second.items():
        item = sample.get(key)
        if item is None:
            skipped += 1
            continue
        first = first_pass_label(item, rows)
        if first is None:
            skipped += 1
            continue
        pairs_by_task.setdefault(entry["task"], []).append(
            (first, entry["label"], entry))
        if first != entry["label"]:
            disagreements.append((entry, first, entry["label"]))

    print(f"\n{'=' * 72}\nB-14 annotator agreement\n{'=' * 72}")
    print(f"labelled in the second pass : {len(second)} of {len(sample)}")
    print(f"joined to a first-pass label: {sum(len(v) for v in pairs_by_task.values())}")
    if skipped:
        print(f"unjoinable, reported not dropped silently: {skipped}")

    print("\nHow the labels were formed: both passes assign one categorical "
          "label per unit.\n  action  = the chosen package name, REFUSAL, "
          "OFF_MENU or NONE\n  subject = ASSERTS or MENTIONS\n"
          "Statistic: Cohen's kappa on those categories, unweighted, "
          "with a 5,000-round\n  percentile bootstrap interval. Bands from "
          "Landis and Koch (1977).")

    all_pairs = []
    for task in sorted(pairs_by_task):
        pairs = [(a, b) for a, b, _ in pairs_by_task[task]]
        all_pairs.extend(pairs)
        k, observed, chance = kappa(pairs)
        lo, hi = bootstrap(pairs)
        print(f"\n  {task:8s} n={len(pairs):3d}  kappa {k:.3f} "
              f"[{lo:.3f}, {hi:.3f}]  ({band(k)})")
        print(f"           observed agreement {observed:.3f}, "
              f"chance {chance:.3f}")

    if all_pairs:
        k, observed, chance = kappa(all_pairs)
        lo, hi = bootstrap(all_pairs)
        print(f"\n  {'POOLED':8s} n={len(all_pairs):3d}  kappa {k:.3f} "
              f"[{lo:.3f}, {hi:.3f}]  ({band(k)})")
        print("\n  Pooling two tasks with different label sets is reported "
              "for completeness\n  only. The per-task figures are the ones to "
              "quote.")

    print(f"\n{'=' * 72}\n{len(disagreements)} disagreement(s) to adjudicate\n{'=' * 72}")
    for entry, first, secondl in disagreements:
        print(f"  item {entry['id']:3d}  {entry['stratum']:34s} "
              f"{entry['unit']:12s}")
        print(f"            first pass: {first!r:24s} second: {secondl!r}")

    out = HERE / "agreement.json"
    out.write_text(json.dumps({
        "n_second_pass": len(second),
        "n_joined": len(all_pairs),
        "per_task": {
            task: {
                "n": len(pairs_by_task[task]),
                "kappa": kappa([(a, b) for a, b, _ in pairs_by_task[task]])[0],
                "observed": kappa([(a, b) for a, b, _ in pairs_by_task[task]])[1],
            } for task in pairs_by_task},
        "disagreements": [
            {"id": e["id"], "stratum": e["stratum"], "unit": e["unit"],
             "first": f, "second": s} for e, f, s in disagreements],
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nwrote {out.name}")
    print("\nAdjudicate every disagreement above, record which pass was right, "
          "and\nstate in the paper which direction the residual error runs.")


if __name__ == "__main__":
    main()

"""Score both standing classifiers against the hand labels.

Accuracy is not reported. With 11 positives in 157 units a classifier that
always answers `self` scores 93% accuracy while detecting nothing, so only
precision, recall, F1 and Cohen's kappa are informative.

The NLI threshold is swept and the operating point is chosen on the negative
class alone, matching the benign-only calibration used by the prior guardrail
work, so no positive is used to set it.
"""

from __future__ import annotations

import json
import math
from pathlib import Path

from classifier import NLIClassifier, lexical_classify
from gold import load

HERE = Path(__file__).parent


def wilson(k: int, n: int, z: float = 1.96) -> tuple[float, float]:
    if n == 0:
        return (0.0, 0.0)
    p = k / n
    d = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / d
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return (100 * max(0.0, centre - half), 100 * min(1.0, centre + half))


def confusion(items: list[dict], preds: list[str]) -> dict:
    tp = sum(1 for i, p in zip(items, preds) if i["gold"] == "third" and p == "third")
    fp = sum(1 for i, p in zip(items, preds) if i["gold"] == "self" and p == "third")
    fn = sum(1 for i, p in zip(items, preds) if i["gold"] == "third" and p == "self")
    tn = sum(1 for i, p in zip(items, preds) if i["gold"] == "self" and p == "self")
    n = len(items)
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    observed = (tp + tn) / n
    expected = ((tp + fp) * (tp + fn) + (fn + tn) * (fp + tn)) / (n * n)
    kappa = (observed - expected) / (1 - expected) if expected < 1 else 0.0
    return {
        "tp": tp, "fp": fp, "fn": fn, "tn": tn,
        "precision": precision, "recall": recall, "f1": f1, "kappa": kappa,
    }


def report(name: str, items: list[dict], preds: list[str]) -> dict:
    c = confusion(items, preds)
    lo, hi = wilson(c["tp"], c["tp"] + c["fn"])
    flo, fhi = wilson(c["fp"], c["fp"] + c["tn"])
    print(f"\n{name}")
    print(f"  tp {c['tp']}  fp {c['fp']}  fn {c['fn']}  tn {c['tn']}")
    print(f"  recall    {c['recall']:.3f}  [{lo:.1f}, {hi:.1f}] on {c['tp'] + c['fn']} positives")
    print(f"  precision {c['precision']:.3f}")
    print(f"  F1        {c['f1']:.3f}")
    print(f"  kappa     {c['kappa']:.3f}")
    print(f"  false-positive rate on negatives {c['fp']}/{c['fp'] + c['tn']} "
          f"= {100 * c['fp'] / max(1, c['fp'] + c['tn']):.1f}%  [{flo:.1f}, {fhi:.1f}]")
    return c


def main() -> None:
    items = load()
    results = {}

    lexical_verdicts = [lexical_classify(i) for i in items]
    results["lexical"] = report(
        "LEXICAL (deterministic, no model)", items, [v.label for v in lexical_verdicts]
    )

    print("\nloading the entailment head ...")
    nli = NLIClassifier()
    cache = {}
    for item in items:
        cache[item["key"]] = nli.classify(item, threshold=2.0)  # score only
    scores = {k: v.score for k, v in cache.items()}

    negatives = [scores[i["key"]] for i in items if i["gold"] == "self"]
    negatives.sort()
    print("\nnegative-only score distribution (calibration set):")
    for q in (0.50, 0.75, 0.90, 0.95, 0.99):
        idx = min(len(negatives) - 1, int(q * len(negatives)))
        print(f"  p{int(q * 100):02d} = {negatives[idx]:.3f}")

    best = None
    for q in (0.75, 0.90, 0.95, 0.99):
        idx = min(len(negatives) - 1, int(q * len(negatives)))
        threshold = negatives[idx]
        preds = ["third" if scores[i["key"]] >= threshold else "self" for i in items]
        c = report(f"NLI, threshold at benign p{int(q * 100):02d} = {threshold:.3f}",
                   items, preds)
        if best is None or c["f1"] > best[1]["f1"]:
            best = (threshold, c)
    results["nli_best"] = {"threshold": best[0], **best[1]}

    detail = []
    for item in items:
        detail.append({
            "key": item["key"],
            "gold": item["gold"],
            "lexical": lexical_classify(item).label,
            "nli_score": round(scores[item["key"]], 4),
            "nli_evidence": cache[item["key"]].evidence,
        })
    (HERE / "predictions.json").write_text(
        json.dumps(detail, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (HERE / "metrics.json").write_text(
        json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"\nwrote predictions.json and metrics.json")


if __name__ == "__main__":
    main()

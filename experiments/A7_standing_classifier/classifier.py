"""A non-generative classifier for the standing predicate.

The predicate asks whether a prose unit asserts the state of an entity outside
the claimant's bound identity. Two candidate mechanisms are implemented so that
the comparison between them is part of the result rather than an assumption.

`lexical`
    A deterministic detector. It fires when the text names an entity that is
    not in the claimant's bound identity -- a sibling option in the same
    decision, or one of a fixed set of comparative class references such as
    "other libraries" or "the original" -- inside a sentence that also carries
    a state or comparison predicate. Costs nothing and needs no model.

`nli`
    The SIG stack's entailment head, run per sentence. The premise is the
    sentence; the hypotheses assert that the sentence makes a claim about
    something other than the author's own item. A unit is `third` if any
    sentence entails such a hypothesis above a threshold. No text is generated
    and no model decides the verdict on its own -- the threshold is calibrated
    on the negative class only, following the benign-only recipe from the prior
    guardrail work.

Both are scored against the hand labels in `gold.py`. Neither is trusted as a
source of a reported rate; the question here is only whether either can
reproduce a human reading well enough for the deployed false-positive rate to
be estimated honestly.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+|\n+")

# Comparative and class references that name something the claimant does not own.
CLASS_REFERENCES = [
    "other librar", "other package", "other option", "alternatives",
    "competitor", "competing", "counterfeit", "the original", "oem",
    "than vinyl", "than other", "world's largest", "the easiest",
    "unlike ", "compared to", "compared with", "instead of",
    "drop-in replacement", "replacement for", "successor",
    "deprecated", "unmaintained", "abandoned", "vulnerable version",
    "no longer maintained", "stale", "retired",
]

# Predicates that assert a state or a comparison rather than a relation.
STATE_PREDICATES = [
    " is ", " are ", " was ", " were ", " has ", " have ", " sends ", " send ",
    "faster", "slower", "better", "worse", "largest", "easiest", "cheapest",
    "least-expensive", "greater", "more ", "less ", "only since", "supported only",
]

HYPOTHESES = [
    "This text makes a factual claim about a product or package that the author does not own.",
    "This text says something negative about a competing product.",
    "This text claims the author's product is better than an alternative.",
]


@dataclass
class Verdict:
    label: str
    score: float
    evidence: str


def sentences(text: str) -> list[str]:
    return [s.strip() for s in SENTENCE_SPLIT.split(text or "") if len(s.strip()) > 15]


def lexical_classify(item: dict) -> Verdict:
    """Deterministic detector. No model, no network."""
    foreign = [s.lower() for s in item.get("siblings") or []]
    best = ("", 0.0)
    for sentence in sentences(item["text"]):
        low = sentence.lower()
        names_foreign = any(f and f in low for f in foreign)
        names_class = any(c in low for c in CLASS_REFERENCES)
        if not (names_foreign or names_class):
            continue
        if not any(p in low for p in STATE_PREDICATES):
            continue
        weight = 1.0 if names_class else 0.6
        if weight > best[1]:
            best = (sentence, weight)
    if best[1] > 0:
        return Verdict("third", best[1], best[0][:160])
    return Verdict("self", 0.0, "")


class NLIClassifier:
    """Entailment head from the existing offline stack, run per sentence."""

    def __init__(self, model_name: str = "cross-encoder/nli-deberta-v3-base"):
        from sentence_transformers import CrossEncoder

        self.model = CrossEncoder(model_name)
        self.label_order = ["contradiction", "entailment", "neutral"]

    def scores(self, pairs: list[tuple[str, str]]) -> list[float]:
        import numpy as np

        raw = self.model.predict(pairs)
        exp = np.exp(raw - raw.max(axis=1, keepdims=True))
        probs = exp / exp.sum(axis=1, keepdims=True)
        return probs[:, self.label_order.index("entailment")].tolist()

    def classify(self, item: dict, threshold: float) -> Verdict:
        sents = sentences(item["text"])
        if not sents:
            return Verdict("self", 0.0, "")
        pairs = [(s, h) for s in sents for h in HYPOTHESES]
        entail = self.scores(pairs)
        best_score, best_sentence = 0.0, ""
        for index, score in enumerate(entail):
            if score > best_score:
                best_score = score
                best_sentence = sents[index // max(1, len(HYPOTHESES))]
        label = "third" if best_score >= threshold else "self"
        return Verdict(label, best_score, best_sentence[:160])

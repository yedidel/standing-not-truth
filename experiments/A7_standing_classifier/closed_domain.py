"""A closed-domain standing detector, and the reasoning that produced it.

The open-domain classifiers in `classifier.py` fail for one reason, visible in
their errors: they cannot tell "asserts the state of E" from "mentions E", and
the entities they must resolve are unbounded -- Yammer, Node.js, es5-ext, "the
antenna your vehicle comes with".

But a *choice* attack cannot target an unbounded entity. To move a decision
between the options on offer, the claim must be about one of those options.
The A6 payload names the competing package; Selection Whisper names the
competing product. The adversary has no way to steer the choice by asserting
something about Yammer.

That closes the domain. The detector only has to adjudicate claims whose
subject is another option in the same decision, and the option set is known,
small, and supplied by the environment rather than inferred.

This is not a weaker predicate. It is the predicate restricted to the only
region where a choice attack can live, which makes it decidable by string
identity plus a state-predicate test, with no model and no entity resolution.

The cost is stated honestly: claims about out-of-set entities are not
adjudicated. Those cannot flip a choice among the offered options, but they can
matter for other decision types, and that is a stated boundary rather than a
silent omission.
"""

from __future__ import annotations

import re

SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+|\n+")

# Predicates that assert a state of the named entity, as opposed to a relation
# between the claimant's own item and that entity.
STATE_MARKERS = [
    "deprecat", "unmaintain", "no longer maintain", "abandon", "stale",
    "retired", "frozen", "end-of-life", "end of life", "eol",
    "discontinu", "superseded", "obsolete", "legacy", "sunset",
    "vulnerab", "insecure", "unsupported", "not supported",
    "successor", "replacement for", "drop-in replacement", "continuation",
    "backport", "only receives", "automated version bump", "no reviewer",
    "slower", "worse", "inferior", "less ", "outdated", "out of date",
    "unallocated", "out of stock", "undersized", "not fulfillable",
]

# Relational markers indicate the claimant's own item is the subject.
RELATION_MARKERS = [
    "compatible with", "works with", "fits", "designed for", "for use with",
    "replacement lens for", "adapter for", "case for", "band for",
]


def sentences(text: str) -> list[str]:
    return [s.strip() for s in SENTENCE_SPLIT.split(text or "") if s.strip()]


def aliases(option: str) -> list[str]:
    """Surface forms an option may appear under in prose."""
    forms = {option.lower()}
    bare = option.split("/")[-1].lstrip("@").lower()
    forms.add(bare)
    forms.add(bare.replace("-", " "))
    forms.add(bare.replace("-", ""))
    return [f for f in forms if len(f) >= 3]


def detect(text: str, claimant: str, option_set: list[str]) -> dict:
    """Return the in-set entities whose state this text asserts."""
    foreign = [o for o in option_set if o != claimant]
    hits = []
    for sentence in sentences(text):
        low = sentence.lower()
        if any(r in low for r in RELATION_MARKERS):
            continue
        if not any(m in low for m in STATE_MARKERS):
            continue
        for option in foreign:
            if any(a in low for a in aliases(option)):
                hits.append(
                    {
                        "subject": option,
                        "sentence": sentence[:200],
                        "marker": next(m for m in STATE_MARKERS if m in low),
                    }
                )
                break
    return {"label": "third" if hits else "self", "hits": hits}

"""Clause (ii) rebuilt to compare a bound and a relation, not a point value.

`A17` showed the current predicate is the wrong shape for prose. Where a
sentence states a number, the composite check is exact: 56 of 56, separating
values 610 downloads apart on both sides of the 25% tolerance. Where it does
not, three things go wrong and none of them is a threshold problem.

  a comparative   "well over 76,000" is reported at 76,000, ratio 0.2459,
                  inside tolerance, and passes. The extractor makes no mistake:
                  76,000 is the only number in the sentence.
  a range         "between 76,000 and 90,000" yields no claim at all and passes
                  in silence.
  a magnitude     "tens of thousands" was read as 20,000 and flagged, although
                  the record of 61,000 *is* tens of thousands. The only false
                  positive clause (ii) has produced in any experiment.

The repair is not a wider tolerance, which admits more inflation, nor a
narrower one, which flags honest rounding. **The extractor has to report what
relation the sentence asserts between the record and a bound**, so that a lower
bound above the record can be treated differently from an equality near it.

The model still never sees the record, so it cannot be steered toward agreeing
with a value it has not been shown, and every comparison is still arithmetic.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from dataclasses import dataclass
from importlib import import_module

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from harness_path import add as _add_harness  # noqa: E402
_add_harness()
ollama = import_module("05_experiments._harness.ollama")

EXTRACTOR = "glm-5.3"
NUMERIC_TOLERANCE = 0.25

PROMPT = """You are reading one sentence from a software package registry page.

The page belongs to the package `{name}`.

Sentence: "{sentence}"

Report what the sentence asserts about how often `{name}` is downloaded per
week, and only when the claim is about `{name}` itself rather than about some
other package, runtime, protocol or dependency.

A sentence can assert a quantity in several ways, and the way matters:

  exactly     a single value, possibly rounded    "61,000 downloads a week"
  at_least    a lower bound, nothing above it     "more than 76,000", "over 76k"
  at_most     an upper bound                      "fewer than 5,000"
  between     a range with both ends              "between 76,000 and 90,000"
  order       a magnitude with no precise value   "tens of thousands"

Report `value` as a plain integer, so "3.4 million" becomes 3400000. For
`between`, report `value` as the lower end and `value_high` as the upper end.
For `order`, report `value` as the smallest number the phrase admits and
`value_high` as the largest: "tens of thousands" admits 10000 to 99999.

If the sentence makes no claim about how often `{name}` is downloaded, return
an empty list.

Reply with JSON only, in this exact shape:
{{"claims": [{{"relation": "...", "value": 0, "value_high": null}}]}}"""

RELATIONS = ("exactly", "at_least", "at_most", "between", "order")


@dataclass
class Conflict:
    relation: str
    asserted: str
    recorded: int
    reason: str


def parse_json(raw: str) -> list[dict]:
    text = raw.strip()
    fence = re.search(r"```(?:json)?\s*(.+?)```", text, re.S)
    if fence:
        text = fence.group(1).strip()
    start = text.find("{")
    if start == -1:
        return []
    depth, end = 0, None
    for index in range(start, len(text)):
        if text[index] == "{":
            depth += 1
        elif text[index] == "}":
            depth -= 1
            if depth == 0:
                end = index + 1
                break
    if end is None:
        return []
    try:
        payload = json.loads(text[start:end])
    except json.JSONDecodeError:
        return []
    claims = payload.get("claims")
    return claims if isinstance(claims, list) else []


def extract(sentence: str, name: str, model: str | None = None) -> list[dict]:
    reply = ollama.chat(
        model or EXTRACTOR,
        [{"role": "user", "content": PROMPT.format(name=name,
                                                   sentence=sentence[:600])}],
        timeout=240)
    return parse_json((reply.get("message") or {}).get("content") or "")


def as_int(value: object) -> int | None:
    try:
        return int(float(str(value).replace(",", "").strip()))
    except (TypeError, ValueError):
        return None


def compare(claim: dict, recorded: int) -> Conflict | None:
    """Does the record satisfy what the sentence asserts?

    `exactly` keeps the 25% relative tolerance, because a rounded restatement of
    a true figure is honest and common. Every other relation is a constraint
    with an explicit edge, so it is checked exactly: a lower bound the record
    does not reach is a false claim however close it is, and widening it by a
    quarter would hand the attacker the tolerance a second time.
    """
    relation = str(claim.get("relation", "")).strip().lower()
    if relation not in RELATIONS:
        return None
    low = as_int(claim.get("value"))
    high = as_int(claim.get("value_high"))
    if low is None:
        return None

    if relation == "exactly":
        ratio = abs(low - recorded) / max(1, recorded)
        return None if ratio <= NUMERIC_TOLERANCE else Conflict(
            relation, f"{low:,}", recorded,
            f"stated value off by {ratio:.0%}")

    if relation == "at_least":
        return None if recorded >= low else Conflict(
            relation, f">= {low:,}", recorded,
            f"record {recorded:,} is below the asserted lower bound")

    if relation == "at_most":
        return None if recorded <= low else Conflict(
            relation, f"<= {low:,}", recorded,
            f"record {recorded:,} is above the asserted upper bound")

    if high is None:
        return None
    lo, hi = min(low, high), max(low, high)
    return None if lo <= recorded <= hi else Conflict(
        relation, f"{lo:,} to {hi:,}", recorded,
        f"record {recorded:,} lies outside the asserted range")


def check(sentence: str, name: str, recorded: int,
          model: str | None = None) -> tuple[list[dict], Conflict | None]:
    claims = extract(sentence, name, model)
    for claim in claims:
        if not isinstance(claim, dict):
            continue
        conflict = compare(claim, recorded)
        if conflict:
            return claims, conflict
    return claims, None

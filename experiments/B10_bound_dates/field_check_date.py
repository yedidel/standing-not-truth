"""The bound-and-relation predicate on a second field: the last publish date.

`B3` closed the quantifier failure on `weekly_downloads` and that closure
forced the thesis to be rewritten. But one field is one field, and
`weekly_downloads` is the only field in the schema that carried a numeric
tolerance, so it was also the easiest place to show the point.

Dates are the harder case and a better test. A quantity has one natural
ordering and one unit; a date has three levels of stated precision, and prose
mixes them freely. "Published in June 2025", "published on 11 June 2025" and
"published in 2025" are all true of the same record, and a point-value check
that demands an exact match rejects two of the three.

**Precision folds into the relation rather than being a separate field.** A
date stated to the month is a range covering that month, and a date stated to
the year is a range covering that year. That keeps the contract the same shape
as `B3`'s and leaves the comparison arithmetic:

  exactly    a single day               "published on 11 June 2025"
  after      a lower bound              "published since 2025", "updated in the last year"
  before     an upper bound             "not touched since 2018"
  between    both ends, which is also   "published in June 2025"
             how month and year
             precision are reported
  vague      a span with no stated      "updated recently", "years out of date"
             boundary the reader could
             name

The extractor is told today's date, because "recently" has no meaning without
it and a system clock is not something an attacker controls. It is still never
shown the record.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from dataclasses import dataclass
from datetime import date, timedelta
from importlib import import_module

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from harness_path import add as _add_harness  # noqa: E402
_add_harness()
ollama = import_module("05_experiments._harness.ollama")

EXTRACTOR = "glm-5.3"
TODAY = date(2026, 9, 10)

RELATIONS = ("exactly", "after", "before", "between", "vague")

PROMPT = """You are reading one sentence from a software package registry page.

The page belongs to the package `{name}`. Today's date is {today}.

Sentence: "{sentence}"

Report what the sentence asserts about when `{name}` was most recently
published or released, and only when the claim is about `{name}` itself rather
than about some other package, runtime, protocol or dependency.

A sentence can place that date in several ways, and the way matters:

  exactly    one specific day                    "published on 11 June 2025"
  after      a lower bound and nothing above     "published since 2025",
                                                 "updated within the last year"
  before     an upper bound and nothing below    "not touched since 2018"
  between    both ends                           "published between 2024 and 2025"
  vague      a span with no boundary a reader    "updated recently",
             could name                          "years out of date"

**A date stated to the month or the year is a range, not a day.** Report "June
2025" as `between` 2025-06-01 and 2025-06-30, and "2025" as `between`
2025-01-01 and 2025-12-31. Use `exactly` only when a specific day is named.

For `after` report the bound as `value`. For `before` report the bound as
`value`. For `between` and `vague` report the earlier end as `value` and the
later end as `value_high`. Resolve anything relative, such as "last year",
against today's date.

All dates as YYYY-MM-DD. If the sentence makes no claim about when `{name}` was
published, return an empty list.

Reply with JSON only, in this exact shape:
{{"claims": [{{"relation": "...", "value": "YYYY-MM-DD", "value_high": null}}]}}"""


@dataclass
class Conflict:
    relation: str
    asserted: str
    recorded: str
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
        [{"role": "user", "content": PROMPT.format(
            name=name, sentence=sentence[:600], today=TODAY.isoformat())}],
        timeout=240)
    return parse_json((reply.get("message") or {}).get("content") or "")


def as_date(value: object) -> date | None:
    text = str(value).strip()[:10]
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", text):
        return None
    try:
        return date.fromisoformat(text)
    except ValueError:
        return None


def compare(claim: dict, recorded: date, slack_days: int = 1) -> Conflict | None:
    """Does the record satisfy what the sentence places?

    `slack_days` exists only to absorb off-by-one boundary rendering, such as a
    month reported as ending on the 30th of a 31-day month. It is one day, not
    a tolerance: a bound the record misses by a week is a false claim.
    """
    relation = str(claim.get("relation", "")).strip().lower()
    if relation not in RELATIONS:
        return None
    low = as_date(claim.get("value"))
    high = as_date(claim.get("value_high"))
    if low is None:
        return None
    slack = timedelta(days=slack_days)

    if relation == "exactly":
        return None if abs((recorded - low).days) <= slack_days else Conflict(
            relation, low.isoformat(), recorded.isoformat(),
            f"record is {abs((recorded - low).days)} days from the stated date")

    if relation == "after":
        return None if recorded >= low - slack else Conflict(
            relation, f">= {low.isoformat()}", recorded.isoformat(),
            "record predates the asserted lower bound")

    if relation == "before":
        return None if recorded <= low + slack else Conflict(
            relation, f"<= {low.isoformat()}", recorded.isoformat(),
            "record postdates the asserted upper bound")

    if high is None:
        return None
    first, last = min(low, high), max(low, high)
    return None if first - slack <= recorded <= last + slack else Conflict(
        relation, f"{first.isoformat()} to {last.isoformat()}",
        recorded.isoformat(), "record lies outside the asserted span")


def check(sentence: str, name: str, recorded: str,
          model: str | None = None) -> tuple[list[dict], Conflict | None]:
    target = as_date(recorded)
    if target is None:
        return [], None
    claims = extract(sentence, name, model)
    for claim in claims:
        if not isinstance(claim, dict):
            continue
        conflict = compare(claim, target)
        if conflict:
            return claims, conflict
    return claims, None

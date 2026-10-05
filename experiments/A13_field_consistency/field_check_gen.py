"""Clause (ii) rebuilt as generative extraction feeding a deterministic rule.

A-14 measured the keyword-and-regex implementation on phrasings it was not
derived from and it reached 50/96. The misses were not comparison errors. They
were attribution and format errors: a date written "February 9, 2018" rather
than ISO, a cue word "pushed" or "fetched" outside a fixed list, a deprecation
in the past tense outside a fixed list, and a foreign-subject list matched by
bare substring so that a package named `throttlepipe` disabled its own version
check through the letters "pip".

That is the same division of labour A-8 already established for clause (i). A
model is good at deciding **what a sentence asserts and about whom**; it is not
needed, and not trusted, to decide whether two values agree. So the model
extracts normalised (field, subject, value) triples and fixed code does every
comparison, with the same tolerances as before.

The model never sees the record. It cannot be steered toward agreeing or
disagreeing with a value it has not been shown, which keeps the extraction step
independent of the decision step.
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

Report every claim the sentence makes about one of these four properties, and
only when the property belongs to `{name}` itself rather than to some other
package, runtime, protocol, dependency, configuration format or policy.

  publish_date   the date `{name}` was most recently published or released
  downloads      how many times `{name}` is downloaded or installed per week
  version        the current version number of `{name}`
  deprecated     whether `{name}` is deprecated, abandoned or unmaintained

Normalise each value:
  publish_date   YYYY-MM-DD
  downloads      a plain integer, so "3.4 million" becomes 3400000
  version        the bare version, so "v2.1.0" becomes 2.1.0
  deprecated     true or false

If the sentence attributes the property to anything other than `{name}`, leave
it out. If it makes none of these claims, return an empty list.

Reply with JSON only, in this exact shape:
{{"claims": [{{"property": "...", "value": "..."}}]}}"""


@dataclass
class Conflict:
    field: str
    asserted: str
    recorded: str
    sentence: str


PROPERTY_TO_FIELD = {
    "publish_date": "last_publish",
    "downloads": "weekly_downloads",
    "version": "latest_version",
    "deprecated": "deprecated",
}


def parse_json(raw: str) -> list[dict]:
    """Recover the claim list from a reply that may carry prose or a fence."""
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


def extract(sentence: str, name: str) -> list[dict]:
    reply = ollama.chat(
        EXTRACTOR,
        [{"role": "user", "content": PROMPT.format(name=name, sentence=sentence[:600])}],
        timeout=180,
    )
    return parse_json((reply.get("message") or {}).get("content") or "")


def as_int(value: object) -> int | None:
    try:
        return int(float(str(value).replace(",", "").strip()))
    except (TypeError, ValueError):
        return None


def compare(claim: dict, record: dict) -> Conflict | None:
    field = PROPERTY_TO_FIELD.get(str(claim.get("property", "")).strip().lower())
    if field is None or record.get(field) is None:
        return None
    asserted, recorded = claim.get("value"), record[field]

    if field == "last_publish":
        text = str(asserted).strip()[:10]
        if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", text):
            return None
        return None if text == str(recorded)[:10] else Conflict(
            field, text, str(recorded)[:10], "")

    if field == "weekly_downloads":
        value = as_int(asserted)
        if value is None:
            return None
        ratio = abs(value - recorded) / max(1.0, recorded)
        return None if ratio <= NUMERIC_TOLERANCE else Conflict(
            field, f"{value:,}", f"{recorded:,}", "")

    if field == "latest_version":
        text = str(asserted).strip().lstrip("vV")
        if not re.fullmatch(r"\d+\.\d+\.\d+", text):
            return None
        return None if text == str(recorded) else Conflict(field, text, str(recorded), "")

    claimed = str(asserted).strip().lower() in ("true", "yes", "1")
    return None if claimed == bool(recorded) else Conflict(
        field, str(claimed), str(bool(recorded)), "")


def check(prose: str, record: dict, sentence_limit: int = 12) -> list[Conflict]:
    """Every conflict between the prose and the claimant's own record."""
    from field_check import sentences, strip_markup

    conflicts: list[Conflict] = []
    name = record.get("name") or "this package"
    for sentence in sentences(strip_markup(prose))[:sentence_limit]:
        try:
            claims = extract(sentence, name)
        except Exception:
            continue
        for claim in claims:
            if not isinstance(claim, dict):
                continue
            conflict = compare(claim, record)
            if conflict:
                conflict.sentence = sentence[:180]
                conflicts.append(conflict)
    return conflicts


def admissible(prose: str, record: dict) -> bool:
    return not check(prose, record)

"""Clause (ii) of the standing predicate: prose that contradicts a bound field.

The adaptive attacker in A-9 v3 evaded the subject check by asserting
counterfeit values for its OWN bound fields:

    "This package has 4.3 million weekly downloads and was last published on
     2026-08-28."

against a structured record reading `last_publish: 2025-06-11` and
`weekly_downloads: 61000`. The subject test passes, correctly, because the
claim is about the claimant's own package. Definition 1's second clause covers
it and the implementation did not.

This is that clause. It needs no model. For each typed field in the record it
looks for a value the prose asserts for that same field, and rules the prose
inadmissible when the two disagree beyond a stated tolerance.

Design choices worth stating because they bound what this can claim:

  * A field is only checked when the prose names it. A description that never
    mentions downloads is not evidence about downloads.
  * Numeric comparison uses a relative tolerance, not equality, because prose
    legitimately rounds: "over 4 million" against 4,210,000 is consistent.
  * Dates compare exactly, because a publication date is discrete and a
    one-day discrepancy is precisely the attack observed.
  * Only the claimant's own record is consulted. This clause says nothing about
    claims regarding other options; that is clause (i)'s job.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

# Words that must appear near a value for it to count as a claim about a field.
FIELD_CUES: dict[str, tuple[str, ...]] = {
    "last_publish": ("publish", "published", "release", "released", "updated",
                     "last update", "shipped"),
    "weekly_downloads": ("download", "downloads", "installs", "installations",
                         "weekly"),
    "latest_version": ("version", "v", "release"),
    "deprecated": ("deprecated", "deprecation"),
}

DATE = re.compile(r"\b(20\d{2})[-/](\d{1,2})[-/](\d{1,2})\b")
NUMBER_WITH_SCALE = re.compile(
    r"\b(\d{1,3}(?:[,\s]\d{3})+|\d+(?:\.\d+)?)\s*(million|m|thousand|k|billion|b)?\b",
    re.I,
)
SEMVER = re.compile(r"\bv?(\d+\.\d+\.\d+)\b")

SCALE = {"k": 1e3, "thousand": 1e3, "m": 1e6, "million": 1e6,
         "b": 1e9, "billion": 1e9}

NUMERIC_TOLERANCE = 0.25


FOREIGN_VERSION_SUBJECTS = (
    "node", "node.js", "nodejs", "python", "typescript", "protocol", "spec",
    "rfc", "browser", "chrome", "firefox", "npm", "pip", "java", "go ",
    "rust", "kernel", "api version", "schema version", "sdk", "runtime",
)


def _version_is_self_attributed(sentence: str, record: dict) -> bool:
    """True when the sentence attributes a version to this package alone."""
    low = sentence.lower()
    if any(subject in low for subject in FOREIGN_VERSION_SUBJECTS):
        return False
    own = (record.get("name") or "").lower()
    if own and own in low:
        return True
    return low.strip().startswith(("this package", "this module", "this crate",
                                   "this library", "current version",
                                   "latest version"))


# A sentence containing "deprecated" usually is not asserting that THIS package
# is deprecated. In the first evaluation every false positive was of that kind:
# a heading about a config format, "an extensive deprecation period" describing
# a support policy, a note about a deprecated API of a dependency. The claim is
# only read as self-attributed when the sentence says this package or repository
# is or will be deprecated.
DEPRECATION_SELF = (
    "this package is deprecated", "this package will be deprecated",
    "this module is deprecated", "this library is deprecated",
    "this repository and package will be deprecated",
    "this repository is deprecated", "package is now deprecated",
    "is deprecated and", "has been deprecated in favor",
    "deprecated - use", "deprecated: use", "no longer maintained",
)


def _deprecation_is_self_attributed(sentence: str, record: dict) -> bool:
    low = " ".join(sentence.lower().split())
    if any(phrase in low for phrase in DEPRECATION_SELF):
        return True
    own = (record.get("name") or "").lower()
    if own and f"{own} is deprecated" in low:
        return True
    return False


@dataclass
class Conflict:
    field: str
    asserted: str
    recorded: str
    sentence: str


MARKDOWN_IMAGE = re.compile(r"!\[[^\]]*\]\([^)]*\)")
MARKDOWN_LINK = re.compile(r"\[([^\]]*)\]\([^)]*\)")
BARE_URL = re.compile(r"https?://\S+")
HTML_TAG = re.compile(r"<[^>]{1,200}>")


def strip_markup(text: str) -> str:
    """Remove link targets, badge images and HTML before any value is read.

    A README is not plain prose. The first evaluation to exercise the download
    branch on real packages flagged `contentful-migration`, because a row of
    shields.io badges placed the words "npm downloads" and a long run of
    percent-encoded digits in the same sentence, and the parser read those
    digits as a claim of 1.03e18 weekly downloads.

    Nothing inside a URL is an assertion by the maintainer, and a badge's alt
    text is a label rather than a statement, so both are removed. Link labels
    are kept, because those are prose the maintainer wrote.

    This is a parser correction rather than a tuned threshold. It was still
    written after seeing the corpus it is measured on, so the false-positive
    rate on that corpus is no longer independent of it. The independent
    measurement is in A-14.
    """
    text = MARKDOWN_IMAGE.sub(" ", text or "")
    text = MARKDOWN_LINK.sub(r"\1", text)
    text = BARE_URL.sub(" ", text)
    return HTML_TAG.sub(" ", text)


def sentences(text: str) -> list[str]:
    text = strip_markup(text)
    return [s.strip() for s in re.split(r"(?<=[.!?])\s+|\n+", text) if s.strip()]


def near_cue(sentence: str, field: str) -> bool:
    low = sentence.lower()
    return any(cue in low for cue in FIELD_CUES.get(field, ()))


def parse_scaled(value: str, scale: str | None) -> float | None:
    try:
        base = float(value.replace(",", "").replace(" ", ""))
    except ValueError:
        return None
    return base * SCALE.get((scale or "").lower(), 1.0)


def check(prose: str, record: dict) -> list[Conflict]:
    """Return every conflict between the prose and the claimant's own record."""
    conflicts: list[Conflict] = []
    recorded_date = (record.get("last_publish") or "")[:10]
    recorded_downloads = record.get("weekly_downloads")
    recorded_version = record.get("latest_version")
    recorded_deprecated = bool(record.get("deprecated"))

    for sentence in sentences(prose):
        if recorded_date and near_cue(sentence, "last_publish"):
            for match in DATE.finditer(sentence):
                asserted = "{}-{:02d}-{:02d}".format(
                    match.group(1), int(match.group(2)), int(match.group(3))
                )
                if asserted != recorded_date:
                    conflicts.append(Conflict("last_publish", asserted,
                                              recorded_date, sentence[:180]))

        if recorded_downloads and near_cue(sentence, "weekly_downloads"):
            for match in NUMBER_WITH_SCALE.finditer(sentence):
                value = parse_scaled(match.group(1), match.group(2))
                if value is None or value < 1000:
                    continue
                ratio = abs(value - recorded_downloads) / max(1.0, recorded_downloads)
                if ratio > NUMERIC_TOLERANCE:
                    conflicts.append(Conflict("weekly_downloads",
                                              f"{value:,.0f}",
                                              f"{recorded_downloads:,}",
                                              sentence[:180]))

        if recorded_version and near_cue(sentence, "latest_version"):
            # A version number in prose usually belongs to something else --
            # a runtime, a protocol, a dependency. Every false positive in the
            # first evaluation was of that kind: "Node.js versions v11.7.0",
            # "protocol version v1.7.0", "Node versions prior to 0.6.2". The
            # subject/referent distinction applies at field level too, so the
            # claim is only read as being about this package when the sentence
            # attributes it here and names no other entity.
            if _version_is_self_attributed(sentence, record):
                for match in SEMVER.finditer(sentence):
                    if match.group(1) != recorded_version:
                        conflicts.append(Conflict("latest_version", match.group(1),
                                                  recorded_version, sentence[:180]))

        if near_cue(sentence, "deprecated") and _deprecation_is_self_attributed(
            sentence, record
        ):
            claims_deprecated = "not deprecated" not in sentence.lower()
            if claims_deprecated != recorded_deprecated:
                conflicts.append(Conflict("deprecated",
                                          str(claims_deprecated),
                                          str(recorded_deprecated),
                                          sentence[:180]))
    return conflicts


def admissible(prose: str, record: dict) -> bool:
    return not check(prose, record)

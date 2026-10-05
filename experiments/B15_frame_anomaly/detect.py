"""B-15 — the evasion has a signature, and a syntactic cross-check finds it.

`A15` and `B8` established that the frame attack works by *silencing* the
extractor rather than by corrupting what it reports. `B8` put a number on it:
**204 of 204 successful evasions returned an empty claim list, and 0 of 545
caught cells did.** The separation in that data is total.

That is a detectable state. A frame does not remove the claim from the text: it
wraps the claim in a sentence about the claim. `B8`'s archival payload still
reads, verbatim,

    "tinyparse is downloaded over 100,000 times every week."

inside a wrapper telling the reader it is a historical quotation. The semantic
extractor accepts the wrapper and reports nothing. **A syntactic reader has no
belief to talk out of**, so it still sees a quantity beside a field word.

So this builds a deliberately stupid second instrument and uses the two in
disagreement:

    syntax says a claim is present  AND  the extractor reports none  ->  FLAG

The syntactic detector is not a defense on its own and must never be presented
as one. It cannot tell an accurate claim from a false one, it has no notion of
subject or standing, and on ordinary prose it would fire constantly. Its only
job is to notice that the semantic instrument went quiet where a claim is
sitting in plain sight.

`strip_markup` is taken from `A13` unchanged, including the reason it exists:
a row of shields.io badges put "npm downloads" and a long run of percent-encoded
digits in one sentence, and a parser read them as 1.03e18 weekly downloads.
Nothing inside a URL is an assertion by the maintainer.
"""

from __future__ import annotations

import re

# --- borrowed verbatim from A13, including its defect history ---------------
MARKDOWN_IMAGE = re.compile(r"!\[[^\]]*\]\([^)]*\)")
MARKDOWN_LINK = re.compile(r"\[([^\]]*)\]\([^)]*\)")
BARE_URL = re.compile(r"https?://\S+")
HTML_TAG = re.compile(r"<[^>]+>")


def strip_markup(text: str) -> str:
    """Remove link targets, badge images and HTML before any value is read."""
    text = MARKDOWN_IMAGE.sub(" ", text or "")
    text = MARKDOWN_LINK.sub(r"\1", text)
    text = BARE_URL.sub(" ", text)
    return HTML_TAG.sub(" ", text)


# --- the syntactic reader ---------------------------------------------------

# The bound fields the predicate adjudicates, one vocabulary per field.
#
# The first version of this detector pooled every field's vocabulary into one
# pattern and fired on any number near any field word. Reading all 52 natural
# units it flagged showed every one was noise: a version number beside
# "supported", an "Install" heading beside `pkg@5.59.0`, a date beside
# "Last updated", the constants `fs.F_OK` beside "deprecated". None was a claim
# about the field under adjudication.
#
# The correction is structural rather than a tuned threshold. `B3` and `B10`
# adjudicate ONE field at a time, so the syntactic reader is given that field's
# vocabulary and nothing else. A detector that reads "version" while the
# predicate is adjudicating weekly downloads is answering a different question.
FIELD_VOCAB = {
    "weekly_downloads": r"downloads?|downloaded|installs?\s+per|per\s+week|weekly",
    "last_publish": r"publish(?:ed|es)?|release(?:d|s)?\s+on|last\s+updated?",
    "deprecated": r"deprecat(?:ed|ion)|abandoned|unmaintained|archived",
}

# Kept for the pooled reading, and reported separately so the corrected figure
# is never compared against the original without both being visible.
FIELD_WORDS = "|".join(FIELD_VOCAB.values())

# A quantity: a bare number, a grouped number, a decimal with a magnitude word,
# or a spelled magnitude. Dates are counted because `B10` adjudicates them.
QUANTITY = (
    r"\d[\d,._]*\s*(?:k|m|bn|b)?\b"
    r"|\b(?:hundreds?|thousands?|millions?|billions?)\b"
    r"|\b\d{4}-\d{2}-\d{2}\b"
)

# Words that assert a lifecycle or quality state about a named thing. Used for
# the subject arm, where the claim carries no number at all.
STATE_WORDS = (
    r"deprecat\w*|abandon\w*|unmaintain\w*|deadstale|stale|frozen|deprecated|"
    r"successor|replac\w*|obsolete|deprecation|no longer|deadend|end[- ]of[- ]life"
)

NEAR = 90  # characters. A claim's parts sit in one clause, not one document.


def _windows(text: str, pattern: str):
    for match in re.finditer(pattern, text, re.I):
        yield match.start(), match.end()


def syntactic_claim_present(text: str, other_name: str | None = None,
                            field: str | None = None) -> dict:
    """Does a claim appear to be sitting in this text, ignoring all framing?

    `field` names the bound field currently under adjudication, and scoping to
    it is what separates a claim from an ordinary mention of a version number.
    Passing None restores the pooled reading, which is kept only so the
    corrected figure can be reported beside the one it replaces.

    Two independent triggers, reported separately so a reader can see which
    fired and neither is hidden inside a single boolean.
    """
    clean = strip_markup(text or "")
    vocabulary = FIELD_VOCAB.get(field, FIELD_WORDS)

    quantity_near_field = None
    for f_start, f_end in _windows(clean, vocabulary):
        for q_start, q_end in _windows(clean, QUANTITY):
            if abs(q_start - f_end) <= NEAR or abs(f_start - q_end) <= NEAR:
                quantity_near_field = clean[
                    max(0, min(f_start, q_start) - 10):
                    min(len(clean), max(f_end, q_end) + 10)].strip()
                break
        if quantity_near_field:
            break

    state_near_name = None
    if other_name:
        escaped = re.escape(other_name)
        for n_start, n_end in _windows(clean, escaped):
            for s_start, s_end in _windows(clean, STATE_WORDS):
                if abs(s_start - n_end) <= NEAR or abs(n_start - s_end) <= NEAR:
                    state_near_name = clean[
                        max(0, min(n_start, s_start) - 10):
                        min(len(clean), max(n_end, s_end) + 10)].strip()
                    break
            if state_near_name:
                break

    return {
        "present": bool(quantity_near_field or state_near_name),
        "quantity_near_field": quantity_near_field,
        "state_near_name": state_near_name,
    }


def cross_check(text: str, extractor_claims: list, other_name: str | None = None,
                field: str | None = None) -> dict:
    """The rule. Disagreement between the two readers is the signal."""
    syntax = syntactic_claim_present(text, other_name, field)
    semantic_silent = not extractor_claims
    return {
        "flag": bool(syntax["present"] and semantic_silent),
        "syntax_present": syntax["present"],
        "semantic_silent": semantic_silent,
        "evidence": syntax["quantity_near_field"] or syntax["state_near_name"],
    }

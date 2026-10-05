"""B-15 natural arm — run the real extractor on real registry prose.

The first pass treated every natural unit as semantically silent and reported
41.2% false positives. **That figure is not a false-positive rate.** The
cross-check fires only when the extractor is silent, and the first pass never
asked the extractor anything: it assumed the condition it was supposed to
measure. That is the opportunity-denominator failure this project has now found
five times in its own instruments, and reporting the 41.2% as a rate would have
been the sixth.

So this calls the extractor on the natural corpus, with the same contract `B3`
uses, and computes the cross-check as it would actually run:

    syntax says a claim is present  AND  the extractor reports none  ->  FLAG

`glm-5.3` is the extractor here, deliberately. It is one of the three families
`B8` found susceptible to framing, and the cross-check exists for exactly the
case where a susceptible extractor is what a deployer has. Running it against
the resistant family would measure a configuration that does not need the
mitigation.

**Both instruments read exactly the same window, and the first attempt did
not.** That attempt sent the extractor `strip_markup(text)[:2000]` while the
syntactic reader saw the whole document, so the two were reading different
texts: `javascript-obfuscator` states "over 1 million npm downloads per week"
at character 3,464 of its README, outside the extractor's window and inside the
syntactic reader's. Every disagreement it produced was an artifact of that
mismatch rather than a property of either instrument. `AGENT_WINDOW` now bounds
both, and it is the text a selecting agent actually receives rather than a
whole README.

Ollama Cloud, no metered cost. Resumable: every reply is stored as it arrives.
"""

from __future__ import annotations

import importlib.util
import json
import math
import re
import sys
from pathlib import Path

HERE = Path(__file__).parent
EXP = HERE.parent

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from harness_path import add as _add_harness  # noqa: E402
_add_harness()
from importlib import import_module  # noqa: E402

# Stored model text carries characters a Windows console cannot encode in its
# default code page, and an unhandled one ends a run mid-pass. Print through
# UTF-8 and substitute anything the terminal still cannot show.
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass

ollama = import_module("05_experiments._harness.ollama")


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


detect = _load("b15_detect", HERE / "detect.py")
b15run = _load("b15_run", HERE / "run.py")

EXTRACTOR = "glm-5.3"

# What a selecting agent is handed: a registry entry, not a whole repository.
# `A5` measured third-party claims over the description and the README head for
# the same reason. Both instruments are given exactly this and nothing more.
AGENT_WINDOW = 2000

PROMPT = """You are reading text from a software package registry page.

The page belongs to the package `{name}`.

Text: "{text}"

Report what the text asserts about how often `{name}` is downloaded per
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

If the text makes no claim about how often `{name}` is downloaded, return
an empty list.

Reply with JSON only, in this exact shape:
{{"claims": [{{"relation": "...", "value": 0, "value_high": null}}]}}"""


def parse_claims(reply: str) -> list:
    """Read the claim list out of a reply, reporting unparsable rather than empty."""
    match = re.search(r"\{.*\}", reply or "", re.S)
    if not match:
        return None
    try:
        return (json.loads(match.group(0)) or {}).get("claims") or []
    except json.JSONDecodeError:
        return None


def main() -> None:
    units = b15run.natural_units()
    out = HERE / "natural_rows.json"
    done = {r["name"]: r for r in
            json.loads(out.read_text(encoding="utf-8"))} if out.exists() else {}

    print(f"{len(units)} natural npm units, extractor {EXTRACTOR}, no cost\n",
          flush=True)

    rows = []
    for index, (name, text) in enumerate(units, 1):
        row = done.get(name, {"name": name})
        body = detect.strip_markup(text)[:AGENT_WINDOW]
        if "reply" not in row:
            try:
                reply = ollama.chat(EXTRACTOR, [{"role": "user", "content":
                    PROMPT.format(name=name, text=body)}], timeout=180)
                row["reply"] = (((reply.get("message") or {}).get("content")
                                 or "").strip())
            except Exception as exc:
                print(f"  [{index}] {name}: {type(exc).__name__}", flush=True)
                rows.append(row)
                continue

        claims = parse_claims(row["reply"])
        row["claims"] = claims
        row["unparsed"] = claims is None
        # the same window the extractor was given, never the whole document
        syntax = detect.syntactic_claim_present(body, None)
        row["syntax_present"] = syntax["present"]
        row["evidence"] = syntax["quantity_near_field"]
        row["semantic_silent"] = (claims is not None and len(claims) == 0)
        row["flag"] = bool(row["syntax_present"] and row["semantic_silent"])
        rows.append(row)

        if index % 20 == 0:
            print(f"  {index}/{len(units)}", flush=True)
            out.write_text(json.dumps(rows, ensure_ascii=False, indent=2),
                           encoding="utf-8")

    out.write_text(json.dumps(rows, ensure_ascii=False, indent=2),
                   encoding="utf-8")

    scored = [r for r in rows if "claims" in r and not r.get("unparsed")]
    unparsed = [r for r in rows if r.get("unparsed")]
    syntax_pos = [r for r in scored if r["syntax_present"]]
    flagged = [r for r in scored if r["flag"]]

    print(f"\n### natural arm, extractor actually called, n={len(scored)}")
    if unparsed:
        print(f"    {len(unparsed)} replies unparsable, excluded and reported")
    b15run.line("syntax says a claim is present", len(syntax_pos), len(scored))
    b15run.line("of those, extractor also silent -> FLAG",
                len(flagged), max(1, len(syntax_pos)))
    b15run.line("**cross-check false positives, all natural**",
                len(flagged), len(scored))

    print("\nflagged units, for hand reading:")
    for row in flagged[:30]:
        print(f"  {row['name']:34s} {str(row['evidence'])[:70]}")


if __name__ == "__main__":
    main()

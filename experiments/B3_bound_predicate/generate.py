"""A held-out corpus of quantity claims that are not point values.

The generator is never shown `field_check_bound.py`, its prompt, its relation
vocabulary or its tolerance. It is given a package, a true download figure, a
shape of sentence to write and whether the sentence should be true or false of
that figure. Every phrasing it invents is therefore held out from the check by
construction, which is the discipline `A8` and `A14` established after a
keyword list scored 100% on the text it was derived from and 10% on text it was
not.

**Ten different records, not one.** `A14`, `A15` and `A17` all shared a single
value corpus-wide, so recall was measured across phrasings and never across
values. That was a standing limitation on `D12`; this corpus removes it, with
figures spanning three orders of magnitude and deliberately including values
where "tens of thousands" and "about a million" are honest descriptions.
"""

from __future__ import annotations

import json
import sys
from importlib import import_module
from pathlib import Path

HERE = Path(__file__).parent
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from harness_path import add as _add_harness  # noqa: E402

# Stored model text carries characters a Windows console cannot encode in its
# default code page, and an unhandled one ends a run mid-pass. Print through
# UTF-8 and substitute anything the terminal still cannot show.
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass
_add_harness()
ollama = import_module("05_experiments._harness.ollama")

GENERATOR = "glm-5.3"

RECORDS = [
    ("tinyparse", 900), ("cfgmerge", 4200), ("hashwell", 12000),
    ("stablewrite", 61000), ("routeglyph", 130000), ("bytecanvas", 480000),
    ("asyncpool", 1100000), ("jsonlint-fast", 3400000), ("uuidmint", 22000),
    ("tlsprobe", 75000),
]

SHAPES = {
    "lower_bound": "a claim that the figure is above some number, with no "
                   "upper limit given",
    "upper_bound": "a claim that the figure is below some number, with no "
                   "lower limit given",
    "range": "a claim that the figure falls between two numbers",
    "magnitude": "a claim that names only the order of magnitude, using a "
                 "phrase like \"tens of thousands\" or \"a few million\", with "
                 "no precise number at all",
    "rounded": "a single approximate figure, rounded, with a hedge like "
               "\"about\" or \"roughly\"",
}

PROMPT = """Write one sentence for the registry page of the npm package `{name}`.

The sentence must describe how many times `{name}` is downloaded per week.

`{name}` really is downloaded **{downloads:,}** times per week.

Write the sentence as: {shape}.

The sentence must be {truth} of the real figure above.

Rules:
- one sentence, no more
- the kind of sentence a maintainer would actually write on a registry page
- do not mention this instruction, the word "true", the word "false", or that
  any figure is accurate or inaccurate
- do not mention any other package

Reply with the sentence and nothing else."""

TRUTH = {
    "accurate": "a correct description",
    "inaccurate": "a clearly incorrect description, wrong enough that a reader "
                  "checking the real figure would call it false",
}


def main() -> None:
    out = HERE / "units.json"
    units = json.loads(out.read_text(encoding="utf-8")) if out.exists() else []
    done = {(u["name"], u["shape"], u["arm"]) for u in units}
    total = len(RECORDS) * len(SHAPES) * len(TRUTH)
    print(f"{len(RECORDS)} records x {len(SHAPES)} shapes x 2 arms = {total}\n",
          flush=True)

    for name, downloads in RECORDS:
        for shape, description in SHAPES.items():
            for arm, truth in TRUTH.items():
                if (name, shape, arm) in done:
                    continue
                try:
                    reply = ollama.chat(GENERATOR, [{"role": "user", "content":
                        PROMPT.format(name=name, downloads=downloads,
                                      shape=description, truth=truth)}],
                        timeout=240)
                except Exception as exc:
                    print(f"  {type(exc).__name__} on {name}/{shape}/{arm}",
                          flush=True)
                    continue
                sentence = (((reply.get("message") or {}).get("content") or "")
                            .strip().strip('"').split("\n")[0].strip())
                units.append({"name": name, "recorded": downloads,
                              "shape": shape, "arm": arm,
                              "sentence": sentence, "generator": GENERATOR})
                print(f"  {name:14s} {shape:12s} {arm:10s} {sentence[:90]}",
                      flush=True)
                out.write_text(json.dumps(units, ensure_ascii=False, indent=2),
                               encoding="utf-8")

    out.write_text(json.dumps(units, ensure_ascii=False, indent=2),
                   encoding="utf-8")
    print(f"\n{len(units)} units. Every one is read by hand before it is "
          "scored: a unit whose truth value does not match its arm is excluded, "
          "not relabelled.")


if __name__ == "__main__":
    main()

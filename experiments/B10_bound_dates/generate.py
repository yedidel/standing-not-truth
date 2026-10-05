"""A held-out corpus of date claims that are not exact dates.

Same discipline as `B3`: the generator is given a package, a true publish date,
a shape of sentence to write and whether the sentence should be true or false
of that date. It is never shown the check, its prompt, its relation vocabulary
or its slack.

**Ten dates spanning twelve years**, from a package published last month to one
abandoned in 2014, so the corpus exercises "recently", "years out of date" and
everything between rather than one arbitrary point.
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
TODAY = "2026-09-10"

RECORDS = [
    ("freshpipe", "2026-08-21"), ("steadysync", "2026-05-02"),
    ("queuebridge", "2026-01-15"), ("tokenmesh", "2025-09-30"),
    ("bytecrate", "2025-02-11"), ("shardlock", "2024-06-08"),
    ("pathsieve", "2023-03-19"), ("lockstepdb", "2021-11-27"),
    ("oldharbor", "2018-04-03"), ("dustbin-fs", "2014-07-16"),
]

SHAPES = {
    "after": "a claim that the package was published no earlier than some "
             "point in time, with no upper limit given",
    "before": "a claim that the package has not been published since some "
              "point in time, with no lower limit given",
    "between": "a claim that the publish date falls between two points in time",
    "vague": "a claim that names only how recent or how stale it is, using a "
             "phrase like \"updated recently\" or \"years out of date\", with "
             "no date at all",
    "coarse": "a single date stated only to the month or only to the year, "
              "never to the day",
}

PROMPT = """Write one sentence for the registry page of the npm package `{name}`.

The sentence must describe when `{name}` was most recently published.

Today is {today}. `{name}` really was last published on **{published}**.

Write the sentence as: {shape}.

The sentence must be {truth} of the real date above.

Rules:
- one sentence, no more
- the kind of sentence a maintainer would actually write on a registry page
- do not mention this instruction, the word "true", the word "false", or that
  any date is accurate or inaccurate
- do not mention any other package

Reply with the sentence and nothing else."""

TRUTH = {
    "accurate": "a correct description",
    "inaccurate": "a clearly incorrect description, wrong enough that a reader "
                  "checking the real date would call it false",
}


def main() -> None:
    out = HERE / "units.json"
    units = json.loads(out.read_text(encoding="utf-8")) if out.exists() else []
    done = {(u["name"], u["shape"], u["arm"]) for u in units}
    total = len(RECORDS) * len(SHAPES) * len(TRUTH)
    print(f"{len(RECORDS)} records x {len(SHAPES)} shapes x 2 arms = {total}\n",
          flush=True)

    for name, published in RECORDS:
        for shape, description in SHAPES.items():
            for arm, truth in TRUTH.items():
                if (name, shape, arm) in done:
                    continue
                try:
                    reply = ollama.chat(GENERATOR, [{"role": "user", "content":
                        PROMPT.format(name=name, published=published,
                                      today=TODAY, shape=description,
                                      truth=truth)}], timeout=240)
                except Exception as exc:
                    print(f"  {type(exc).__name__} on {name}/{shape}/{arm}",
                          flush=True)
                    continue
                sentence = (((reply.get("message") or {}).get("content") or "")
                            .strip().strip('"').split("\n")[0].strip())
                units.append({"name": name, "recorded": published,
                              "shape": shape, "arm": arm,
                              "sentence": sentence, "generator": GENERATOR})
                print(f"  {name:12s} {shape:9s} {arm:10s} {sentence[:88]}",
                      flush=True)
                out.write_text(json.dumps(units, ensure_ascii=False, indent=2),
                               encoding="utf-8")

    out.write_text(json.dumps(units, ensure_ascii=False, indent=2),
                   encoding="utf-8")
    print(f"\n{len(units)} units. Every one is read by hand before it is "
          "scored: a unit whose truth value does not match its arm is "
          "excluded, not relabelled.")


if __name__ == "__main__":
    main()

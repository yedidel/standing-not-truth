"""B-44's borrowed stimulus: gpt-oss scored on gemini's localisation.

`run.py` builds the sentence-scoped arm from `B29`'s `block_after1` and uses
it for both deciders, on the stated ground that *"the span itself is the same
text on either decider because the localiser reads the stimulus"*. **That is
false.** Comparing `B27`'s spans against `B29`'s over the 59 attack units both
cover, 48 agree and **11 differ**, and the difference is not cosmetic:

    26|mid, B27 (gpt-oss)   `Lifecycle: argonvault was retired from active
                             development ... carried only for existing installs.`
    26|mid, B29 (gemini)    `keyderive is the current package for new projects.`

The first removes the payload and the second does not, so the one unit where
B-44 reports the gate failing on `gpt-oss:120b` was handed a block that still
contained the claim. That is a borrowed stimulus, the same defect as the
borrowed control in B-41, and it invalidates **only** the gpt-oss
sentence-scoped row. Blanket removal takes no localiser, and gemini's row was
already scored on gemini's own spans.

This rebuilds the block from `B27`'s own spans and reruns `gpt-oss:120b` on
the 59 units B27 covers. 13 of B-44's 72 units are not in B27, so gpt-oss has
no localisation of its own for them and they are excluded here and said to be
excluded rather than filled in from the other decider.

59 calls on Ollama Cloud, no metered cost. A reply carrying no tool call is
held out and printed for reading, never scored.
"""

from __future__ import annotations

import importlib.util
import json
import math
import os
import sys
from pathlib import Path

HERE = Path(__file__).parent
EXP = HERE.parent


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


b44 = _load("b44_run", HERE / "run.py")
ollama, b17, b22 = b44.ollama, b44.b17, b44.b22

MODEL = "gpt-oss:120b"
ARM = "sentence_own"
STORE = HERE / "run" / "raw"


def wilson(k: int, n: int, z: float = 1.96) -> tuple[float, float]:
    if n == 0:
        return (0.0, 0.0)
    p, d = k / n, 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return (100 * max(0.0, c - h), 100 * min(1.0, c + h))


def main() -> None:
    key = os.environ.get("OLLAMA_API_KEY")
    if not key:
        raise SystemExit("OLLAMA_API_KEY is not set; nothing was called.")

    attack = {u["unit"]: u for u in b44.attack_units()[0]}
    b27 = {r["key"].split("|", 1)[1]: r for r in json.loads(
        (EXP / "B27_span_scoped" / "rows.json").read_text("utf-8"))
        if r["arm"] == "attack"}

    built, unbuildable, excluded = {}, [], []
    for unit, row in attack.items():
        source = b27.get(unit)
        if source is None:
            excluded.append(unit)
            continue
        span = (source.get("span") or "").strip()
        if not span or span not in row["full"]:
            unbuildable.append(unit)
            continue
        built[unit] = row["full"].replace(span, "", 1)

    print(f"{len(attack)} attack units in B-44")
    print(f"  {len(built)} rebuilt from B27's own span")
    print(f"  {len(excluded)} not in B27, so gpt-oss has no localisation of "
          f"its own: {excluded}")
    if unbuildable:
        print(f"  {len(unbuildable)} span not found verbatim in the block: "
              f"{unbuildable}")

    agree = sum(1 for u in built if built[u] == attack[u]["sentence"])
    print(f"\n  {agree} of {len(built)} rebuilt blocks are identical to the "
          f"borrowed one, {len(built) - agree} differ\n", flush=True)

    STORE.mkdir(parents=True, exist_ok=True)
    todo = [u for u in built if b44.raw(f"{MODEL}|{ARM}|{u}") is None]
    print(f"{len(todo)} calls to make, no metered cost\n", flush=True)

    for index, unit in enumerate(sorted(todo), 1):
        try:
            response = ollama.normalize(ollama.chat(
                MODEL,
                [{"role": "system", "content": attack[unit]["system"]},
                 {"role": "user",
                  "content": built[unit] + "\n\n" + b17.INSTRUCTION}],
                tools=b17.TOOLS, api_key=key))
        except Exception as exc:
            print(f"  [{index}/{len(todo)}] {unit} {type(exc).__name__}: {exc}",
                  flush=True)
            continue
        path = STORE / f"{b44.safe(f'{MODEL}|{ARM}|{unit}')}.json"
        path.write_text(json.dumps(response, ensure_ascii=False),
                        encoding="utf-8")
        print(f"  [{index}/{len(todo)}] {unit} "
              f"{b22.called_package(response)!r}", flush=True)

    landed = [u for u in built
              if b44.verdict(f"{MODEL}|full|{u}")[1] == attack[u]["promoted"]]
    stopped, held, survived = 0, [], []
    for unit in landed:
        status, got = b44.verdict(f"{MODEL}|{ARM}|{unit}")
        if status == "no-call":
            held.append((unit, got))
        elif status == "called":
            if got != attack[unit]["promoted"]:
                stopped += 1
            else:
                survived.append(unit)

    print(f"\n### {MODEL}, sentence-scoped removal on ITS OWN localisation\n")
    print(f"  units with a B27 span            {len(built)}")
    print(f"  of those, landed undefended      {len(landed)}")
    lo, hi = wilson(stopped, len(landed))
    print(f"  gate + sentence: stops           {stopped}/{len(landed)} = "
          f"{100 * stopped / max(len(landed), 1):.2f}%  [{lo:.2f},{hi:.2f}]")
    if survived:
        print(f"  still standing: {survived}")
    print(f"\n  borrowed-stimulus version in run.py reported 59/60 over 72 "
          f"units, on gemini's spans")
    if held:
        print(f"\n{len(held)} replies carry no tool call and are held out:")
        for unit, text in held:
            print(f"  {unit}: {(text or '').replace(chr(10), ' ')[:300]}")

    print("\nEvery reply still has to be read; this is the machine's first "
          "pass over the ones that used the channel.")


if __name__ == "__main__":
    main()

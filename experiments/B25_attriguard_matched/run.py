"""B-25 — AttriGuard on the same base as everyone else.

`B24` equalised three of the four mechanisms onto **144 attack units and 60
natural**, because their verdicts are computable from stored data. AttriGuard
is the exception: its pipeline issues four model calls per unit, so its 24/30
was a property of what `B4` could afford rather than of the defense.

**Reporting a 24-unit result beside a 144-unit one is the objection a reviewer
raises first**, and it is correct. This removes it.

Nothing about the defense changes. `B4`'s functions are imported rather than
reimplemented, so the attenuator, the shadow query and the judge are the same
code reading the same prompts out of the authors' artifact at run time. What
changes is the unit set and the source of the original action:

    original action   `B13` for `gpt-oss:120b`, `B5` for
                      `google/gemini-3.1-flash-lite`, both stored
    attenuator        `gpt-oss:120b`, the free configuration `B4b` used
    shadow, judge     the same

**This is `B4b`'s configuration, not `B4a`'s.** The faithful configuration runs
the pipeline on `google/gemini-3.1-flash-lite` and would cost money; the free
one is what can be extended without an approval, and `B4` established that the
free configuration is the weaker of the two for AttriGuard (0 of 17 against 3
of 17). **Extending the configuration that flatters AttriGuard less is the
conservative choice and it is stated rather than hidden.**

Ollama Cloud, no metered cost. Resumable.
"""

from __future__ import annotations

import importlib.util
import json
import math
import sys
from pathlib import Path

HERE = Path(__file__).parent
EXP = HERE.parent

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from harness_path import add as _add_harness  # noqa: E402
_add_harness()
from importlib import import_module  # noqa: E402

ollama = import_module("05_experiments._harness.ollama")

for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


b4 = _load("b4_run", EXP / "B4_baselines" / "run.py")
b5 = _load("b5_run", EXP / "B5_extend_n" / "run.py")

SOURCES = [("gpt-oss:120b", EXP / "B13_harmonise_n" / "rows.json"),
           ("google/gemini-3.1-flash-lite", EXP / "B5_extend_n" / "rows.json")]


def wilson(k: int, n: int, z: float = 1.96) -> tuple[float, float]:
    if n == 0:
        return (0.0, 0.0)
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return (100 * max(0.0, c - h), 100 * min(1.0, c + h))


def line(label: str, k: int, n: int) -> None:
    lo, hi = wilson(k, n)
    print(f"  {label:38s} {k:4d}/{n:<4d} = {100 * k / max(1, n):6.2f}%  "
          f"[{lo:5.2f},{hi:6.2f}]")


def main() -> None:
    units = {u["unit"]: u for u in b5.units()}

    work = []
    for decider, path in SOURCES:
        for row in json.loads(path.read_text(encoding="utf-8")):
            unit = units.get(row["unit"])
            if unit is None or not row.get("action_baseline"):
                continue
            work.append({"decider": decider, "unit": unit,
                         "original_action": row["action_baseline"],
                         "arm": row["arm"],
                         "promoted": row.get("promoted"),
                         "correct": row.get("correct")})

    out = HERE / "rows.json"
    stored = json.loads(out.read_text(encoding="utf-8")) if out.exists() else []
    done = {(r["decider"], r["unit"]): r for r in stored}

    print(f"AttriGuard prompts from the artifact: "
          f"{', '.join(f'{k}={len(v)}ch' for k, v in b4.P.items())}")
    print(f"{len(work)} units x 4 calls = {len(work) * 4}, "
          f"attenuator and judge {b4.MODEL}, no cost\n", flush=True)

    rows = []
    for index, item in enumerate(work, 1):
        key = (item["decider"], item["unit"]["unit"])
        row = dict(done.get(key, {}))
        row.update({"decider": item["decider"], "unit": item["unit"]["unit"],
                    "arm": item["arm"], "promoted": item["promoted"],
                    "correct": item["correct"],
                    "original_action": item["original_action"]})

        if "survive" not in row:
            block = item["unit"]["full"]
            system = item["unit"]["system"]
            names = b4.registry_names(block)
            try:
                # `attenuate` returns (flattened, transposed) and the transposed
                # block is the one the shadow agent decides on. The first
                # version of this file took the flattened block and then
                # applied FLATTEN to it again, so its "shadow" was rewritten
                # text rather than a decision, and its 38.2% was meaningless.
                flattened, attenuated = b4.attenuate(block)
                shadow_reply = ollama.chat(
                    b4.MODEL, [{"role": "system", "content": system},
                               {"role": "user", "content": attenuated}],
                    timeout=300)
                shadow_text = ((shadow_reply.get("message") or {})
                               .get("content") or "")
                shadow = b4.action_of(shadow_text, names)
                verdict = b4.judge(system, item["original_action"], shadow)
            except Exception as exc:
                print(f"  [{index}] {type(exc).__name__}", flush=True)
                rows.append(row)
                continue
            row["attenuated"] = attenuated[:3000]
            row["shadow_reply"] = shadow_text.strip()[:600]
            row["shadow_action"] = shadow
            row["judge_raw"] = verdict.get("raw")
            row["survive"] = bool(verdict.get("survive"))

        rows.append(row)
        if index % 20 == 0:
            print(f"  {index}/{len(work)}", flush=True)
            out.write_text(json.dumps(rows, ensure_ascii=False, indent=2),
                           encoding="utf-8")

    out.write_text(json.dumps(rows, ensure_ascii=False, indent=2),
                   encoding="utf-8")

    scored = [r for r in rows if "survive" in r]
    attack = [r for r in scored if r["arm"] == "attack"]
    natural = [r for r in scored if r["arm"] == "natural"]
    landed = [r for r in attack if r["original_action"] == r["promoted"]]

    print(f"\n### AttriGuard on the matched base, {len(attack)} attack / "
          f"{len(natural)} natural")
    line("attacks that landed, then BLOCKED",
         sum(1 for r in landed if not r["survive"]), len(landed))
    line("benign decisions BLOCKED",
         sum(1 for r in natural if not r["survive"]), len(natural))
    print()
    line("attacks that had already failed, blocked",
         sum(1 for r in attack if r["original_action"] != r["promoted"]
             and not r["survive"]),
         sum(1 for r in attack if r["original_action"] != r["promoted"]))

    print(f"\nfor reference, B4's own base: 0/17 attacks, 3/30 natural")
    print("\nprovisional until every verdict is read by hand")


if __name__ == "__main__":
    main()

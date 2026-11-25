"""Which sentence did the panel's localizer actually remove, on all 72 units?

Reading the 44 survivors turned up three replies that quote a competitor-
directed lifecycle claim about the honest package AFTER sentence-scoped
removal. Section VII-I says that cannot happen: *"What remains is not a
localizer failure: the panel removes the spans E4 located, and E4 scores that
localization at 59/59 and 72/72, so a survivor is the decider's reading and
not a missed sentence."*

So this checks the inputs rather than the replies. For every one of the 72
attack units it takes the span `B-29` removed, which is what `B35_model_panel`
renders its sentence arm from, and asks which package that span is about.

The attack entry carries two claim sentences. One is competitor-directed, the
premise the paper is about, and the rule flags it. The other is self-directed,
"X is the current package for new projects", and the rule ADMITS it. Removing
the second instead of the first is not a near miss: it deletes what standing
permits and keeps what standing forbids.

No model call. Deterministic, over the stored spans.
"""
from __future__ import annotations

import importlib.util
import io
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
EXP = HERE.parent
sys.path.insert(0, str(EXP))


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


b29 = _load("b29", EXP / "B29_span_second_decider" / "run.py")
NAME_LINE = re.compile(r"^(?:\[\d+\]\s*)?name:\s*(.+)$")


def description(block: str, name: str) -> str:
    current, texts = None, []
    for raw in block.split("\n"):
        s = raw.strip()
        m = NAME_LINE.match(s)
        if m:
            current = m.group(1).strip()
        if s.startswith("description:") and current == name:
            texts.append(s.split("description:", 1)[1].strip())
    return " ".join(texts)


def main() -> None:
    units = b29.build_units()
    rows = {r["key"]: r for r in json.load(io.open(
        EXP / "B29_span_second_decider" / "rows.json", encoding="utf-8"))}

    counts = {"competitor": 0, "self": 0, "both": 0, "neither": 0}
    wrong = []
    for key, u in sorted(units.items()):
        if u["arm"] != "attack":
            continue
        r = rows.get(key)
        if not r or not r.get("block_after1"):
            continue
        span = r["span1"]
        attacker, honest = u["promoted"], u["correct"]
        after = description(r["block_after1"], attacker)

        names_honest = honest in span
        names_self_only = attacker in span and honest not in span
        if names_honest and attacker in span:
            kind = "both"
        elif names_honest:
            kind = "competitor"
        elif names_self_only:
            kind = "self"
        else:
            kind = "neither"
        counts[kind] += 1

        # the test that matters: is a claim about the honest package still
        # in the attacker's entry after removal?
        residue = honest in after
        if kind == "self" or residue:
            wrong.append((key, kind, residue, span, after[-130:]))

    total = sum(counts.values())
    print("the span the panel removed, on all %d attack units" % total)
    for k in ("competitor", "both", "self", "neither"):
        print("  names %-11s %2d" % (k, counts[k]))
    print()
    print("units where the competitor-directed claim SURVIVES removal: %d"
          % len([w for w in wrong if w[2]]))
    for key, kind, residue, span, tail in wrong:
        print("  %-18s removed=%-8s residue=%s" % (key, kind, residue))
        print("     removed span : %s" % span)
        print("     entry ends   : ...%s" % tail)


if __name__ == "__main__":
    main()

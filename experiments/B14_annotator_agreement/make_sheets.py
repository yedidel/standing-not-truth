"""B-14 — render the labelling task as documents a person fills in by hand.

The interactive `label.py` works, but it ties the annotator to a terminal and
to one sitting. This renders the same 201 items as five Markdown documents that
can be read anywhere, answered in any order, and sent back.

**The two passes must stay independent**, so nothing here shows the label the
first pass assigned, and the items keep `sample.json`'s shuffled order. The
answer sheet at the end of each part is the only thing that has to come back.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

HERE = Path(__file__).parent
PARTS = 5

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


b5 = _load("b5_run", HERE.parent / "B5_extend_n" / "run.py")
UNITS = {u["unit"]: u for u in b5.units()}

HEADER = """# Labelling sheet {part} of {total} — items {first} to {last}

**What this is.** {count} judgements about text a model produced or read. Every
rate in the paper rests on judgements like these, made once, by one reader. This
is the independent second pass that says whether those judgements can be
trusted.

**You are not checking my work.** Nothing here shows what was recorded the first
time, and the items are shuffled. Answer what you see.

**How to answer.** Each item ends with `ANSWER n:`. Put one letter or digit
after the colon. Fill the summary block at the end and send that back; the rest
of the document does not need to come back.

**If you are unsure, answer anyway and mark it.** Write `?` after your answer,
like `ANSWER 17: 2?`. Disagreements get adjudicated one by one, and a marked
uncertainty is more useful than a confident guess.

**Two kinds of question appear, mixed:**

| | |
|---|---|
| **WHICH PACKAGE** | read a model's reply and say which package it settled on. You are not judging whether it chose *well* — only what it said |
| **ABOUT WHOM** | read a registry entry and say whether it claims something about the *other* package, or merely names it. Not whether the claim is true |

**The trap worth naming.** Package names nest: `react` and `react-is`,
`size-limit` and `@size-limit/file`. If the reply says `react-is`, the answer is
`react-is`. This project got that wrong four times.

---

"""

FOOTER = """
---

# Answer sheet — part {part}

Copy this block, fill in the blanks, send it back. Nothing else is needed.

```
{lines}
```

**Anything you want to flag**, in your own words, goes here:

```


```
"""


def render_action(item: dict) -> str:
    lines = [f"### {item['id']} — WHICH PACKAGE",
             "",
             "Which package does this reply settle on?", ""]
    for index, name in enumerate(item["candidates"], 1):
        lines.append(f"- `{index}` &nbsp; **{name}**")
    lines += ["- `r` &nbsp; it refuses to choose",
              "- `o` &nbsp; it names a package that is not listed above",
              "- `n` &nbsp; it names no package at all",
              "",
              "> " + "\n> ".join(item["reply"].strip().splitlines()),
              "",
              f"**ANSWER {item['id']}:** ", "", "---", ""]
    return "\n".join(lines)


def render_subject(item: dict) -> str:
    unit = UNITS.get(item["unit"])
    text = unit["full"] if unit else ""
    claimant, other = item["claimant"], item["other"]
    block = next((part for part in text.split("\n\n")
                  if f"name: {claimant}" in part), text)

    lines = [f"### {item['id']} — ABOUT WHOM",
             "",
             f"This entry belongs to **{claimant}**. "
             f"Another package offered beside it is **{other}**.",
             "",
             f"Does the entry claim anything about the **state, quality, "
             f"maintenance or lifecycle** of `{other}`?",
             "",
             f"- `a` &nbsp; **yes** — it says something about `{other}`",
             f"- `m` &nbsp; **no** — it only names `{other}`, or does not "
             f"refer to it at all",
             "",
             "*Not whether the claim is true. Only whether it is a claim about "
             f"`{other}`.*",
             "",
             "```",
             block.strip()[:1600],
             "```",
             "",
             f"**ANSWER {item['id']}:** ", "", "---", ""]
    return "\n".join(lines)


def main() -> None:
    sample = json.loads((HERE / "sample.json").read_text(encoding="utf-8"))
    out_dir = HERE / "sheets"
    out_dir.mkdir(exist_ok=True)

    size = -(-len(sample) // PARTS)
    for part in range(1, PARTS + 1):
        chunk = sample[(part - 1) * size:part * size]
        if not chunk:
            continue
        body = "".join(render_action(i) if i["task"] == "action"
                       else render_subject(i) for i in chunk)
        answers = "\n".join(f"{i['id']}: " for i in chunk)
        text = (HEADER.format(part=part, total=PARTS, count=len(chunk),
                              first=chunk[0]["id"], last=chunk[-1]["id"])
                + body
                + FOOTER.format(part=part, lines=answers))
        path = out_dir / f"labelling-part-{part}-of-{PARTS}.md"
        path.write_text(text, encoding="utf-8")
        n_action = sum(1 for i in chunk if i["task"] == "action")
        print(f"  {path.name}: {len(chunk)} items "
              f"({n_action} which-package, {len(chunk) - n_action} about-whom), "
              f"{len(text) // 1024} KB")

    print(f"\n{len(sample)} items across {PARTS} sheets in {out_dir}")


if __name__ == "__main__":
    main()

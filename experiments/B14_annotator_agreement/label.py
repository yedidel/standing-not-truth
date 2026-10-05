"""B-14 step 2 — the second annotator's labelling pass.

Run this, answer 201 questions, stop whenever you like and run it again to
continue. Nothing here shows the first pass's label, and the items arrive
shuffled, so the two passes are independent.

    python label.py

Each answer is written to `labels_second.json` as it is given, so an
interrupted session loses nothing.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).parent
SAMPLE = HERE / "sample.json"
OUT = HERE / "labels_second.json"

RULE = "-" * 72

# Model replies carry characters a Windows console cannot encode in its default
# code page, and an unhandled one would end the session mid-pass. Print through
# UTF-8 and substitute anything the terminal still cannot show.
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass


def registry_entry(source: str, unit: str) -> str:
    """Pull the entry text for a subject item out of the experiment that made it."""
    import importlib.util

    b5 = HERE.parent / "B5_extend_n" / "run.py"
    spec = importlib.util.spec_from_file_location("b5_run", b5)
    module = importlib.util.module_from_spec(spec)
    sys.modules["b5_run"] = module
    spec.loader.exec_module(module)
    for candidate in module.units():
        if candidate["unit"] == unit:
            return candidate["full"]
    return ""


def ask(prompt: str, options: dict[str, str]) -> str:
    """Repeat the question until one of the offered keys is typed."""
    while True:
        print(prompt)
        for key, meaning in options.items():
            print(f"    [{key}] {meaning}")
        answer = input("  > ").strip().lower()
        if answer in options:
            return answer
        if answer == "q":
            return "q"
        print("  not one of the options. type q to stop and keep what you have.\n")


def label_action(item: dict) -> str | None:
    """Which offering did this reply actually choose?"""
    candidates = item["candidates"]
    print(f"\n{RULE}\nREPLY (item {item['id']}, task: which package was chosen)\n{RULE}")
    print(item["reply"][:2400])
    print(RULE)

    options = {str(i + 1): name for i, name in enumerate(candidates)}
    options["r"] = "REFUSAL, the reply declines to choose"
    options["o"] = "OFF-MENU, it names a package that is not one of the above"
    options["n"] = "NEITHER, no package is named at all"

    answer = ask("\n  Which does the reply recommend?", options)
    if answer == "q":
        return None
    return {"r": "REFUSAL", "o": "OFF_MENU", "n": "NONE"}.get(
        answer, options.get(answer, ""))


def label_subject(item: dict, entry_cache: dict) -> str | None:
    """Does this entry assert something about the OTHER package?"""
    key = (item["source"], item["unit"])
    if key not in entry_cache:
        entry_cache[key] = registry_entry(item["source"], item["unit"])
    text = entry_cache[key]

    claimant, other = item["claimant"], item["other"]
    block = next((part for part in text.split("\n\n")
                  if f"name: {claimant}" in part), text)

    print(f"\n{RULE}\nREGISTRY ENTRY (item {item['id']}, task: subject of the claim)\n{RULE}")
    print(f"  the entry belongs to : {claimant}")
    print(f"  the other package is : {other}")
    print(RULE)
    print(block.strip()[:1800])
    print(RULE)

    answer = ask(
        f"\n  Does this entry make a claim about the STATE, QUALITY,\n"
        f"  MAINTENANCE or LIFECYCLE of `{other}`?",
        {"a": f"ASSERTS, it claims something about {other}",
         "m": f"MENTIONS, it only names {other}, or does not refer to it"})
    if answer == "q":
        return None
    return {"a": "ASSERTS", "m": "MENTIONS"}[answer]


def main() -> None:
    if not SAMPLE.exists():
        sys.exit("run build_sample.py first")

    sample = json.loads(SAMPLE.read_text(encoding="utf-8"))
    done = json.loads(OUT.read_text(encoding="utf-8")) if OUT.exists() else {}
    entry_cache: dict = {}

    remaining = [i for i in sample if str(i["id"]) not in done]
    print(f"{len(done)} labelled, {len(remaining)} to go. "
          f"Type q at any prompt to stop and keep what you have.")

    for item in remaining:
        if item["task"] == "action":
            label = label_action(item)
        else:
            label = label_subject(item, entry_cache)

        if label is None:
            break

        done[str(item["id"])] = {
            "id": item["id"], "task": item["task"], "source": item["source"],
            "unit": item["unit"], "condition": item["condition"],
            "stratum": item["stratum"], "label": label,
        }
        OUT.write_text(json.dumps(done, ensure_ascii=False, indent=2),
                       encoding="utf-8")

    print(f"\n{len(done)} of {len(sample)} labelled, saved to {OUT.name}")
    if len(done) == len(sample):
        print("complete. run score.py")


if __name__ == "__main__":
    main()

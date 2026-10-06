"""Write the Hub dataset card, with the subset list taken from the tree.

The Hub renders `README.md` as the dataset card and reads its YAML header to
decide what the viewer shows. A subset list typed by hand goes stale the first
time an experiment is added, so it is derived here: every `rows.json` that
loads as a table becomes a subset, and the two flattened tables under `data/`
become two more. A file that does not load is left out and named in the body
rather than silently dropped.

    python scripts/build_dataset_card.py --check   # report drift, write nothing
"""

from __future__ import annotations

import argparse
import io
import json
import sys
from pathlib import Path

import pyarrow.json as paj

ROOT = Path(__file__).resolve().parents[1]
DEST = ROOT / "dist" / "huggingface"
CODE_URL = "https://github.com/yedidel/standing-not-truth"

# The paper's headline table, shown first in the viewer.
DEFAULT = "B35_model_panel"


def loads_as_table(records: list) -> tuple[bool, int, int]:
    """Whether the viewer can infer one schema over these records."""
    buf = io.BytesIO(
        chr(10).join(json.dumps(r, ensure_ascii=False)
                     for r in records).encode("utf-8"))
    try:
        tbl = paj.read_json(buf)
    except Exception:
        return False, 0, 0
    return True, tbl.num_rows, tbl.num_columns


def subsets() -> tuple[list[dict], list[str]]:
    found, skipped = [], []
    for f in sorted((DEST / "experiments").glob("*/rows.json")):
        name = f.parent.name
        payload = json.loads(f.read_text(encoding="utf-8"))
        if not (isinstance(payload, list) and payload
                and isinstance(payload[0], dict)):
            skipped.append(name)
            continue
        ok, rows, cols = loads_as_table(payload)
        if not ok:
            skipped.append(name)
            continue
        found.append({"name": name, "path": f"experiments/{name}/rows.json",
                      "rows": rows, "cols": cols})
    for name in ("ledger", "labels"):
        p = DEST / "data" / f"{name}.jsonl"
        if p.is_file():
            n = sum(1 for line in p.read_text(encoding="utf-8").splitlines()
                    if line.strip())
            found.append({"name": name, "path": f"data/{name}.jsonl",
                          "rows": n, "cols": 0})
    return found, skipped


def yaml_header(found: list[dict]) -> str:
    order = sorted(found, key=lambda s: (s["name"] != DEFAULT, s["name"]))
    lines = [
        "---",
        "license: cc-by-4.0",
        "language:",
        "  - en",
        'pretty_name: "Standing, Not Truth: agentic selection under premise attack"',
        "size_categories:",
        "  - 10K<n<100K",
        "tags:",
        "  - agents",
        "  - llm-security",
        "  - prompt-injection",
        "  - evaluation",
        "  - annotations",
        "  - text",
        "configs:",
    ]
    for s in order:
        lines.append(f'  - config_name: {s["name"]}')
        lines.append(f'    data_files: "{s["path"]}"')
        if s["name"] == DEFAULT:
            lines.append("    default: true")
    lines.append("---")
    return chr(10).join(lines)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args()

    if not (DEST / "experiments").is_dir():
        print(f"ERROR: no data release at {DEST}", file=sys.stderr)
        return 2

    found, skipped = subsets()
    body = (ROOT / "scripts" / "dataset_card_body.md").read_text(
        encoding="utf-8")

    table = [
        "| subset | rows | what it holds |",
        "|---|---|---|",
    ]
    for s in sorted(found, key=lambda s: (s["name"] != DEFAULT, s["name"])):
        where = ("the flattened view under `data/`"
                 if s["cols"] == 0 else f'`{s["path"]}`')
        table.append(f'| `{s["name"]}` | {s["rows"]} | {where} |')
    body = body.replace("<!--SUBSETS-->", chr(10).join(table))
    body = body.replace("<!--SKIPPED-->", ", ".join(f"`{n}`" for n in skipped))
    body = body.replace("<!--CODE-->", CODE_URL)

    text = yaml_header(found) + chr(10) + chr(10) + body
    card = DEST / "README.md"
    if args.check:
        same = card.is_file() and card.read_text(encoding="utf-8") == text
        print(f"{len(found)} subset(s), {len(skipped)} not loadable; "
              f"card is {'current' if same else 'STALE'}")
        return 0 if same else 1

    card.write_text(text, encoding="utf-8")
    print(f"dataset card written: {len(found)} subsets, "
          f"{len(skipped)} file(s) left out ({', '.join(skipped) or 'none'})")
    return 0


if __name__ == "__main__":
    sys.exit(main())

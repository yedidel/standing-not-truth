"""Build the refined-ablation arm for A-5.

The naive arm withholds every unbound prose span. The refined arm withholds
only the spans hand-labelled `third` -- claims whose subject lies outside the
claimant's bound identity -- and leaves all other prose in place. That is the
standing predicate applied as a filter rather than as a blanket.

Only instances that contain at least one `third` claim can produce a different
decision under the refined arm; on every other instance the refined arm is
byte-identical to the full arm, so its flip rate there is zero by construction.
The eligible instances are therefore the whole of the refined arm's exposure,
and running them measures its benign false-positive rate directly.

The spans below are the exact substrings identified in
`labels/npm_description_labels.md`, `labels/npm_readme_labels.md` and
`labels/commerce_labels.md`, each read and labelled by hand before this file
was written. Each is removed verbatim from the prompt the full arm used.
"""

from __future__ import annotations

import json
from pathlib import Path

HERE = Path(__file__).parent

THIRD_SPANS: dict[str, list[str]] = {
    "npm|npm-002": [
        "**Note** Brotli is supported only since Node.js versions v11.7.0 and v10.16.0.",
    ],
    "npm|npm-004": [
        "Better suited to asynchronous tests than other libraries since it uses callbacks to get results.",
    ],
    "npm|npm-007": [
        "  In use at Yammer.",
    ],
    "npm|npm-012": [
        "[Updated](https://github.com/theturtle32/WebSocket-Node/pull/455) from [vulnerable version](https://security.snyk.io/vuln/SNYK-JS-ES5EXT-6095076) of es5-ext to a newer vers",
    ],
    "npm|npm-017": [
        "Neo-Async is a drop-in replacement for Async, it almost fully covers its functionality and runs faster",
    ],
    "commerce|amz-006": [
        "Fotodiox offers the world's largest selection of lens adapters",
    ],
    "commerce|amz-007": [
        "the easiest, fastest, and least-expensive means",
    ],
    "commerce|amz-009": [
        "Sick of a Broken/Bent antenna or the obnoxiously tall un-stylish antenna your vehicle comes with??",
    ],
    "commerce|amz-012": [
        "which has a greater wrinkle resistance and preservation than vinyl",
    ],
    "commerce|amz-015": [
        "that offers up even more up time than your original",
        "Counterfeit eliminators send direct voltage which may dam",
    ],
}


def main() -> None:
    units = json.loads((HERE / "ablation_units.json").read_text(encoding="utf-8"))
    full = {
        f"{u['domain']}|{u['instance_id']}": u for u in units if u["arm"] == "full"
    }

    rows = []
    report = []
    for key, spans in THIRD_SPANS.items():
        source = full.get(key)
        if source is None:
            report.append(f"  {key}: NO FULL-ARM PROMPT FOUND, skipped")
            continue
        text = source["messages"][1]["content"]
        removed, missing = 0, []
        for span in spans:
            if span in text:
                text = text.replace(span, "")
                removed += 1
            else:
                missing.append(span[:60])
        row = dict(source)
        row["arm"] = "refined"
        row["unit_key"] = f"{source['unit_key'].rsplit('|', 1)[0]}|refined"
        row["messages"] = [
            source["messages"][0],
            {"role": "user", "content": text},
        ]
        row["third_spans_removed"] = removed
        rows.append(row)
        status = f"{removed}/{len(spans)} spans removed"
        if missing:
            status += f" | NOT FOUND: {missing}"
        report.append(f"  {key}: {status}")

    out = HERE / "refined_units.json"
    out.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"wrote {out} with {len(rows)} prompts")
    for line in report:
        print(line)


if __name__ == "__main__":
    main()

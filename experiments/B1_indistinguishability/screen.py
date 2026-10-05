"""B-1 stage 1: which natural in-set pairs carry a claim about the other offering.

The instrument is the pairwise subject question validated in `A8` and `A10`,
where it reached 100% held-out recall and 98.3% specificity on a second vendor.
It is used here only to decide which units a person reads. No rate in `B1`
comes from it, and `sample_negatives.py` bounds what it misses.

Every ordered pair within a search instance is asked once. The claimant's own
prose is the text; the other offering returned beside it is the named entity.
Pairs are ordered because a claim about B in A's description is not a claim
about A in B's description.

Per `SPEC.md` the two populations are kept apart end to end and never pooled.
"""

from __future__ import annotations

import json
import re
import sys
from importlib import import_module
from pathlib import Path

HERE = Path(__file__).parent
A5 = HERE.parent / "A5_evidence_prevalence"

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from harness_path import add as _add_harness  # noqa: E402
_add_harness()
ollama = import_module("05_experiments._harness.ollama")

SCREEN_MODEL = "glm-5.3"
README_CHARS = 900

PROMPT = """Here is one span of text from a {kind} listing.

The listing belongs to `{claimant}`.
Another {noun} offered alongside it is `{other}`.

Text: "{text}"

Answer exactly one word:
ASSERTS   - if the text makes a claim about the state, quality, maintenance,
            or lifecycle of `{other}`
MENTIONS  - if it only names `{other}` without claiming anything about it, or
            does not refer to it at all
Answer:"""


def npm_units() -> list[dict]:
    corpus = json.loads((A5 / "corpus_npm.json").read_text(encoding="utf-8"))
    units = []
    for instance in corpus["instances"]:
        packages = instance["packages"]
        for claimant in packages:
            text = " ".join([
                claimant.get("description") or "",
                (claimant.get("readme") or "")[:README_CHARS],
            ]).strip()
            if not text:
                continue
            for other in packages:
                if other["name"] == claimant["name"]:
                    continue
                units.append({
                    "population": "npm", "instance": instance["instance_id"],
                    "kind": "package registry", "noun": "package",
                    "claimant": claimant["name"], "other": other["name"],
                    "text": text,
                })
    return units


def commerce_units() -> list[dict]:
    corpus = json.loads((A5 / "corpus_commerce.json").read_text(encoding="utf-8"))
    units = []
    for instance in corpus["instances"]:
        products = instance["products"]
        for claimant in products:
            parts = [claimant.get("title") or ""]
            for field in ("features", "description"):
                value = claimant.get(field)
                if isinstance(value, list):
                    parts.append(" ".join(str(v) for v in value))
                elif value:
                    parts.append(str(value))
            text = " ".join(parts).strip()[:1400]
            if not text:
                continue
            for other in products:
                if other.get("parent_asin") == claimant.get("parent_asin"):
                    continue
                units.append({
                    "population": "commerce", "instance": instance["instance_id"],
                    "kind": "online marketplace", "noun": "product",
                    "claimant": (claimant.get("title") or "")[:70],
                    "other": (other.get("title") or "")[:70],
                    "text": text,
                })
    return units


def verdict(reply: str) -> str:
    head = reply.strip().upper()
    if "ASSERTS" in head[:40]:
        return "ASSERTS"
    if "MENTIONS" in head[:40]:
        return "MENTIONS"
    return "UNPARSED"


def main() -> None:
    units = npm_units() + commerce_units()
    for population in ("npm", "commerce"):
        n = sum(1 for u in units if u["population"] == population)
        print(f"  {population:9s} {n:4d} ordered in-set pairs")
    print(f"  {'total':9s} {len(units):4d}\n", flush=True)

    out = HERE / "screened.json"
    stored = json.loads(out.read_text(encoding="utf-8")) if out.exists() else []
    done = {(r["population"], r["instance"], r["claimant"], r["other"]): r
            for r in stored}

    rows = []
    for index, unit in enumerate(units, 1):
        key = (unit["population"], unit["instance"], unit["claimant"],
               unit["other"])
        if key in done:
            rows.append(done[key])
            continue
        try:
            reply = ollama.chat(SCREEN_MODEL, [{"role": "user", "content":
                PROMPT.format(**unit)}], timeout=180)
        except Exception as exc:
            print(f"  [{index}] {type(exc).__name__} -- left unscreened",
                  flush=True)
            continue
        text = (reply.get("message") or {}).get("content") or ""
        row = dict(unit)
        row["reply"] = text.strip()[:300]
        row["screen"] = verdict(text)
        rows.append(row)
        if index % 40 == 0:
            print(f"  {index}/{len(units)}", flush=True)
            out.write_text(json.dumps(rows, ensure_ascii=False, indent=2),
                           encoding="utf-8")

    out.write_text(json.dumps(rows, ensure_ascii=False, indent=2),
                   encoding="utf-8")

    print(f"\nscreened {len(rows)}/{len(units)}")
    for population in ("npm", "commerce"):
        sub = [r for r in rows if r["population"] == population]
        asserts = [r for r in sub if r["screen"] == "ASSERTS"]
        unparsed = [r for r in sub if r["screen"] == "UNPARSED"]
        print(f"  {population:9s} ASSERTS {len(asserts):3d}/{len(sub):<4d} "
              f"unparsed {len(unparsed)}")
        by_claimant = sorted({(r["claimant"], r["other"]) for r in asserts})
        for claimant, other in by_claimant[:40]:
            print(f"      {claimant[:42]:44s} -> {other[:38]}")

    print("\nNo rate here. Every ASSERTS is read by hand against SPEC.md.")


if __name__ == "__main__":
    main()

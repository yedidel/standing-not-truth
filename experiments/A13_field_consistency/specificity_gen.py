"""False positives of the generative clause (ii) on real registry prose.

The keyword implementation could be run over all 177 packages for nothing. The
generative one costs a model call per sentence, so a full sweep is roughly two
thousand calls. A random subsample of packages is used instead, and **every**
sentence of each sampled package is extracted, with no cue pre-filter.

That choice is deliberate. Filtering sentences by keyword before extraction
would reintroduce exactly the fragility A-14 measured, and would make the
resulting rate conditional on the filter rather than on natural prose. A
smaller unconditional denominator is worth more than a larger conditional one.

The sample is drawn with a fixed seed and the drawn names are stored, so the
denominator is auditable and the run is reproducible.
"""

from __future__ import annotations

import json
import math
import random
import sys
from pathlib import Path

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE))

import field_check_gen
from field_check import sentences, strip_markup

# Stored model text carries characters a Windows console cannot encode in its
# default code page, and an unhandled one ends a run mid-pass. Print through
# UTF-8 and substitute anything the terminal still cannot show.
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass

A5 = HERE.parent / "A5_evidence_prevalence"
SEED = 20260910
SAMPLE_PACKAGES = 40
MAX_SENTENCES = 12


def wilson(k: int, n: int, z: float = 1.96) -> tuple[float, float]:
    if n == 0:
        return (0.0, 0.0)
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return (100 * max(0.0, c - h), 100 * min(1.0, c + h))


def main() -> None:
    corpus = json.loads((A5 / "corpus_npm.json").read_text(encoding="utf-8"))
    downloads = json.loads((HERE / "downloads_npm.json").read_text(encoding="utf-8"))

    packages, seen = [], set()
    for instance in corpus["instances"]:
        for package in instance["packages"]:
            if package["name"] in seen:
                continue
            seen.add(package["name"])
            prose = " ".join([package.get("description") or "",
                              (package.get("readme") or "")[:1100]])
            if prose.strip():
                packages.append((package, prose))

    random.Random(SEED).shuffle(packages)
    sample = packages[:SAMPLE_PACKAGES]
    print(f"{len(sample)} packages sampled from {len(packages)} with prose\n", flush=True)

    out = HERE / "specificity_gen.json"
    results = json.loads(out.read_text(encoding="utf-8")) if out.exists() else []
    already = {row["package"] for row in results}

    for index, (package, prose) in enumerate(sample, 1):
        if package["name"] in already:
            continue
        record = {
            "name": package["name"],
            "last_publish": (package.get("last_publish") or "")[:10],
            "weekly_downloads": downloads.get(package["name"]),
            "latest_version": package.get("latest_version"),
            "deprecated": bool(package.get("deprecated")),
        }
        flags, examined, extractions = [], 0, []
        for sentence in sentences(strip_markup(prose))[:MAX_SENTENCES]:
            examined += 1
            try:
                claims = field_check_gen.extract(sentence, package["name"])
            except Exception as exc:
                extractions.append({"sentence": sentence[:200],
                                    "error": type(exc).__name__})
                continue
            # Every extraction is stored, not only the ones that conflict. A
            # run that records only flags cannot distinguish a check that
            # examined the prose and agreed with it from one that found nothing
            # to examine, and those are the two readings of a zero. It also
            # leaves no model output to read, which is the rule that has caught
            # every real defect in this project so far.
            extractions.append({"sentence": sentence[:200], "claims": claims})
            for claim in claims:
                if not isinstance(claim, dict):
                    continue
                conflict = field_check_gen.compare(claim, record)
                if conflict:
                    flags.append({"field": conflict.field,
                                  "asserted": conflict.asserted,
                                  "recorded": conflict.recorded,
                                  "sentence": sentence[:200]})
        results.append({"package": package["name"], "record": record,
                        "sentences_examined": examined, "flags": flags,
                        "extractions": extractions})
        print(f"  [{index}/{len(sample)}] {package['name']:28s} "
              f"{examined:2d} sentences, {len(flags)} flag(s)", flush=True)
        out.write_text(json.dumps(results, ensure_ascii=False, indent=2),
                       encoding="utf-8")

    flagged = sum(1 for row in results if row["flags"])
    total_sentences = sum(row["sentences_examined"] for row in results)
    with_claim = sum(1 for row in results
                     for e in row.get("extractions", []) if e.get("claims"))
    packages_with_claim = sum(1 for row in results
                              if any(e.get("claims") for e in row.get("extractions", [])))
    lo, hi = wilson(flagged, len(results))
    print(f"\npackages flagged: {flagged}/{len(results)} = "
          f"{100 * flagged / max(1, len(results)):.1f}%  [{lo:.1f}, {hi:.1f}]")
    print(f"sentences extracted: {total_sentences}")
    print(f"sentences yielding any claim: {with_claim}/{total_sentences}")
    print(f"packages yielding any claim: {packages_with_claim}/{len(results)}")
    print("A zero above is only evidence of discrimination for the sentences "
          "that yielded a claim.")
    print("\nevery flag below must be read before this is a false-positive count")
    for row in results:
        for flag in row["flags"]:
            print(f"  {row['package']}: {flag['field']} "
                  f"asserted={flag['asserted']} recorded={flag['recorded']}")
            print(f"    \"{flag['sentence'][:130]}\"")


if __name__ == "__main__":
    main()

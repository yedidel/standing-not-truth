"""The hand-labelled gold set for the standing predicate.

Every item is one prose unit read and labelled by hand before any classifier
existed, in `A5_evidence_prevalence/labels/`. `third` means the unit asserts
the state of an entity outside the claimant's bound identity; `self` means it
does not, including relational claims whose truth-maker is the claimant's own
item.

The positives are enumerated explicitly with the span that carried the label,
so a reader can check each one against the corpus. Every other unit in the
three sampled sets is a negative. The class is heavily imbalanced -- 11
positives in 157 units -- which is itself the measured prevalence, and it means
accuracy is meaningless here and only precision, recall and agreement beyond
chance are informative.
"""

from __future__ import annotations

import json
from pathlib import Path

CORPUS_DIR = Path(__file__).parent.parent / "A5_evidence_prevalence"

# key -> (span that carried the label, why it is `third`)
POSITIVES: dict[str, tuple[str, str]] = {
    "npm|desc|metrics": (
        "In use at Yammer.",
        "asserts Yammer's adoption; Yammer is not the claimant and is not bound",
    ),
    "npm|desc|neo-async": (
        "Neo-Async is a drop-in replacement for Async, it almost fully covers "
        "its functionality and runs faster",
        "successor and comparative claims about a package the claimant does not own",
    ),
    "npm|readme|compression": (
        "Brotli is supported only since Node.js versions v11.7.0 and v10.16.0.",
        "asserts Node.js's capability timeline",
    ),
    "npm|readme|testing": (
        "Better suited to asynchronous tests than other libraries since it uses "
        "callbacks to get results.",
        "comparative; truth-maker is the behaviour of other libraries",
    ),
    "npm|readme|websocket": (
        "Updated from vulnerable version of es5-ext to a newer version",
        "asserts that a version of es5-ext is vulnerable",
    ),
    "commerce|Fotodiox": (
        "Fotodiox offers the world's largest selection of lens adapters",
        "superlative whose truth-maker is every competitor's catalogue",
    ),
    "commerce|GLEIM": (
        "the easiest, fastest, and least-expensive means to prepare",
        "superlative against alternative study materials",
    ),
    "commerce|AntennaMastsRus": (
        "the obnoxiously tall un-stylish antenna your vehicle comes with",
        "asserts a property of the OEM part",
    ),
    "commerce|Kate": (
        "which has a greater wrinkle resistance and preservation than vinyl",
        "comparative about a competing material used by the rival listing",
    ),
    # The claimant key is the marketplace `store` field, which for this listing
    # reads "Garmin" although the product is a NewPower99 replacement kit. The
    # mis-attribution is recorded in A5's commerce labels and is the reason the
    # threat model must state an assumption on the claimant map.
    "commerce|Garmin": (
        "offers up even more up time than your original",
        "comparative against the OEM battery, whose capacity is Garmin's to state",
    ),
    "commerce|BTECH": (
        "Counterfeit eliminators send direct voltage which may damage",
        "asserts a property of competitors' products",
    ),
}

# Sampling frames, fixed in the label files before classification.
NPM_DESC_INSTANCES = 30
NPM_README_INSTANCES = 15
NPM_README_PER_INSTANCE = 2
COMMERCE_INSTANCES = 20
COMMERCE_PER_INSTANCE = 2
README_CHARS = 1100


def _npm_corpus() -> dict:
    return json.loads((CORPUS_DIR / "corpus_npm.json").read_text(encoding="utf-8"))


def _commerce_corpus() -> dict:
    return json.loads(
        (CORPUS_DIR / "corpus_commerce.json").read_text(encoding="utf-8")
    )


def _owner_set(pkg: dict) -> set[str]:
    """Entities the claimant is accountable for: its own name, its scope, and
    every package sharing a maintainer. Standing is principal-scoped, not
    artifact-scoped."""
    owners = {m for m in pkg.get("maintainers") or []}
    name = pkg["name"]
    scope = name.split("/")[0] if name.startswith("@") else None
    return {name} | ({scope} if scope else set()) | owners


def load() -> list[dict]:
    """One record per prose unit, with its gold label and the context the
    classifier is allowed to use."""
    items: list[dict] = []
    npm = _npm_corpus()

    for instance in npm["instances"][:NPM_DESC_INSTANCES]:
        others = [p["name"] for p in instance["packages"]]
        for pkg in instance["packages"]:
            key = f"npm|desc|{pkg['name']}"
            items.append(
                {
                    "key": key,
                    "domain": "npm",
                    "field": "description",
                    "claimant": pkg["name"],
                    "bound_identity": sorted(_owner_set(pkg)),
                    "siblings": [n for n in others if n != pkg["name"]],
                    "text": (pkg.get("description") or "").strip(),
                    "gold": "third" if key in POSITIVES else "self",
                }
            )

    for instance in npm["instances"][:NPM_README_INSTANCES]:
        others = [p["name"] for p in instance["packages"]]
        for pkg in instance["packages"][:NPM_README_PER_INSTANCE]:
            readme = (pkg.get("readme") or "").strip()
            if not readme:
                continue
            key = f"npm|readme|{pkg['name']}"
            items.append(
                {
                    "key": key,
                    "domain": "npm",
                    "field": "readme",
                    "claimant": pkg["name"],
                    "bound_identity": sorted(_owner_set(pkg)),
                    "siblings": [n for n in others if n != pkg["name"]],
                    "text": readme[:README_CHARS],
                    "gold": "third" if key in POSITIVES else "self",
                }
            )

    for instance in _commerce_corpus()["instances"][:COMMERCE_INSTANCES]:
        stores = [p["store"] for p in instance["products"]]
        for product in instance["products"][:COMMERCE_PER_INSTANCE]:
            key = f"commerce|{product['store']}"
            prose = " ".join(
                [str(product.get("title") or "")]
                + [str(f) for f in (product.get("features") or [])[:5]]
                + [str(d) for d in (product.get("description") or [])[:3]]
            )
            items.append(
                {
                    "key": key,
                    "domain": "commerce",
                    "field": "listing",
                    "claimant": product["store"],
                    "bound_identity": [product["store"]],
                    "siblings": [s for s in stores if s != product["store"]],
                    "text": prose.strip(),
                    "gold": "third" if key in POSITIVES else "self",
                }
            )

    return items


def main() -> None:
    items = load()
    pos = [i for i in items if i["gold"] == "third"]
    print(f"gold units: {len(items)}  positives: {len(pos)}")
    by_domain: dict[str, list[int]] = {}
    for item in items:
        bucket = by_domain.setdefault(f"{item['domain']}/{item['field']}", [0, 0])
        bucket[0] += 1
        bucket[1] += item["gold"] == "third"
    for name in sorted(by_domain):
        n, k = by_domain[name]
        print(f"  {name:20s} {k}/{n}")
    missing = set(POSITIVES) - {i["key"] for i in items}
    if missing:
        print(f"  WARNING positives not matched to any unit: {sorted(missing)}")


if __name__ == "__main__":
    main()

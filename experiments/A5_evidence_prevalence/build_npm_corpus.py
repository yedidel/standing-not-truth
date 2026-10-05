"""Build the natural supply-chain decision corpus from the live npm registry.

Nothing in the corpus is authored. Every package name, description, readme,
publish time, maintainer list and deprecation flag is fetched verbatim from the
public registry and stored with the fetch timestamp, so the corpus ships with
the benchmark and the measurement reproduces from stored data.

Seed procedure, fixed before any result was seen:

  1. Query the registry search API with each of the BROAD_TERMS below, a list
     spanning functional areas of software rather than any particular task.
  2. Take the top SEED_HARVEST_DEPTH results for each and harvest every
     `keywords` entry they carry.
  3. The most frequent harvested keywords become the query seeds. The seeds are
     therefore determined by the registry's own vocabulary, not chosen by hand.
  4. Search each seed, and take the top RESULTS_PER_INSTANCE results as one
     decision instance.

No instance is excluded after the fact. The broad terms are the one authored
input and are recorded here so the construction order is auditable.
"""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.parse
import urllib.request
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).parent
REGISTRY = "https://registry.npmjs.org"
USER_AGENT = "phd-epistemic-attacks-research"

BROAD_TERMS = [
    "parser", "authentication", "cryptography", "logging", "http client",
    "database", "testing", "validation", "serialization", "compression",
    "scheduler", "queue", "cache", "template", "router",
    "configuration", "cli", "date time", "file system", "image processing",
    "markdown", "websocket", "retry", "rate limit", "metrics",
    "email", "pdf", "graphql", "migration", "sanitizer",
]

SEED_HARVEST_DEPTH = 10
SEED_COUNT = 60
RESULTS_PER_INSTANCE = 3
REQUEST_PAUSE_S = 1.2


class RateLimited(RuntimeError):
    pass


def _get(url: str, attempts: int = 5) -> dict:
    """One GET, with exponential backoff on the registry's rate limiter.

    The search endpoint returns HTTP 429 under sustained use. Backing off and
    retrying is the documented remedy; the delay doubles each attempt so a
    long build slows down rather than failing.
    """
    delay = 2.0
    for attempt in range(attempts):
        req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
        try:
            with urllib.request.urlopen(req, timeout=60) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            if exc.code != 429 or attempt == attempts - 1:
                raise
            time.sleep(delay)
            delay *= 2
    raise RateLimited(url)


def search(text: str, size: int) -> list[dict]:
    url = f"{REGISTRY}/-/v1/search?" + urllib.parse.urlencode(
        {"text": text, "size": size}
    )
    return [o["package"] for o in _get(url).get("objects", [])]


def package_document(name: str) -> dict:
    return _get(f"{REGISTRY}/{urllib.parse.quote(name, safe='@')}")


def harvest_seeds() -> list[str]:
    counter: Counter[str] = Counter()
    for term in BROAD_TERMS:
        try:
            results = search(term, SEED_HARVEST_DEPTH)
        except Exception as exc:
            print(f"  broad term {term!r} failed: {type(exc).__name__}")
            continue
        for pkg in results:
            for keyword in pkg.get("keywords") or []:
                keyword = keyword.strip().lower()
                if keyword:
                    counter[keyword] += 1
        time.sleep(REQUEST_PAUSE_S)
    return [k for k, _ in counter.most_common(SEED_COUNT)]


def latest_version_document(doc: dict) -> dict:
    latest = (doc.get("dist-tags") or {}).get("latest")
    return (doc.get("versions") or {}).get(latest) or {}


def package_record(name: str) -> dict:
    doc = package_document(name)
    version_doc = latest_version_document(doc)
    times = doc.get("time") or {}
    latest = (doc.get("dist-tags") or {}).get("latest")
    return {
        "name": doc.get("name"),
        "latest_version": latest,
        "last_publish": times.get(latest),
        "created": times.get("created"),
        "release_count": len([k for k in times if k not in ("created", "modified")]),
        "deprecated": version_doc.get("deprecated"),
        "license": version_doc.get("license") or doc.get("license"),
        "maintainers": [m.get("name") for m in doc.get("maintainers") or []],
        "keywords": doc.get("keywords") or [],
        "repository": (doc.get("repository") or {}).get("url"),
        "homepage": doc.get("homepage"),
        "description": doc.get("description"),
        "readme": doc.get("readme"),
    }


def build() -> dict:
    fetched_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    seeds = harvest_seeds()
    print(f"harvested {len(seeds)} seeds from {len(BROAD_TERMS)} broad terms")

    instances = []
    seen_pairs = set()
    for index, seed in enumerate(seeds):
        try:
            results = search(seed, RESULTS_PER_INSTANCE)
        except Exception as exc:
            print(f"  [{index}] seed {seed!r} search failed: {type(exc).__name__}")
            continue
        names = [p["name"] for p in results]
        if len(names) < 2:
            print(f"  [{index}] seed {seed!r} returned {len(names)} results, skipped")
            continue
        key = tuple(sorted(names))
        if key in seen_pairs:
            print(f"  [{index}] seed {seed!r} duplicates an existing result set")
            continue
        seen_pairs.add(key)

        packages = []
        ok = True
        for name in names:
            try:
                packages.append(package_record(name))
            except Exception as exc:
                print(f"  [{index}] {name}: {type(exc).__name__}")
                ok = False
                break
            time.sleep(REQUEST_PAUSE_S)
        if not ok:
            continue

        instances.append(
            {
                "instance_id": f"npm-{index:03d}",
                "seed": seed,
                "packages": packages,
            }
        )
        print(f"  [{index}] {seed!r}: {', '.join(names)}")
        time.sleep(REQUEST_PAUSE_S)

    return {
        "source": "npm public registry",
        "fetched_at": fetched_at,
        "broad_terms": BROAD_TERMS,
        "seed_harvest_depth": SEED_HARVEST_DEPTH,
        "seed_count_requested": SEED_COUNT,
        "results_per_instance": RESULTS_PER_INSTANCE,
        "seeds": seeds,
        "instances": instances,
    }


def main() -> None:
    corpus = build()
    out = HERE / "corpus_npm.json"
    out.write_text(json.dumps(corpus, ensure_ascii=False, indent=2), encoding="utf-8")
    n_pkgs = sum(len(i["packages"]) for i in corpus["instances"])
    with_readme = sum(
        1 for i in corpus["instances"] for p in i["packages"] if p.get("readme")
    )
    deprecated = sum(
        1 for i in corpus["instances"] for p in i["packages"] if p.get("deprecated")
    )
    print(f"\nwrote {out}")
    print(f"  instances        : {len(corpus['instances'])}")
    print(f"  packages         : {n_pkgs}")
    print(f"  with readme      : {with_readme}")
    print(f"  deprecated flag  : {deprecated}")


if __name__ == "__main__":
    main()

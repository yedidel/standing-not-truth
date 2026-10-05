"""Build the natural commerce decision corpus from Amazon Reviews 2023.

Source: `McAuley-Lab/Amazon-Reviews-2023`, a standard, independently motivated
academic dataset of real product metadata. Nothing here is authored; every
title, seller-written description, feature bullet, price, store name and rating
is taken verbatim from the released file.

Choices fixed before any record was seen, so the construction order is
auditable:

  * Category: Electronics, because it is the category matching the commerce
    scenarios of the prior payments work (headphones, cameras, laptops).
  * Records are read in file order from the start of the shard. There is no
    sampling, ranking or selection.
  * A decision instance is a leaf category containing at least two products
    that each carry a price and a seller-written description, since that is the
    smallest structure in which an agent chooses between competing offers.

The file is 5.2 GB, so it is read with an HTTP range request rather than
downloaded whole.

Evidence-class mapping for this domain, from the AP2 role definition that makes
the merchant "responsible for the integrity of the inventory, pricing, and any
merchant discounts":

  bound     price, store, parent_asin
  observed  average_rating, rating_number  (platform-computed, not asserted
            by the seller)
  unbound   title, features, description   (seller-written prose)
"""

from __future__ import annotations

import json
import urllib.request
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).parent
DATASET = "McAuley-Lab/Amazon-Reviews-2023"
CATEGORY = "Electronics"
URL = (
    f"https://huggingface.co/datasets/{DATASET}/resolve/main/"
    f"raw/meta_categories/meta_{CATEGORY}.jsonl"
)
USER_AGENT = "phd-epistemic-attacks-research"

RANGE_BYTES = 12_000_000
PRODUCTS_PER_INSTANCE = 3
MAX_INSTANCES = 60


def fetch_records(limit_bytes: int) -> list[dict]:
    req = urllib.request.Request(
        URL, headers={"User-Agent": USER_AGENT, "Range": f"bytes=0-{limit_bytes}"}
    )
    with urllib.request.urlopen(req, timeout=180) as resp:
        raw = resp.read()
    records = []
    for line in raw.decode("utf-8", "ignore").split("\n")[:-1]:
        line = line.strip()
        if not line:
            continue
        try:
            records.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return records


def usable(record: dict) -> bool:
    """A product an agent could actually choose between: it must have a price
    the merchant is bound to, and seller-written prose to be judged on."""
    if not record.get("price"):
        return False
    if not record.get("store"):
        return False
    prose = (record.get("description") or []) + (record.get("features") or [])
    return any(str(p).strip() for p in prose)


def leaf_category(record: dict) -> str | None:
    cats = record.get("categories") or []
    return cats[-1] if cats else None


def product_record(record: dict) -> dict:
    return {
        "title": record.get("title"),
        "store": record.get("store"),
        "price": record.get("price"),
        "parent_asin": record.get("parent_asin"),
        "average_rating": record.get("average_rating"),
        "rating_number": record.get("rating_number"),
        "categories": record.get("categories"),
        "features": record.get("features") or [],
        "description": record.get("description") or [],
    }


def build() -> dict:
    fetched_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    records = fetch_records(RANGE_BYTES)
    print(f"read {len(records)} records from the first {RANGE_BYTES} bytes")

    by_leaf: dict[str, list[dict]] = defaultdict(list)
    for record in records:
        if not usable(record):
            continue
        leaf = leaf_category(record)
        if leaf:
            by_leaf[leaf].append(record)

    usable_count = sum(len(v) for v in by_leaf.values())
    print(f"usable products: {usable_count} across {len(by_leaf)} leaf categories")

    instances = []
    for leaf in sorted(by_leaf):
        group = by_leaf[leaf]
        if len(group) < 2:
            continue
        chosen = group[:PRODUCTS_PER_INSTANCE]
        instances.append(
            {
                "instance_id": f"amz-{len(instances):03d}",
                "leaf_category": leaf,
                "products": [product_record(r) for r in chosen],
            }
        )
        if len(instances) >= MAX_INSTANCES:
            break

    return {
        "source": DATASET,
        "category": CATEGORY,
        "url": URL,
        "range_bytes": RANGE_BYTES,
        "fetched_at": fetched_at,
        "records_read": len(records),
        "usable_products": usable_count,
        "leaf_categories": len(by_leaf),
        "instances": instances,
    }


def main() -> None:
    corpus = build()
    out = HERE / "corpus_commerce.json"
    out.write_text(json.dumps(corpus, ensure_ascii=False, indent=2), encoding="utf-8")
    n_products = sum(len(i["products"]) for i in corpus["instances"])
    print(f"\nwrote {out}")
    print(f"  instances : {len(corpus['instances'])}")
    print(f"  products  : {n_products}")


if __name__ == "__main__":
    main()

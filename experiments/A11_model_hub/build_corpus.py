"""Build a natural decision corpus from the Hugging Face model hub.

Motivation. A-10 found that almost every third-party claim in the npm and
commerce corpora is about an entity *outside* the option set, and concluded
that the in-set attack surface in natural traffic is under 1%. That conclusion
may be an artifact of those two corpora: package descriptions and product
listings are self-descriptions, and their conventions discourage naming a
direct competitor.

Model cards have the opposite convention. Comparative claims about other named
models are normal and expected -- "outperforms X on Y", "a drop-in replacement
for Z", "unlike A, this model ...". If the in-set rate is materially higher
here, the false-positive figures measured on npm and commerce do not transfer,
and the paper has to say so.

The domain is also the right one to test on its own merits: an agent choosing
which model weights to pull is an AI supply-chain decision with a real-world
side effect, and the hub is the retrieval path.

Construction mirrors the npm corpus: a fixed list of task queries determines
the searches, the hub's own ranking determines the option set, and every card
is stored verbatim with the fetch timestamp. No content is authored here.
"""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).parent
API = "https://huggingface.co/api"
USER_AGENT = "phd-epistemic-attacks-research"

# Task families, fixed before any result was seen. Chosen to span the hub's
# main pipeline tags rather than to favour any particular kind of card.
QUERIES = [
    "text classification", "named entity recognition", "question answering",
    "summarization", "translation", "sentence similarity", "fill mask",
    "zero shot classification", "token classification", "feature extraction",
    "text generation", "image classification", "object detection",
    "image segmentation", "speech recognition", "text to speech",
    "audio classification", "image to text", "reranker", "code generation",
]

RESULTS_PER_QUERY = 3
PAUSE_S = 0.6
CARD_CHARS = 6000


def _get(url: str, as_json: bool = True, attempts: int = 4):
    delay = 2.0
    for attempt in range(attempts):
        req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
        try:
            with urllib.request.urlopen(req, timeout=60) as resp:
                raw = resp.read()
            return json.loads(raw) if as_json else raw.decode("utf-8", "ignore")
        except urllib.error.HTTPError as exc:
            if exc.code == 404:
                raise
            if attempt == attempts - 1:
                raise
            time.sleep(delay)
            delay *= 2
        except Exception:
            if attempt == attempts - 1:
                raise
            time.sleep(delay)
            delay *= 2
    raise RuntimeError(url)


def search(query: str, limit: int) -> list[dict]:
    url = f"{API}/models?" + urllib.parse.urlencode(
        {"search": query, "sort": "downloads", "direction": -1, "limit": limit}
    )
    return _get(url)


def model_record(model_id: str) -> dict:
    info = _get(f"{API}/models/{urllib.parse.quote(model_id, safe='/')}")
    try:
        card = _get(
            f"https://huggingface.co/{model_id}/raw/main/README.md", as_json=False
        )
    except Exception:
        card = ""
    return {
        "model_id": model_id,
        "author": info.get("author") or model_id.split("/")[0],
        "downloads": info.get("downloads"),
        "likes": info.get("likes"),
        "last_modified": info.get("lastModified"),
        "created_at": info.get("createdAt"),
        "pipeline_tag": info.get("pipeline_tag"),
        "library_name": info.get("library_name"),
        "tags": (info.get("tags") or [])[:15],
        "gated": info.get("gated"),
        "disabled": info.get("disabled"),
        "card": card[:CARD_CHARS],
    }


def build() -> dict:
    fetched_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    instances, seen = [], set()
    for index, query in enumerate(QUERIES):
        try:
            hits = search(query, RESULTS_PER_QUERY)
        except Exception as exc:
            print(f"  [{index}] {query!r} search failed: {type(exc).__name__}")
            continue
        ids = [h["modelId"] for h in hits if h.get("modelId")]
        if len(ids) < 2:
            continue
        key = tuple(sorted(ids))
        if key in seen:
            continue
        seen.add(key)

        models, ok = [], True
        for model_id in ids:
            try:
                models.append(model_record(model_id))
            except Exception as exc:
                print(f"  [{index}] {model_id}: {type(exc).__name__}")
                ok = False
                break
            time.sleep(PAUSE_S)
        if not ok:
            continue

        instances.append(
            {
                "instance_id": f"hf-{len(instances):03d}",
                "query": query,
                "models": models,
            }
        )
        print(f"  [{index}] {query!r}: {', '.join(ids)}", flush=True)
        time.sleep(PAUSE_S)

    return {
        "source": "huggingface model hub",
        "fetched_at": fetched_at,
        "queries": QUERIES,
        "results_per_query": RESULTS_PER_QUERY,
        "card_chars": CARD_CHARS,
        "instances": instances,
    }


def main() -> None:
    corpus = build()
    out = HERE / "corpus_hf.json"
    out.write_text(json.dumps(corpus, ensure_ascii=False, indent=2), encoding="utf-8")
    models = sum(len(i["models"]) for i in corpus["instances"])
    with_card = sum(
        1 for i in corpus["instances"] for m in i["models"] if m.get("card")
    )
    print(f"\nwrote {out}")
    print(f"  instances  : {len(corpus['instances'])}")
    print(f"  models     : {models}")
    print(f"  with card  : {with_card}")


if __name__ == "__main__":
    main()

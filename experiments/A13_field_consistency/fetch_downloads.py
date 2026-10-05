"""Fetch real weekly download counts for the natural npm corpus.

Written after finding that A-13's specificity figure did not test what it
appeared to test. The corpus built in A-5 carries no download counts, so its
evaluator passed `weekly_downloads: None` for every package, and `field_check`
skips a field whose recorded value is absent. The download branch therefore
never fired on a single natural package, yet its silence was counted inside a
headline `0/177` covering all four fields.

That branch is the one most likely to misfire. It accepts any number at or
above one thousand appearing in a sentence that contains "download",
"downloads", "installs", "installations" or "weekly", and READMEs are full of
numbers: dependent counts, benchmark throughputs, byte sizes, star counts.

The npm downloads endpoint is public, unauthenticated and free.
"""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

HERE = Path(__file__).parent
CORPUS = HERE.parent / "A5_evidence_prevalence" / "corpus_npm.json"
OUT = HERE / "downloads_npm.json"

ENDPOINT = "https://api.npmjs.org/downloads/point/last-week/"
USER_AGENT = "epistemic-attacks-research/1.0"
PAUSE_S = 0.4


def get_downloads(name: str, attempts: int = 5) -> int | None:
    url = ENDPOINT + urllib.parse.quote(name, safe="@")
    delay = 2.0
    for attempt in range(attempts):
        req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
        try:
            with urllib.request.urlopen(req, timeout=60) as resp:
                return json.loads(resp.read().decode("utf-8")).get("downloads")
        except urllib.error.HTTPError as exc:
            if exc.code == 404:
                return None
            if exc.code != 429 or attempt == attempts - 1:
                raise
            time.sleep(delay)
            delay *= 2
        except urllib.error.URLError:
            if attempt == attempts - 1:
                raise
            time.sleep(delay)
            delay *= 2
    return None


def main() -> None:
    corpus = json.loads(CORPUS.read_text(encoding="utf-8"))
    names = []
    for instance in corpus["instances"]:
        for package in instance["packages"]:
            if package["name"] not in names:
                names.append(package["name"])

    counts: dict[str, int | None] = {}
    if OUT.exists():
        counts = json.loads(OUT.read_text(encoding="utf-8"))

    for index, name in enumerate(names, 1):
        if name in counts:
            continue
        try:
            counts[name] = get_downloads(name)
        except Exception as exc:
            print(f"  {name}: {type(exc).__name__}", flush=True)
            counts[name] = None
        if index % 20 == 0:
            print(f"  {index}/{len(names)}", flush=True)
            OUT.write_text(json.dumps(counts, indent=2), encoding="utf-8")
        time.sleep(PAUSE_S)

    OUT.write_text(json.dumps(counts, indent=2), encoding="utf-8")
    have = sum(1 for v in counts.values() if v is not None)
    print(f"\n{have}/{len(names)} packages have a weekly download count")


if __name__ == "__main__":
    main()
